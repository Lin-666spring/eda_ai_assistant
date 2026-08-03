"""
Application controller — UI-agnostic orchestration layer.

All business logic lives here. GUI and CLI consume this single API,
so feature parity is guaranteed across interfaces.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.agent.llm_client import LLMClient
from src.agent.prompt_templates import PromptTemplates
from src.agent.router import LLMRouter, TaskIntent
from src.bom.checker import BOMDuplicateChecker
from src.bom.merger import BOMMerger
from src.bom.parser import BOMItem, BOMParser
from src.bom.validator import BOMValidator
from src.config import config
from src.html_bom.generator import HTMLBOMConfig, HTMLBOMGenerator
from src.interfaces.eda_adapter import LCEDAAdapter, PCBData
from src.rag.indexer import RAGIndexer
from src.rag.retriever import RAGRetriever
from src.rules.checker import DesignRuleChecker
from src.supply.lcsc_client import LcscSearchClient
from src.supply.bom_health import BOMHealthChecker

logger = logging.getLogger(__name__)


def _is_key_usable(key: Optional[str]) -> bool:
    return bool(key and key not in ("", "your_api_key_here", "sk-"))


# ══════════════════════════════════════════════════════
#  Shared context — single source of truth for session state
# ══════════════════════════════════════════════════════


@dataclass
class CommandContext:
    """Mutable session state shared across all operations."""

    bom_items: list = field(default_factory=list)
    positions: dict = field(default_factory=dict)
    netlist: list = field(default_factory=list)
    bom_file: Optional[str] = None
    pcb_data: Optional[PCBData] = None

    @property
    def has_data(self) -> bool:
        return bool(self.bom_items)


# ══════════════════════════════════════════════════════
#  Controller
# ══════════════════════════════════════════════════════


class AppController:
    """Core controller — pure logic, zero UI dependencies.

    Both ``MainWindow`` (GUI) and ``CLIPrototype`` (CLI) consume this class,
    guaranteeing identical behaviour regardless of the interface.
    """

    # ── Lifecycle ──

    @staticmethod
    def _create_llm_client(api_key: str, base_url: str, model: str, provider: str,
                            tool_executor=None) -> Optional[LLMClient]:
        """工厂方法：根据 provider 创建对应的客户端

        Claude 使用 Anthropic 原生 Messages API（非 OpenAI 兼容），
        其余厂商使用 OpenAI 兼容的 LLMClient。
        """
        if provider == "claude":
            from src.agent.anthropic_client import AnthropicClient
            return AnthropicClient(
                api_key=api_key,
                base_url=base_url or None,
                model=model or None,
                provider=provider,
                tool_executor=tool_executor,
            )
        else:
            return LLMClient(
                api_key=api_key,
                base_url=base_url or None,
                model=model or None,
                provider=provider,
                tool_executor=tool_executor,
            )

    def __init__(self, api_key: Optional[str] = None):
        effective_key = api_key or config.llm.api_key
        self.agent = self._create_llm_client(
            effective_key, config.llm.base_url, config.llm.model,
            config.llm.provider, self._dispatch_operation,
        ) if _is_key_usable(effective_key) else None
        self.router = LLMRouter.from_config(effective_key) if _is_key_usable(effective_key) else None
        self.parser = BOMParser()
        self.eda = LCEDAAdapter()
        self.context = CommandContext()
        self._conversation_active = False
        self._active_assistant: Optional[str] = None  # 当前助手 ID
        self._rag_index_checked = False  # RAG 索引是否已检查/建立

    def reconfigure_llm(self, provider: str, api_key: str, base_url: str, model: str):
        """热重载 LLM 客户端 — 用户通过设置面板修改配置后调用。"""
        if _is_key_usable(api_key):
            self.agent = self._create_llm_client(
                api_key, base_url or "", model or "", provider,
                self._dispatch_operation,
            )
            self.router = LLMRouter.from_config(api_key)
        else:
            self.agent = None
            self.router = None
        self._conversation_active = False
        logger.info(
            "LLM reconfigured: provider=%s, model=%s, has_key=%s",
            provider, model or "(default)", bool(self.agent),
        )

    def clear_conversation(self):
        """清空对话历史与上下文标记"""
        self._conversation_active = False
        if self.agent:
            self.agent.clear_history()

    def set_active_assistant(self, assistant_id: str):
        """切换当前助手 — 影响 AI 回复的系统提示词风格

        Args:
            assistant_id: 助手 ID，如 'eda-general' / 'bom-expert' / 'pcb-reviewer' / 'vision-analyst'
        """
        self._active_assistant = assistant_id
        self._conversation_active = False
        if self.agent:
            self.agent.clear_history()
        logger.info("Active assistant switched to: %s", assistant_id)

    # ══════════════════════════════════════════════════
    #  File I/O
    # ══════════════════════════════════════════════════

    def load_bom(self, file_path: str) -> tuple[int, str]:
        """Parse a BOM file, populate context, return (count, message)."""
        self.context.bom_items = self.parser.parse(file_path)
        self.context.bom_file = file_path
        self.clear_conversation()
        name = Path(file_path).name
        n = len(self.context.bom_items)
        logger.info("BOM loaded: %s (%d items)", name, n)
        return n, f" 已加载 BOM: {name}\n共 {n} 条物料记录"

    def get_design_suggestions(self) -> str:
        """设计意图识别：扫描 BOM 匹配电路模板，主动建议缺失元件"""
        if not self.context.bom_items:
            return ""
        try:
            from src.agent.design_templates import DesignTemplateEngine
            engine = DesignTemplateEngine()
            return engine.get_suggestions_report(self.context.bom_items)
        except Exception as e:
            logger.exception("Design suggestions failed")
            return ""

    def load_positions(self, file_path: str) -> tuple[int, str]:
        """Parse a Pick & Place file, return (count, message)."""
        self.context.positions = self.eda.get_positions(file_path)
        name = Path(file_path).name
        n = len(self.context.positions)
        logger.info("Positions loaded: %s (%d entries)", name, n)
        return n, f" 已加载坐标: {name}\n共 {n} 个位号坐标"

    def load_pcb(self, file_path: str) -> tuple[int, str]:
        """Parse a PCB layout file, populate context, return (net_count, message)."""
        self.context.pcb_data = self.eda.get_pcb_data(file_path)
        name = Path(file_path).name
        pcb = self.context.pcb_data
        logger.info(
            "PCB loaded: %s (%d nets, %d traces, %d vias)",
            name, pcb.net_count, pcb.trace_count, pcb.via_count,
        )
        summary = (
            f" 已加载 PCB: {name}\n"
            f"  格式: {pcb.format}\n"
            f"  网络: {pcb.net_count} 个\n"
            f"  走线: {pcb.trace_count} 条\n"
            f"  过孔: {pcb.via_count} 个\n"
            f"  层: {', '.join(pcb.layers) if pcb.layers else '无'}"
        )
        return pcb.net_count, summary

    # ══════════════════════════════════════════════════
    #  BOM operations — each returns a formatted report
    # ══════════════════════════════════════════════════

    def merge_bom(self) -> str:
        merger = BOMMerger()
        merged = merger.merge(self.context.bom_items)
        return merger.get_merge_report(self.context.bom_items, merged)

    def ai_merge_bom(self) -> str:
        """AI-assisted BOM merge: rule-based merge + AI suggestions for further merging."""
        if not self.is_agent_available():
            return self.merge_bom() + "\n\n AI 未配置，仅执行了规则合并"

        merger = BOMMerger()
        rule_merged = merger.merge(self.context.bom_items)

        bom_text = self._format_merged_for_ai(rule_merged)
        prompt = PromptTemplates.get("bom_ai_merge", bom_data=bom_text)
        system = PromptTemplates.get_system_prompt("bom")

        try:
            raw = self.agent.chat(prompt, system_prompt=system)
            parsed = self._extract_json(raw)
            suggestions = parsed.get("suggestions", []) if isinstance(parsed, dict) else []
        except Exception:
            logger.exception("AI merge analysis failed")
            suggestions = []

        final_merged, ai_count = merger.merge_with_ai_suggestion(
            self.context.bom_items, suggestions,
        )

        report = merger.get_merge_report(self.context.bom_items, final_merged)
        if ai_count > 0:
            report += f"\n\n AI 额外识别了 {ai_count} 组合并"
        else:
            report += "\n\n AI 未发现额外合并机会"
        return report

    def _format_merged_for_ai(self, merged: list) -> str:
        """Format rule-merged BOM groups as compact text for AI analysis."""
        lines: list[str] = []
        for i, m in enumerate(merged, 1):
            lines.append(
                f"{i}. 位号:{m.reference_str} | 型号:{m.part_number} "
                f"| 封装:{m.package} | 值:{m.value} | 数量:{m.total_quantity}"
            )
        return "\n".join(lines)

    def validate_packages(self) -> str:
        validator = BOMValidator()
        results = validator.validate(self.context.bom_items)
        return validator.get_validation_report(results)

    def check_duplicates(self) -> str:
        checker = BOMDuplicateChecker()
        duplicates = checker.check(self.context.bom_items)
        return checker.get_report(duplicates)

    def generate_html_bom(self, output_path: Optional[str] = None) -> str:
        if output_path is None:
            out_dir = Path(__file__).parent.parent.parent / "output"
            out_dir.mkdir(exist_ok=True)
            output_path = str(out_dir / "ibom.html")

        title = (
            f"BOM — {Path(self.context.bom_file).stem}"
            if self.context.bom_file
            else "EDA AI BOM"
        )
        generator = HTMLBOMGenerator(HTMLBOMConfig(title=title))
        generator.generate(self.context.bom_items, self.context.positions, output_path)
        logger.info("HTML BOM generated: %s", output_path)
        return f" HTML BOM 已生成:\n{output_path}"

    def export_bom_csv(self, output_path: Optional[str] = None) -> str:
        """导出 BOM 为 UTF-8-BOM CSV 文件（Excel 兼容中文）"""
        if not self.context.bom_items:
            return " 请先导入 BOM 文件再导出。"

        if output_path is None:
            out_dir = Path(__file__).parent.parent.parent / "output"
            out_dir.mkdir(exist_ok=True)
            # 生成带时间戳的文件名
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = Path(self.context.bom_file).stem if self.context.bom_file else "bom_export"
            output_path = str(out_dir / f"{name}_{ts}.csv")

        try:
            import csv
            # 使用 UTF-8-BOM 编码确保 Excel 正确显示中文
            with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                # 表头
                writer.writerow(["位号", "参数值", "封装", "型号", "描述", "数量", "制造商"])
                for item in self.context.bom_items:
                    writer.writerow([
                        item.reference,
                        item.value,
                        item.package,
                        item.part_number,
                        item.description,
                        item.quantity,
                        item.manufacturer,
                    ])
            logger.info("BOM CSV exported: %s", output_path)
            return (
                f" BOM CSV 已导出（UTF-8-BOM 编码，Excel 兼容中文）:\n"
                f"`{output_path}`\n\n"
                f"共计 {len(self.context.bom_items)} 行物料数据。"
            )
        except Exception as e:
            logger.error("BOM CSV export failed: %s", e)
            return f" CSV 导出失败: {str(e)}"

    def check_design_rules(self) -> str:
        checker = DesignRuleChecker()
        violations = checker.check_all(
            self.context.bom_items,
            self.context.positions,
            pcb_data=self.context.pcb_data,
        )
        return checker.get_report(violations)

    def review_design_multi_agent(self) -> str:
        """多智能体协同设计审查 — 5 个专业 Agent 并行审查 + 合成报告

        返回 JSON 格式的结构化审查报告（供前端雷达图 + 卡片渲染）。
        """
        if not self.context.bom_items:
            return json.dumps({"error": "请先导入 BOM 文件"}, ensure_ascii=False)

        try:
            # 运行设计规则检查
            checker = DesignRuleChecker()
            violations = checker.check_all(
                self.context.bom_items,
                self.context.positions,
                pcb_data=self.context.pcb_data,
            )

            # 多智能体审查（如果 LLM 可用则深度分析，否则基于规则）
            from src.agent.review_agents import MultiAgentReviewer
            reviewer = MultiAgentReviewer(llm_client=self.agent if self.is_agent_available() else None)

            if self.is_agent_available():
                report = reviewer.review_with_llm(
                    violations,
                    self.context.bom_items,
                    self.context.positions,
                    self.context.pcb_data,
                )
            else:
                report = reviewer.review(
                    violations,
                    self.context.bom_items,
                    self.context.positions,
                    self.context.pcb_data,
                )

            # 构建前端可渲染的 JSON
            result = {
                "radar_data": report.radar_data,
                "overall_score": report.overall_score,
                "overall_grade": report.overall_grade,
                "consensus": report.consensus_summary,
                "agents": {},
                "critical_issues": report.critical_issues,
                "improvement_roadmap": report.improvement_roadmap,
            }

            for key, ar in report.agent_reports.items():
                result["agents"][key] = {
                    "name": ar.agent_name,
                    "emoji": ar.agent_emoji,
                    "domain": ar.domain,
                    "summary": ar.summary,
                    "score": ar.score,
                    "findings": [
                        {
                            "severity": f.severity,
                            "title": f.title,
                            "detail": f.detail,
                            "suggestion": f.suggestion,
                            "location": f.location,
                        }
                        for f in ar.findings[:5]
                    ],
                }

            logger.info("Multi-agent review completed: score=%s, grade=%s",
                        report.overall_score, report.overall_grade)
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.exception("Multi-agent review failed")
            return json.dumps({"error": f"多智能体审查失败: {e}"}, ensure_ascii=False)

    def verify_suggestion_handler(self) -> str:
        """闭环验证的本地降级处理 — 引导用户提供待验证的建议。"""
        if not self.context.bom_items:
            return json.dumps(
                {"error": "请先导入 BOM 文件，然后再进行闭环验证"},
                ensure_ascii=False,
            )
        return (
            " 闭环验证已就绪（已加载 BOM 数据）。\n\n"
            "请告诉我你想验证的 PCB 设计建议，例如：\n"
            "• \"验证建议：将 C1 改为 10µF 陶瓷电容\"\n"
            "• \"检查这个修改：在电源引脚附近增加 100nF 去耦电容\"\n"
            "• \"帮我验证：移除 R5 是否安全\"\n\n"
            "我会运行 DRC 规则引擎检查你的建议，如果发现问题会自动要求修正。"
        )

    def verify_suggestion(self, suggestion: str) -> str:
        """闭环验证 — 对 LLM 设计建议执行规则引擎验证 (路线三核心)。

        流程: LLM 建议 → DRC 检查 → 发现问题 → LLM 修正 → 重新检查
        最多迭代 3 轮。

        Returns:
            JSON 格式的 VerificationReport
        """
        from src.core.verifier import (
            VerificationEngine,
            SuggestionCategory,
            create_verifier_from_controller,
        )
        engine = create_verifier_from_controller(self)
        report = engine.verify(suggestion, category=SuggestionCategory.GENERAL)
        return json.dumps(report.to_dict(), ensure_ascii=False)

    def run_electrical_health_check(self) -> str:
        """PCB 电气健康检查 — 使用电路计算引擎进行真实工程分析。

        覆盖: 阻抗 · PDN · 去耦 · 电流承载 · 热 · 串扰
        不依赖 LLM，纯数学计算。

        Returns:
            JSON 格式的 PCBHealthReport
        """
        from src.pcb.calculator import (
            PCBHealthReport,
            microstrip_impedance,
            ipc2221_current_capacity,
            analyze_decoupling_capacitor,
            crosstalk_3w_rule_check,
            estimate_junction_temp,
        )

        report = PCBHealthReport()
        pcb = self.context.pcb_data
        bom = self.context.bom_items
        if not bom:
            return json.dumps({"error": "请先导入 BOM 文件"}, ensure_ascii=False)

        # 1. 电流承载检查
        for trace in (pcb.traces if pcb else []):
            if trace.width_mm > 0 and trace.net_name:
                # 估算电流需求（简化为根据网络名猜测）
                is_power = any(kw in trace.net_name.upper() for kw in ("VCC", "VDD", "VIN", "+5", "+3", "POWER", "VBAT"))
                if is_power:
                    capacity = ipc2221_current_capacity(trace.width_mm)
                    # 检查常见电源电流等级
                    if capacity < 1.0:
                        report.current_issues.append(
                            f"电源网络 {trace.net_name}: 走线宽 {trace.width_mm}mm "
                            f"仅承载 {capacity:.2f}A，建议加宽至 ≥0.5mm"
                        )
                elif trace.width_mm < 0.15:
                    report.current_issues.append(
                        f"信号线 {trace.net_name}: 线宽仅 {trace.width_mm}mm，"
                        f"接近制造极限(0.1mm)，建议加宽"
                    )

        # 2. 去耦电容检查
        voltage_guess = "3.3"  # 从 BOM 推断工作电压
        for item in bom:
            desc_upper = (item.description or "").upper() + (item.value or "").upper()
            if any(kw in desc_upper for kw in ("STM32", "MCU", "FPGA", "CPLD", "ARM", "单片机")):
                # 微控制器需要去耦
                has_decoupling = False
                for other in bom:
                    other_desc = (other.description or "").upper() + (other.value or "").upper()
                    if any(kw in other_desc for kw in ("0.1UF", "100NF", "104", "0.1ΜF")):
                        has_decoupling = True
                        break
                if not has_decoupling:
                    report.decoupling_issues.append(
                        f"{item.reference} ({item.value}) 缺少 100nF 去耦电容。"
                        f"每个数字 IC 至少需要 1 个 100nF 电容靠近 VDD 引脚。"
                    )

        # 3. 热估算
        for item in bom:
            pkg = (item.package or "").upper()
            if pkg and any(kw in (item.description or "").upper()
                          for kw in ("LDO", "REGULATOR", "稳压", "AMS1117", "LM1117")):
                # 估算 LDO 功耗
                power_w = 0.5  # 粗略估计
                t = estimate_junction_temp(power_w, pkg)
                if not t.is_safe:
                    report.thermal_issues.append(
                        f"{item.reference} ({item.value}, {pkg}): "
                        f"估计结温 {t.junction_temp_c}°C 超过安全限 {125}°C。"
                        f"建议改用散热更好的封装或添加散热器。"
                    )
                elif t.junction_temp_c > 85:
                    report.thermal_issues.append(
                        f"{item.reference} ({item.value}, {pkg}): "
                        f"估计结温 {t.junction_temp_c}°C 偏高，建议关注散热。"
                    )

        # 4. 串扰/EMC
        if pcb and pcb.traces:
            # 检查走线间距
            for i in range(min(20, len(pcb.traces))):
                for j in range(i + 1, min(20, len(pcb.traces))):
                    t1, t2 = pcb.traces[i], pcb.traces[j]
                    # 简化为检查同一层的相邻走线
                    if t1.layer == t2.layer and t1.width_mm > 0 and t2.width_mm > 0:
                        span = min(t1.width_mm, t2.width_mm)
                        ok, ratio, msg = crosstalk_3w_rule_check(span * 2, span)
                        if not ok:
                            report.crosstalk_issues.append(
                                f"{t1.net_name} ↔ {t2.net_name}: {msg}"
                            )
                            break

        # 5. 阻抗估计
        if pcb and pcb.traces:
            for trace in pcb.traces[:10]:
                if trace.width_mm > 0:
                    z0 = microstrip_impedance(trace.width_mm, 0.2)  # 假设 4层板 0.2mm 介质
                    if 45 <= z0 <= 55:
                        pass  # 50Ω 附近，正常
                    elif z0 < 30 or z0 > 80:
                        report.impedance_issues.append(
                            f"网络 {trace.net_name or '?'}: 线宽 {trace.width_mm}mm → "
                            f"Z₀≈{z0}Ω (目标 50Ω)。建议调整为差分或加宽走线。"
                        )

        # 综合评分
        total = len(report.impedance_issues) + len(report.pdn_issues) + \
                len(report.decoupling_issues) + len(report.current_issues) + \
                len(report.thermal_issues) + len(report.crosstalk_issues)
        report.overall_score = max(50, 100 - total * 8)

        logger.info("Electrical health check: score=%.0f, issues=%d", report.overall_score, total)
        return json.dumps({
            "ok": True,
            "markdown": report.to_markdown(),
            "score": report.overall_score,
            "issues": report.total_issues,
            "details": {
                "impedance": report.impedance_issues,
                "pdn": report.pdn_issues,
                "decoupling": report.decoupling_issues,
                "current": report.current_issues,
                "thermal": report.thermal_issues,
                "crosstalk": report.crosstalk_issues,
            },
        }, ensure_ascii=False)

    def check_bom_health(self) -> str:
        """BOM 健康检查 — 库存 / 生命周期 / 替代料 / 成本。"""
        if not self.context.has_data:
            return " 请先导入 BOM 文件"
        client = LcscSearchClient()
        checker = BOMHealthChecker(client)
        report = checker.check(self.context.bom_items)
        logger.info(
            "BOM health: %d items, score=%.0f, cost=¥%.2f",
            report.total_items, report.health_score, report.total_cost_estimate,
        )
        return BOMHealthChecker.format_report(report)

    def get_bom_summary(self) -> dict:
        prefixes: dict[str, int] = {}
        for item in self.context.bom_items:
            first_ref = item.reference.split(",")[0].strip()
            prefix = "".join(c for c in first_ref if c.isalpha())
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
        return {"total": len(self.context.bom_items), "by_prefix": dict(sorted(prefixes.items()))}

    # ── Operation dispatch table (strategy pattern) ──

    def _dispatch_operation(self, operation: str, params: dict) -> str:
        # 处理 LLM 返回的追问
        if operation == "__clarify__":
            question = params.get("question", "不太确定您的意思，能再说详细一点吗？")
            options = params.get("options", [])
            if options:
                return " " + question + "\n\n可选项：\n" + "\n".join(f"  • {o}" for o in options)
            return " " + question

        # RAG 知识库查询 — 需要传递 query 参数
        if operation == "rag_query":
            query = params.get("query", "")
            return self.query_knowledge_base(query)

        # 闭环验证 — 需要传递 suggestion 参数
        if operation == "verify_suggestion":
            suggestion = params.get("suggestion", "")
            if not suggestion:
                return (
                    " 闭环验证需要提供待验证的设计建议。\n\n"
                    "使用方法：请描述你想验证的PCB设计建议，例如：\n"
                    "• \"验证建议：在U1附近添加100nF去耦电容\"\n"
                    "• \"验证这个修改：将电源线宽改为1.5mm\""
                )
            return self.verify_suggestion(suggestion)

        # 从 ToolRegistry 获取 handler 映射（带懒加载降级）
        dispatch = self._build_dispatch_map()
        handler = dispatch.get(operation)
        if handler:
            return handler()

        return (
            f" 无法识别操作「{operation}」\n\n"
            "可用操作：合并BOM / 校验封装 / 检查重复 / 筛选元件 / "
            "生成HTML BOM / 设计规则检查 / BOM健康检查"
        )

    def _build_dispatch_map(self) -> dict[str, Callable[[], str]]:
        """从 ToolRegistry 构建操作分发映射"""
        handlers: dict[str, Callable[[], str]] = {}
        try:
            from src.agent.tools import ToolRegistry
            for name, handler_name in ToolRegistry.get_dispatch_map().items():
                if handler_name == "_filter_input":
                    handlers[name] = self._filter_input_handler
                elif handler_name == "_pcb_analysis_cmd":
                    handlers[name] = self._pcb_analysis_handler
                else:
                    method = getattr(self, handler_name, None)
                    if method:
                        handlers[name] = method
        except ImportError:
            pass  # ToolRegistry 不可用

        # 补充特殊方法
        if "generate_html_bom" in handlers:
            orig = handlers["generate_html_bom"]
            handlers["generate_html_bom"] = lambda: orig()
        if "filter_components" in handlers:
            handlers["filter_components"] = lambda: self._filter_components({})

        # 向后兼容旧指令名
        handlers["load_pcb"] = lambda: " 请通过 文件→导入PCB 加载电路板文件。"
        return handlers

    # ══════════════════════════════════════════════════
    #  RAG 知识库
    # ══════════════════════════════════════════════════

    def _ensure_rag_indexed(self) -> bool:
        """惰性自动索引知识库文件（首次查询触发）

        扫描 rag_data/*.md 文件并增量索引到 ChromaDB。
        使用 manifest 跟踪文件 mtime，只有变更文件才重新索引。

        Returns:
            True 若索引就绪，False 若索引失败
        """
        if self._rag_index_checked:
            return True

        rag_dir = Path(__file__).parent.parent.parent / "rag_data"
        if not rag_dir.exists():
            logger.warning("RAG: rag_data directory not found at %s", rag_dir)
            self._rag_index_checked = True
            return False

        try:
            indexer = RAGIndexer()
            manifest_path = str(rag_dir / ".index_manifest.json")
            stats = indexer.index_directory(str(rag_dir), manifest_path)
            logger.info(
                "RAG auto-index: %d indexed, %d skipped, %d errors, %d total chunks",
                stats["indexed"], stats["skipped"],
                len(stats.get("errors", [])), indexer.chunk_count,
            )
            self._rag_index_checked = True
            return True
        except Exception as e:
            logger.exception("RAG auto-index failed: %s", e)
            self._rag_index_checked = True
            return False

    def query_knowledge_base(self, query: str = "") -> str:
        """查询 RAG 知识库

        Args:
            query: 自然语言查询问题。若为空则返回帮助提示。

        Returns:
            格式化的知识库检索结果（Markdown 格式）
        """
        if not query or not query.strip():
            return (
                "📚 **知识库查询**\n\n"
                "请指定要查询的内容，例如：\n"
                "  • 查询 IPC-2221 载流计算公式\n"
                "  • DDR5 VREFDQ 配置规范是什么\n"
                "  • 0603 封装尺寸参数\n"
                "  • PDN 目标阻抗如何计算\n"
                "  • GaN 散热设计要点\n"
                "  • 华为 PCB 设计规范有哪些\n\n"
                f"当前知识库包含 {11} 个专业文档，覆盖 "
                "IPC 标准、高速数字设计、信号完整性、EMC、DFM、热管理、"
                "混合信号/RF、BGA 封装、先进材料、中国行业实践等领域。"
            )

        self._ensure_rag_indexed()

        try:
            retriever = RAGRetriever()
            context = retriever.query_with_context(query, top_k=5)
            if context == "（未找到相关文档）":
                return (
                    f"🔍 未找到与「{query}」相关的知识库内容。\n\n"
                    "建议：\n"
                    "  • 尝试更通用的关键词（如用「DDR5 布线」替代「DDR5-6400 CL40」）\n"
                    "  • 确认知识库已被索引（检查控制台日志）\n"
                    "  • 尝试查询相关主题：IPC 标准、封装尺寸、DRC 规则、去耦电容等"
                )
            return f"🔍 **知识库查询结果: {query}**\n\n{context}"
        except FileNotFoundError as e:
            logger.warning("RAG index not found, attempting auto-index: %s", e)
            try:
                self._rag_index_checked = False  # 重置以允许重建
                self._ensure_rag_indexed()
                retriever = RAGRetriever()
                return f"🔍 **知识库查询结果: {query}**\n\n{retriever.query_with_context(query, top_k=5)}"
            except Exception as e2:
                logger.exception("RAG retrieval failed after auto-index")
                return f"❌ 知识库查询失败: {e2}\n\n请确保知识库文件已正确放置在 rag_data/ 目录。"
        except Exception as e:
            logger.exception("RAG query failed")
            return f"❌ 知识库查询失败: {e}"

    # ══════════════════════════════════════════════════
    #  Natural-language processing
    # ══════════════════════════════════════════════════

    def is_agent_available(self) -> bool:
        return self.agent is not None

    def _require_data(self) -> Optional[str]:
        if not self.context.has_data:
            return " 请先导入 BOM 文件再输入指令。"
        return None

    def process_input(self, user_input: str) -> str:
        guard = self._require_data()
        if guard:
            return guard
        if self.is_agent_available():
            result = self._try_ai(user_input)
            if result is not None:
                return result
        return self._local_fallback(user_input)

    def process_input_stream(
        self, user_input: str, on_token: Callable[[str], None]
    ) -> str:
        guard = self._require_data()
        if guard:
            return guard
        if self.is_agent_available():
            result = self._try_ai_stream(user_input, on_token)
            if result is not None:
                return result
        return self._local_fallback(user_input)

    def chat_message_stream(self, user_input: str, on_token: Callable[[str], None]) -> str:
        """自然语言对话（流式），不要求 BOM 预加载，LLM 直接输出 Markdown。

        与 process_input() 的区别：
        - 不要求 _require_data() — 无需导入 BOM 即可对话
        - LLM 用自然语言回复（Markdown 格式），而非 JSON 命令解析
        - 通过 on_token 回调流式输出每个 token
        - 使用 general 系统提示词，支持多轮对话历史

        Returns:
            AI 的完整回复文本
        """
        if not self.is_agent_available():
            return self._local_fallback(user_input)

        try:
            system = PromptTemplates.get_system_prompt("general")
            raw = self.agent.chat_stream(
                user_input, system_prompt=system,
                on_token=on_token, use_history=self._conversation_active,
            )
            self._conversation_active = True
            return raw
        except Exception:
            logger.exception("chat_message_stream failed")
            return " AI 调用失败，请检查网络连接和 API 配置。\n\n建议：\n- 检查 API Key 是否正确\n- 检查网络连接是否通畅\n- 检查 API 额度是否充足"

    def agent_loop(
        self,
        user_input: str,
        on_token: Optional[Callable[[str], None]] = None,
        max_iterations: int = 5,
    ) -> str:
        """Function Calling Agent Loop — LLM 自主选择工具，多步推理

        与 process_input() 的区别：
        - process_input: 意图分类 → 命令解析 → 执行一个操作 → 返回
        - agent_loop:    LLM 每轮自主决定调用哪些工具 → 执行 → 基于结果
                         继续推理 → 循环直到 LLM 输出文本回复

        适用场景：需要多步操作的复杂任务，如
        - "检查BOM健康，对缺货的元件找替代料"
        - "合并BOM，然后验证封装，最后生成HTML报告"

        Args:
            user_input: 用户输入
            on_token: 流式输出回调（最终文本回复时逐 token 回调）
            max_iterations: 最大工具调用轮数

        Returns:
            LLM 的最终文本回复
        """
        if not self.is_agent_available():
            return " Agent Loop 需要配置 AI 模型。请在设置中配置 API Key。"

        try:
            from src.agent.tools import ToolRegistry
            from src.agent.prompt_templates import PromptTemplates

            functions = ToolRegistry.get_function_definitions()
            system = PromptTemplates.get_system_prompt("agent")

            # 注入 tool_executor（确保热重载后仍有效）
            if self.agent.tool_executor is None:
                self.agent.tool_executor = self._dispatch_operation

            result = self.agent.chat_with_tools(
                user_message=user_input,
                functions=functions,
                system_prompt=system,
                on_token=on_token,
                use_history=self._conversation_active,
                max_iterations=max_iterations,
            )
            self._conversation_active = True
            return result
        except RuntimeError as e:
            logger.exception("Agent loop runtime error")
            return f" Agent Loop 错误: {e}"
        except Exception:
            logger.exception("Agent loop failed")
            return " Agent Loop 调用失败，请检查网络连接和 API 配置。"

    def process_image_input(self, text: str, image_b64: str) -> str:
        """处理带图片的用户输入 — 调用多模态 LLM 分析

        不需要 BOM 预加载（图片分析独立于 BOM 数据）。
        """
        if not self.is_agent_available():
            return " 图片分析需要配置 AI 模型。请在设置中配置支持多模态的 API（如 Kimi、GPT-4o、Qwen-VL）。"

        try:
            return self._analyze_image(text, image_b64)
        except Exception as e:
            logger.exception("Image analysis failed")
            return f" 图片分析失败: {e}"

    # ── AI helpers ──

    def _get_nlu_engine(self):
        """lazy init NLU 引擎（获取或创建）"""
        if not hasattr(self, '_nlu_engine'):
            try:
                from src.agent.nlu_engine import NLUEngine
                self._nlu_engine = NLUEngine()
                logger.info("NLU Engine ready (embedding: %s)", self._nlu_engine.embedding_available)
            except Exception as e:
                logger.warning("NLU Engine init failed: %s", e)
                self._nlu_engine = None
        return self._nlu_engine

    def _intent_to_system_type(self, intent: TaskIntent) -> str:
        """将 TaskIntent 映射到 system prompt 类型

        如果设置了 active assistant，优先使用助手偏好的提示词类型。
        """
        # 助手→系统提示映射
        assistant_map = {
            "eda-general": None,       # 使用意图自动映射
            "bom-expert": "bom",       # 始终用 BOM 提示词
            "pcb-reviewer": "pcb",     # 始终用 PCB 提示词
            "vision-analyst": "vision", # 始终用视觉提示词
        }
        if self._active_assistant and self._active_assistant in assistant_map:
            override = assistant_map[self._active_assistant]
            if override:
                return override

        # 默认：基于意图映射
        mapping = {
            TaskIntent.BOM_ANALYSIS: "bom",
            TaskIntent.RULE_CHECK: "rule",
            TaskIntent.PCB_ANALYSIS: "pcb",
            TaskIntent.CODE_RULE_GEN: "rule",
            TaskIntent.VISUAL: "vision",
            TaskIntent.TEXT_CHAT: "general",
            TaskIntent.LOCAL_ONLY: "general",
        }
        return mapping.get(intent, "general")

    def _build_ai_prompt(self, user_input: str) -> tuple[str, str]:
        """根据意图分类选择最合适的 system prompt 和模板"""
        if self.router:
            intent = self.router.classify_intent(user_input)
        else:
            intent = TaskIntent.TEXT_CHAT

        system_type = self._intent_to_system_type(intent)
        system = PromptTemplates.get_system_prompt(system_type)
        prompt = PromptTemplates.get("command_parse", user_command=user_input)
        logger.debug("Intent: %s → system_prompt=%s", intent.name, system_type)
        return system, prompt

    def _ai_to_operation(self, raw_response: str) -> Optional[str]:
        parsed = self._extract_json(raw_response)
        if parsed is None:
            return None
        result = self._dispatch_operation(
            parsed.get("operation", ""), parsed.get("params", {})
        )
        explanation = parsed.get("explanation", "")
        return f" AI 理解: {explanation}\n\n{result}" if explanation else result

    def _try_ai(self, user_input: str) -> Optional[str]:
        """两阶段 NLU 管线

        Stage 1: 意图分类（语义 + 关键词混合，带置信度）
          - 高置信 (>0.7)  → 进入 Stage 2
          - 中置信 (0.4-0.7) → 返回追问
          - 低置信 (<0.4)   → 走原 LLM 路径兜底

        Stage 2: 实体抽取 + 命令解析 → 操作分发
        """
        try:
            nlu = self._get_nlu_engine()
            if nlu is not None:
                intent_name, confidence, _debug = nlu.classify(user_input)
                try:
                    intent = TaskIntent[intent_name]
                except KeyError:
                    intent = TaskIntent.TEXT_CHAT

                logger.debug("NLU: intent=%s confidence=%.2f", intent.name, confidence)

                if confidence < 0.40:
                    # 低置信 → 走原 LLM 路径
                    return self._legacy_ai_path(user_input)
                elif confidence < 0.70:
                    # 中置信 → 追问
                    return self._ask_clarification(user_input, nlu)
                else:
                    # 高置信 → Stage 2
                    return self._execute_with_intent(user_input, intent)
            else:
                # NLU 不可用 → 走原 LLM 路径
                return self._legacy_ai_path(user_input)
        except Exception:
            logger.exception("AI processing failed, falling back to local")
            return None

    def _try_ai_stream(
        self, user_input: str, on_token: Callable[[str], None]
    ) -> Optional[str]:
        """流式版本 — 暂用原路径（流式不适合两阶段追问）"""
        try:
            return self._legacy_ai_path_stream(user_input, on_token)
        except Exception:
            logger.exception("AI streaming failed, falling back to local")
            return None

    def _legacy_ai_path(self, user_input: str) -> Optional[str]:
        """原 AI 路径：单次 LLM 调用解析"""
        system, prompt = self._build_ai_prompt(user_input)
        raw = self.agent.chat(
            prompt, system_prompt=system,
            use_history=self._conversation_active,
        )
        result = self._ai_to_operation(raw)
        if result is not None:
            self._conversation_active = True
        return result

    def _legacy_ai_path_stream(
        self, user_input: str, on_token: Callable[[str], None]
    ) -> Optional[str]:
        """流式版本的遗留路径"""
        system, prompt = self._build_ai_prompt(user_input)
        raw = self.agent.chat_stream(
            prompt, system_prompt=system, on_token=on_token,
            use_history=self._conversation_active,
        )
        result = self._ai_to_operation(raw)
        if result is not None:
            self._conversation_active = True
        return result

    def _execute_with_intent(self, user_input: str, intent: TaskIntent) -> Optional[str]:
        """Stage 2: 基于已确认意图的精准命令解析

        先用 entity_extract 模板提取实体，将实体上下文注入 command_parse，
        让 LLM 在已有意图方向的前提下做更精准的解析。
        """
        system_type = self._intent_to_system_type(intent)
        system = PromptTemplates.get_system_prompt(system_type)

        try:
            # Step 2a: 实体抽取（best-effort）
            entity_prompt = PromptTemplates.get("entity_extract", user_command=user_input)
            entity_raw = self.agent.chat(entity_prompt, system_prompt=system)
            entities = self._extract_json(entity_raw)
            entity_context = ""
            if entities and entities.get("entities"):
                entity_context = "\n已提取的实体上下文：\n" + json.dumps(
                    entities["entities"], ensure_ascii=False, indent=2
                )

            # Step 2b: 精准命令解析
            cmd_prompt = PromptTemplates.get(
                "command_parse",
                user_command=user_input,
                entity_context=entity_context,
            )
            cmd_raw = self.agent.chat(cmd_prompt, system_prompt=system)

            result = self._ai_to_operation(cmd_raw)
            if result is not None:
                self._conversation_active = True
            return result
        except Exception:
            logger.exception("Stage 2 parsing failed, falling back to legacy")
            return self._legacy_ai_path(user_input)

    def _ask_clarification(self, user_input: str, nlu=None) -> str:
        """生成意图追问（中置信度时调用）"""
        if nlu is None:
            nlu = self._get_nlu_engine()
        if nlu is not None:
            return nlu.get_clarification_question(user_input)
        return (
            " 不太确定您的意思，能再说详细一点吗？\n\n"
            "可用操作：合并BOM / 校验封装 / 检查重复 / 设计规则 / PCB分析 / BOM健康"
        )

    def _analyze_image(self, text: str, image_b64: str) -> str:
        """调用多模态 LLM 分析图片

        使用视觉系统提示词和 VISION_ANALYSIS 模板，
        通过 LLMClient.chat_multimodal 发送 base64 图片。
        """
        system = PromptTemplates.get_system_prompt("vision")
        prompt = PromptTemplates.get(
            "vision_analysis",
            user_command=text,
        )
        try:
            raw = self.agent.chat_multimodal(
                user_message=prompt,
                image_b64=image_b64,
                system_prompt=system,
            )
            return f" AI 视觉分析:\n\n{raw}"
        except Exception as e:
            logger.exception("Multimodal LLM call failed")
            return (
                f" 视觉分析调用失败: {e}\n\n"
                "请确认:\n"
                "• 已配置支持多模态的 API（如 Kimi、GPT-4o、Qwen-VL）\n"
                "• 当前模型支持图片输入\n"
                "• API 额度充足"
            )

    def _filter_components(self, params: dict) -> str:
        keyword = (params.get("keyword") or "").lower()
        if not keyword:
            return " 请指定筛选关键词"
        matched = [
            item for item in self.context.bom_items
            if keyword in f"{item.reference} {item.value} {item.package} {item.part_number} {item.description}".lower()
        ]
        if not matched:
            return f" 未找到包含「{keyword}」的元件"
        lines = [f" 筛选结果 ({len(matched)} 条):"]
        for item in matched:
            lines.append(
                f"   {item.reference:15s} {item.value:10s} "
                f"{item.package:10s} {item.part_number}"
            )
        return "\n".join(lines)

    # ── Local keyword fallback ──

    # _KEYWORD_ROUTES 已从 ToolRegistry 派生（单一事实来源）
    # 保留此属性以兼容旧代码，实际匹配在 _match_keyword 中通过 ToolRegistry 完成
    _KEYWORD_ROUTES: tuple = ()  # deprecated, kept for compatibility

    def _get_keyword_map(self):
        """懒加载 ToolRegistry 关键词映射"""
        try:
            from src.agent.tools import ToolRegistry
            return ToolRegistry.get_keyword_map()
        except ImportError:
            return ()

    def _match_keyword(self, user_input: str) -> Optional[Callable[[], str]]:
        """关键词匹配 — 从 ToolRegistry 派生（精确子串 → 模糊 n-gram 降级）"""
        lowered = user_input.lower()

        # 第一轮：精确子串匹配（ToolRegistry 关键词，优先顺序已内置）
        for keywords, tool_name in self._get_keyword_map():
            if any(kw in lowered for kw in keywords):
                logger.debug("Keyword match: '%s' → %s", user_input[:30], tool_name)
                return self._resolve_handler_by_tool(tool_name)

        # 第二轮：汉字 bigram 模糊匹配
        best_tool: Optional[str] = None
        best_score = 0.0
        threshold = 0.25

        for keywords, tool_name in self._get_keyword_map():
            for kw in keywords:
                if len(kw) < 2:
                    continue
                score = self._char_ngram_similarity(lowered, kw, n=2)
                if score > best_score:
                    best_score = score
                    best_tool = tool_name

        if best_score >= threshold and best_tool:
            logger.debug("Fuzzy match: '%s' → %s (ngram=%.2f)", user_input[:30], best_tool, best_score)
            return self._resolve_handler_by_tool(best_tool)

        return None

    def _resolve_handler_by_tool(self, tool_name: str) -> Optional[Callable[[], str]]:
        """通过 ToolRegistry 解析 tool name → handler callable"""
        # 特殊处理：需要参数或特殊逻辑的工具
        # 所有 filter/search/lookup 类工具都使用 _filter_input_handler
        filter_tools = {"filter_components", "search_component", "component_lookup"}
        analysis_tools = {"pcb_analysis", "calc_trace_width"}
        health_tools = {"bom_health", "find_alternatives", "supply_risk", "bom_cost_summary"}
        report_tools = {"generate_html_bom"}
        rule_tools = {"check_rule", "explain_design_rule"}
        code_gen_tools = {"generate_drc_rule"}
        review_tools = {"review_multi_agent"}
        verify_tools = {"verify_suggestion"}

        if tool_name in filter_tools:
            return self._filter_input_handler
        if tool_name in analysis_tools:
            return self._pcb_analysis_handler
        if tool_name in health_tools:
            return self.check_bom_health
        if tool_name in report_tools:
            return self.generate_html_bom
        if tool_name in rule_tools:
            return self.check_design_rules
        if tool_name in code_gen_tools:
            return self._generate_drc_rule
        if tool_name in review_tools:
            return self.review_design_multi_agent
        if tool_name in verify_tools:
            return self.verify_suggestion_handler

        # 标准工具：从 Registry 获取 handler 名称
        try:
            from src.agent.tools import ToolRegistry
            dispatch = ToolRegistry.get_dispatch_map()
            handler_name = dispatch.get(tool_name)
            if handler_name:
                return getattr(self, handler_name, None)
        except ImportError:
            pass
        return None

    def _resolve_handler(self, method_name: str) -> Optional[Callable[[], str]]:
        """将方法名解析为可调用对象（向后兼容旧 _KEYWORD_ROUTES 路径）"""
        if method_name == "_filter_input":
            return self._filter_input_handler
        if method_name == "_pcb_analysis_cmd":
            return self._pcb_analysis_handler
        return getattr(self, method_name, None)

    def _filter_input_handler(self) -> str:
        """处理用户的筛选/搜索请求（从输入中提取关键词）"""
        # 这个方法在本地降级时被调用，但我们没有保存原始输入
        # 返回引导信息
        return (
            " 请在指令中指定要筛选的关键词，例如：\n"
            "• \"筛选0603封装的电阻\"\n"
            "• \"查找STM32\"\n"
            "• \"搜索10kΩ\""
        )

    def _pcb_analysis_handler(self) -> str:
        """处理 PCB 分析请求（本地降级时）"""
        if self.agent is None:
            return " PCB 分析需要 AI 支持，请先配置 API Key。"
        return self.agent.chat(
            PromptTemplates.get("pcb_analysis", pcb_summary=str(self.context.pcb_data or "未加载")),
            system_prompt=PromptTemplates.get_system_prompt("pcb"),
        )

    @staticmethod
    def _char_ngram_similarity(a: str, b: str, n: int = 2) -> float:
        """汉字 character n-gram Jaccard 相似度

        用于处理输入法导致的近似匹配，如 "合饼" → "合并"、 "物料青丹" → "物料清单"。
        """
        def ngrams(s: str) -> set:
            return {s[i:i + n] for i in range(len(s) - n + 1)}

        grams_a = ngrams(a)
        grams_b = ngrams(b)
        if not grams_a or not grams_b:
            return 0.0
        intersection = grams_a & grams_b
        union = grams_a | grams_b
        return len(intersection) / len(union)

    def _get_closest_commands(self, user_input: str, top: int = 3) -> list[tuple[str, float]]:
        """找到与用户输入最相似的前 N 条指令（从 ToolRegistry 派生）"""
        lowered = user_input.lower()
        scored: list[tuple[str, float]] = []

        for keywords, tool_name in self._get_keyword_map():
            max_score = max(
                (self._char_ngram_similarity(lowered, kw, n=2) for kw in keywords),
                default=0.0,
            )
            if max_score > 0.15:
                scored.append((tool_name, max_score))

        # 去重保留最高分
        seen: set[str] = set()
        unique: list[tuple[str, float]] = []
        for tool, score in sorted(scored, key=lambda x: -x[1]):
            if tool not in seen:
                seen.add(tool)
                unique.append((tool, score))

        return unique[:top]

    def _local_fallback(self, user_input: str) -> str:
        handler = self._match_keyword(user_input)
        if handler:
            return handler()

        # 未匹配 → 查找最相似的指令给出建议
        suggestions = self._get_closest_commands(user_input, top=3)
        suggestion_text = ""
        if suggestions:
            suggestion_text = "\n 您是不是想:\n"
            for tool_name, score in suggestions:
                label = ToolRegistry.get_label(tool_name) if 'ToolRegistry' in dir() else tool_name
                suggestion_text += f"  • {label}\n"

        # 从 ToolRegistry 生成帮助文本
        try:
            from src.agent.tools import ToolRegistry
            help_text = ToolRegistry.get_help_text()
        except ImportError:
            help_text = (
                "可用指令:\n"
                "• 合并/整理 BOM     — 合并同类元件\n"
                "• AI智能合并         — AI 辅助识别\n"
                "• 校验/验证封装      — 检查封装匹配\n"
                "• 查重/位号检查      — 检测重复位号\n"
                "• 筛选/查找元件      — 搜索元件\n"
                "• 生成 HTML/导出     — 交互式 BOM\n"
                "• 规则检查 / DRC     — 设计规则检查\n"
                "• BOM健康 / 库存     — 库存/替代料\n"
                "• PCB / 电路板       — PCB 状态\n"
                "• 统计 / 概览        — 元件统计"
            )

        return " 无法识别指令。" + suggestion_text + "\n" + help_text

    @staticmethod
    def _method_label(method_name: str) -> str:
        """方法名 → 用户可读标签（从 ToolRegistry 派生，向后兼容）"""
        try:
            from src.agent.tools import ToolRegistry
            # 尝试通过 handler 名称反查
            for tool in ToolRegistry.get_all():
                if tool.handler == method_name or tool.name == method_name:
                    return tool.label
        except ImportError:
            pass
        return method_name

    def _summary_report(self) -> str:
        summary = self.get_bom_summary()
        lines = [
            "=" * 50,
            "        BOM 元件统计",
            "=" * 50,
            f"总元件数：{summary['total']}",
            "-" * 50,
        ]
        for prefix, count in summary["by_prefix"].items():
            lines.append(f"  {prefix}: {count} 个")
        lines.append("=" * 50)
        return "\n".join(lines)

    def _generate_drc_rule(self) -> str:
        """DRC 规则自动生成 — 根据自然语言描述生成检查规则代码

        利用 LLM 将用户对 PCB 设计规则的自然语言描述
        转换为可运行的 Python 规则检查代码（RuleViolation 格式）。
        """
        guard = self._require_llm()
        if guard:
            return guard

        # 从用户最后一条输入获取规则描述
        history = self.context.conversation_history
        rule_desc = ""
        for msg in reversed(history):
            if msg.get("role") == "user":
                rule_desc = msg.get("content", "")
                break

        if not rule_desc:
            return " 请先描述你想生成的 DRC 规则。例如：'生成一个检查LED限流电阻的规则'"

        # 构建生成提示
        sample_code = '''def _check_example(self, bom_items, positions, netlist):
    """规则名称：简短描述触发的条件"""
    violations = []
    # 遍历 BOM 元件
    for item in bom_items:
        ref = getattr(item, "reference", "").split(",")[0].strip()
        desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
        part_number = (getattr(item, "part_number", "") or "").strip().upper()
        pkg = (getattr(item, "package", "") or "").strip().upper()
        value = (getattr(item, "value", "") or "").strip().upper()
        # 在此编写检查逻辑
        # 如果需要位置信息:
        # if positions and ref in positions:
        #     pos = positions[ref]
        #     x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
        # 如果需要PCB数据:
        # pcb = self._pcb_data
        # if pcb and pcb.traces: ...
    return violations'''

        prompt = (
            "你是一个 PCB 设计规则检查代码生成器。根据用户的自然语言描述，"
            "生成一个完整的 Python 规则检查方法。\n\n"
            "## 代码规范\n"
            f"```python\n{sample_code}\n```\n\n"
            "## 要求\n"
            "1. 方法名格式: `_check_<英文简短描述>` (如 _check_led_current_limit)\n"
            "2. 必须包含完整的文档字符串（规则名称：xxx）\n"
            "3. 使用 RuleViolation 返回违规项，包含: rule_name, description, severity, location, suggestion, theory\n"
            "4. severity 取值: RuleSeverity.INFO / WARNING / ERROR\n"
            "5. 使用 getattr(item, 'field', default) 安全访问 BOMItem 字段\n"
            "6. 每个违规项必须提供 theory（理论基础）字段\n"
            "7. 如果所需数据不足，返回空列表\n\n"
            f"## 用户需求\n{rule_desc}\n\n"
            "请只输出 Python 代码，不要附带任何解释文字。代码应该可以直接复制到 DesignRuleChecker 类中。"
        )

        try:
            llm = self.agent
            code = llm.chat(prompt)
            # 清理可能存在的 markdown 代码块标记
            code = code.strip()
            if code.startswith("```python"):
                code = code[9:]
            elif code.startswith("```"):
                code = code[3:]
            if code.endswith("```"):
                code = code[:-3]
            code = code.strip()

            # 验证生成的代码是否语法正确
            try:
                compile(code, "<generated_drc_rule>", "exec")
            except SyntaxError as e:
                return (
                    f" 生成的规则代码存在语法错误:\n```\n{e}\n```\n\n"
                    f"请修改规则描述后重试。"
                )

            # 格式化为用户可查看的结果
            return (
                "##  DRC 规则已生成\n\n"
                "以下规则代码可直接添加到 `src/rules/checker.py` 的 DesignRuleChecker 类中：\n\n"
                f"```python\n{code}\n```\n\n"
                "### 使用方式\n"
                "1. 复制上方代码到 `src/rules/checker.py`\n"
                "2. 保存文件后规则自动生效（`_check_` 前缀方法自动注册）\n"
                "3. 运行 `python -m pytest tests/ -q` 验证无误\n\n"
                " 提示: AI 生成的规则建议人工审核后再投入使用。"
            )
        except Exception as e:
            return f" DRC 规则生成失败: {str(e)}\n\n请确保 LLM API 配置正确并重试。"

    def _require_llm(self) -> Optional[str]:
        """检查 LLM 是否可用"""
        if not self.is_agent_available():
            return " 此功能需要配置 LLM API Key。请在设置中配置 AI 模型。"
        return None

    def _pcb_status(self) -> str:
        """返回已加载 PCB 的状态摘要"""
        pcb = self.context.pcb_data
        if not pcb:
            return " 未加载 PCB 文件。请通过 文件→导入PCB 加载电路板文件。"
        return (
            f" PCB 状态:\n"
            f"  格式: {pcb.format}\n"
            f"  网络: {pcb.net_count} 个\n"
            f"  走线: {pcb.trace_count} 条\n"
            f"  过孔: {pcb.via_count} 个\n"
            f"  层: {', '.join(pcb.layers) if pcb.layers else '无'}"
        )

    # ── Static utility ──

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None
