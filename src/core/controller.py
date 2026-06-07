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

    def __init__(self, api_key: Optional[str] = None):
        effective_key = api_key or config.llm.api_key
        self.agent = LLMClient(
            api_key=effective_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
            provider=config.llm.provider,
        ) if _is_key_usable(effective_key) else None
        self.router = LLMRouter.from_config(effective_key) if _is_key_usable(effective_key) else None
        self.parser = BOMParser()
        self.eda = LCEDAAdapter()
        self.context = CommandContext()
        self._conversation_active = False
        self._active_assistant: Optional[str] = None  # 当前助手 ID

    def reconfigure_llm(self, provider: str, api_key: str, base_url: str, model: str):
        """热重载 LLM 客户端 — 用户通过设置面板修改配置后调用。"""
        if _is_key_usable(api_key):
            self.agent = LLMClient(
                api_key=api_key,
                base_url=base_url or None,
                model=model or None,
                provider=provider,
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
        return n, f"✅ 已加载 BOM: {name}\n共 {n} 条物料记录"

    def load_positions(self, file_path: str) -> tuple[int, str]:
        """Parse a Pick & Place file, return (count, message)."""
        self.context.positions = self.eda.get_positions(file_path)
        name = Path(file_path).name
        n = len(self.context.positions)
        logger.info("Positions loaded: %s (%d entries)", name, n)
        return n, f"✅ 已加载坐标: {name}\n共 {n} 个位号坐标"

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
            f"✅ 已加载 PCB: {name}\n"
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
            return self.merge_bom() + "\n\n⚠️ AI 未配置，仅执行了规则合并"

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
            report += f"\n\n🤖 AI 额外识别了 {ai_count} 组合并"
        else:
            report += "\n\n🤖 AI 未发现额外合并机会"
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
        return f"🌐 HTML BOM 已生成:\n{output_path}"

    def check_design_rules(self) -> str:
        checker = DesignRuleChecker()
        violations = checker.check_all(
            self.context.bom_items,
            self.context.positions,
            pcb_data=self.context.pcb_data,
        )
        return checker.get_report(violations)

    def check_bom_health(self) -> str:
        """BOM 健康检查 — 库存 / 生命周期 / 替代料 / 成本。"""
        if not self.context.has_data:
            return "⚠️ 请先导入 BOM 文件"
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
                return "🤔 " + question + "\n\n可选项：\n" + "\n".join(f"  • {o}" for o in options)
            return "🤔 " + question

        # 从 ToolRegistry 获取 handler 映射（带懒加载降级）
        dispatch = self._build_dispatch_map()
        handler = dispatch.get(operation)
        if handler:
            return handler()

        return (
            f"🤔 无法识别操作「{operation}」\n\n"
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
        handlers["load_pcb"] = lambda: "⚠️ 请通过 文件→导入PCB 加载电路板文件。"
        return handlers

    # ══════════════════════════════════════════════════
    #  Natural-language processing
    # ══════════════════════════════════════════════════

    def is_agent_available(self) -> bool:
        return self.agent is not None

    def _require_data(self) -> Optional[str]:
        if not self.context.has_data:
            return "⚠️ 请先导入 BOM 文件再输入指令。"
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
            return "⚠️ AI 调用失败，请检查网络连接和 API 配置。\n\n建议：\n- 检查 API Key 是否正确\n- 检查网络连接是否通畅\n- 检查 API 额度是否充足"

    def process_image_input(self, text: str, image_b64: str) -> str:
        """处理带图片的用户输入 — 调用多模态 LLM 分析

        不需要 BOM 预加载（图片分析独立于 BOM 数据）。
        """
        if not self.is_agent_available():
            return "⚠️ 图片分析需要配置 AI 模型。请在设置中配置支持多模态的 API（如 Kimi、GPT-4o、Qwen-VL）。"

        try:
            return self._analyze_image(text, image_b64)
        except Exception as e:
            logger.exception("Image analysis failed")
            return f"⚠️ 图片分析失败: {e}"

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
        return f"🤖 AI 理解: {explanation}\n\n{result}" if explanation else result

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
            "🤔 不太确定您的意思，能再说详细一点吗？\n\n"
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
            return f"🤖 AI 视觉分析:\n\n{raw}"
        except Exception as e:
            logger.exception("Multimodal LLM call failed")
            return (
                f"⚠️ 视觉分析调用失败: {e}\n\n"
                "请确认:\n"
                "• 已配置支持多模态的 API（如 Kimi、GPT-4o、Qwen-VL）\n"
                "• 当前模型支持图片输入\n"
                "• API 额度充足"
            )

    def _filter_components(self, params: dict) -> str:
        keyword = (params.get("keyword") or "").lower()
        if not keyword:
            return "🔍 请指定筛选关键词"
        matched = [
            item for item in self.context.bom_items
            if keyword in f"{item.reference} {item.value} {item.package} {item.part_number} {item.description}".lower()
        ]
        if not matched:
            return f"🔍 未找到包含「{keyword}」的元件"
        lines = [f"🔍 筛选结果 ({len(matched)} 条):"]
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
        if tool_name == "filter_components":
            return self._filter_input_handler
        if tool_name == "pcb_analysis":
            return self._pcb_analysis_handler

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
            "🔍 请在指令中指定要筛选的关键词，例如：\n"
            "• \"筛选0603封装的电阻\"\n"
            "• \"查找STM32\"\n"
            "• \"搜索10kΩ\""
        )

    def _pcb_analysis_handler(self) -> str:
        """处理 PCB 分析请求（本地降级时）"""
        if self.agent is None:
            return "⚠️ PCB 分析需要 AI 支持，请先配置 API Key。"
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
            suggestion_text = "\n💡 您是不是想:\n"
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

        return "🤔 无法识别指令。" + suggestion_text + "\n" + help_text

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

    def _pcb_status(self) -> str:
        """返回已加载 PCB 的状态摘要"""
        pcb = self.context.pcb_data
        if not pcb:
            return "⚠️ 未加载 PCB 文件。请通过 文件→导入PCB 加载电路板文件。"
        return (
            f"📐 PCB 状态:\n"
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
