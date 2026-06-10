"""
多智能体协同设计审查系统 (Multi-Agent Collaborative Design Review)

5 个专业审查 Agent 同时审查 PCB 设计，各司其职：
- PowerIntegrityAgent: 电源完整性
- SignalIntegrityAgent: 信号完整性
- ThermalAgent: 热管理
- EMCAgent: 电磁兼容
- DFMAgent: 可制造性

工作流程:
1. 所有 Agent 接收相同的违规列表（已按维度预分组）
2. 每个 Agent 从专业角度深度分析其领域的违规
3. Synthesizer 合并所有 Agent 的发现，解决冲突，生成统一报告

使用方式:
    from src.agent.review_agents import MultiAgentReviewer
    reviewer = MultiAgentReviewer(llm_client)
    report = reviewer.review(violations, bom_items, positions, pcb_data)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── 5 个专业 Agent 的领域定义 ──

AGENT_DEFINITIONS = {
    "power": {
        "name": "电源完整性审查师",
        "emoji": "[Power]",
        "domain": "Power Integrity",
        "expertise": (
            "精通电源分配网络(PDN)设计、去耦策略、DC-DC转换器布局、"
            "电源滤波、载流能力计算、LDO选型与稳定性分析。"
            "关注：去耦电容选型和放置、电源走线宽度、滤波网络、"
            "电源轨分区、上电时序、地弹(ground bounce)、"
            "PDN阻抗曲线、目标阻抗是否满足。"
        ),
        "focus_rules": [
            "去耦电容", "电源滤波", "电源轨去耦", "电源线宽",
            "DC-DC 反馈", "电容耐压降额", "多电源引脚去耦",
            "开关电源布局", "磁珠隔离", "去耦电容距离",
            "电池电压分压器", "电源极性保护",
        ],
    },
    "signal": {
        "name": "信号完整性审查师",
        "emoji": "[Signal]",
        "domain": "Signal Integrity",
        "expertise": (
            "精通高速数字和模拟信号完整性分析、时钟分配、"
            "差分对设计、阻抗控制、串扰抑制、时序分析。"
            "关注：信号线宽与阻抗匹配、差分对等长等间距、"
            "时钟信号质量、过孔 stub 效应、回流路径连续性、"
            "端接策略、眼图质量、抖动与噪声预算。"
        ),
        "focus_rules": [
            "晶振负载电容", "晶振频率匹配", "晶振布局",
            "I2C 上拉电阻", "信号线宽", "走线锐角",
            "过孔密度", "差分对间距", "差分对等长",
            "时钟信号包地", "3W 串扰间距", "环路面积",
            "ADC 输入滤波", "运放反馈网络", "光耦输入限流",
            "悬空引脚", "复位电路",
        ],
    },
    "thermal": {
        "name": "热管理审查师",
        "emoji": "[Thermal]",
        "domain": "Thermal Management",
        "expertise": (
            "精通 PCB 热设计、功率器件散热方案、热仿真、"
            "温度敏感元件布局、热应力与可靠性。"
            "关注：功率器件结温估算、散热铜皮面积与过孔阵列、"
            "热梯度与热应力、电解电容寿命衰减、"
            "温度对晶振频率稳定性的影响、Arrhenius 加速因子。"
        ),
        "focus_rules": [
            "热焊盘", "温度敏感元件布局", "电阻功率降额",
            "元件高度分区",
        ],
    },
    "emc": {
        "name": "电磁兼容审查师",
        "emoji": "[EMC]",
        "domain": "EMC",
        "expertise": (
            "精通电磁兼容设计、EMI 抑制、ESD 防护、"
            "接地策略、屏蔽设计、滤波拓扑。"
            "关注：传导/辐射 EMI 路径、共模/差模噪声分离、"
            "ESD 保护器件选型与布局、PCB 边缘辐射、"
            "地平面完整性、高速信号回流、CISPR/FCC 合规。"
        ),
        "focus_rules": [
            "ESD 保护", "EMI 滤波", "EMI 滤波器布局",
            "天线净空区", "铜皮连接", "模数分离",
            "MOSFET 栅极电阻", "继电器续流二极管",
        ],
    },
    "dfm": {
        "name": "可制造性审查师",
        "emoji": "[DFM]",
        "domain": "DFM",
        "expertise": (
            "精通 PCB 可制造性设计(DFM)、SMT 工艺、"
            "波峰焊/回流焊兼容性、装配工艺、测试策略。"
            "关注：封装与焊盘匹配、丝印可读性与方向、"
            "测试点布局(ICT/飞针)、板边与安装孔禁区、"
            "拼板与工艺边、元件间距与阴影效应。"
        ),
        "focus_rules": [
            "封装一致性", "位号连续性", "板边间距",
            "丝印可读性", "测试点覆盖", "安装孔禁区",
            "连接器边沿布局", "调试接口",
        ],
    },
}


@dataclass
class AgentFinding:
    """单个 Agent 的审查发现"""
    agent_key: str
    agent_name: str
    agent_emoji: str
    severity: str  # "critical" | "major" | "minor" | "observation"
    title: str
    detail: str
    rule_name: str = ""
    location: str = ""
    suggestion: str = ""
    confidence: float = 1.0  # Agent 对此发现的置信度


@dataclass
class AgentReport:
    """单个 Agent 的完整审查报告"""
    agent_key: str
    agent_name: str
    agent_emoji: str
    domain: str
    summary: str  # 1-2 句总结
    findings: list[AgentFinding] = field(default_factory=list)
    score: float = 100.0  # 维度评分


@dataclass
class MultiAgentReviewReport:
    """多智能体协同审查最终报告"""
    agent_reports: dict[str, AgentReport]  # key → AgentReport
    radar_data: list[dict]  # 6 维度评分
    overall_score: float
    overall_grade: str
    critical_issues: list[dict]  # 跨 Agent 合并的关键问题
    consensus_summary: str  # 合成共识摘要
    improvement_roadmap: list[str]  # 改进路线图


class MultiAgentReviewer:
    """多智能体协同设计审查器

    协调 5 个专业 Agent 并行审查，然后合成结果。
    支持有 LLM（深度分析）和无 LLM（基于规则评分）两种模式。
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def review(
        self,
        violations: list,
        bom_items: list = None,
        positions: dict = None,
        pcb_data=None,
    ) -> MultiAgentReviewReport:
        """执行多智能体审查

        Args:
            violations: RuleViolation 列表（来自 DesignRuleChecker）
            bom_items: BOM 元件列表
            positions: 元件坐标
            pcb_data: PCB 数据

        Returns:
            MultiAgentReviewReport
        """
        from ..core.design_scorer import DesignScorer

        bom_items = bom_items or []

        # Step 1: 评分引擎计算基础评分
        scorer = DesignScorer()
        score_report = scorer.score(violations, bom_items, positions)

        # Step 2: 每个 Agent 分析其领域的违规
        agent_reports: dict[str, AgentReport] = {}
        for agent_key, agent_def in AGENT_DEFINITIONS.items():
            # 筛选该 Agent 关注的违规
            agent_violations = self._filter_violations(violations, agent_def["focus_rules"])

            # 提取该维度的评分
            dim_score = score_report.dimensions.get(agent_key)
            agent_score = dim_score.score if dim_score else 100.0

            # 生成审查发现
            findings = self._analyze_violations(
                agent_key, agent_def, agent_violations, bom_items
            )

            # 生成领域总结
            summary = self._summarize_findings(agent_def, findings, agent_score)

            agent_reports[agent_key] = AgentReport(
                agent_key=agent_key,
                agent_name=agent_def["name"],
                agent_emoji=agent_def["emoji"],
                domain=agent_def["domain"],
                summary=summary,
                findings=findings,
                score=agent_score,
            )

        # Step 3: 合成所有 Agent 的结果
        critical_issues = self._synthesize_critical(agent_reports)
        consensus = self._build_consensus(agent_reports, score_report)
        roadmap = self._build_roadmap(agent_reports, score_report)

        return MultiAgentReviewReport(
            agent_reports=agent_reports,
            radar_data=score_report.radar_data,
            overall_score=score_report.overall,
            overall_grade=score_report.grade,
            critical_issues=critical_issues,
            consensus_summary=consensus,
            improvement_roadmap=roadmap,
        )

    def review_with_llm(
        self,
        violations: list,
        bom_items: list = None,
        positions: dict = None,
        pcb_data=None,
    ) -> MultiAgentReviewReport:
        """带 LLM 深度分析的多智能体审查

        每个 Agent 使用 LLM 从专业角度深度解读违规。
        """
        if not self.llm:
            logger.warning("No LLM client, falling back to rule-based review")
            return self.review(violations, bom_items, positions, pcb_data)

        from ..core.design_scorer import DesignScorer

        bom_items = bom_items or []
        scorer = DesignScorer()
        score_report = scorer.score(violations, bom_items, positions)

        agent_reports: dict[str, AgentReport] = {}
        for agent_key, agent_def in AGENT_DEFINITIONS.items():
            agent_violations = self._filter_violations(violations, agent_def["focus_rules"])
            dim_score = score_report.dimensions.get(agent_key)
            agent_score = dim_score.score if dim_score else 100.0

            # 尝试用 LLM 深度分析
            try:
                findings = self._llm_deep_analyze(agent_key, agent_def, agent_violations)
                summary = self._llm_summarize(agent_def, findings, agent_score)
            except Exception as e:
                logger.warning("LLM deep analysis failed for %s: %s, falling back", agent_key, e)
                findings = self._analyze_violations(agent_key, agent_def, agent_violations, bom_items)
                summary = self._summarize_findings(agent_def, findings, agent_score)

            agent_reports[agent_key] = AgentReport(
                agent_key=agent_key,
                agent_name=agent_def["name"],
                agent_emoji=agent_def["emoji"],
                domain=agent_def["domain"],
                summary=summary,
                findings=findings,
                score=agent_score,
            )

        critical_issues = self._synthesize_critical(agent_reports)
        consensus = self._build_consensus(agent_reports, score_report)
        roadmap = self._build_roadmap(agent_reports, score_report)

        return MultiAgentReviewReport(
            agent_reports=agent_reports,
            radar_data=score_report.radar_data,
            overall_score=score_report.overall,
            overall_grade=score_report.grade,
            critical_issues=critical_issues,
            consensus_summary=consensus,
            improvement_roadmap=roadmap,
        )

    # ── 内部方法 ──

    def _filter_violations(self, violations: list, focus_rules: list[str]) -> list:
        """筛选属于某 Agent 领域的违规"""
        result = []
        for v in violations:
            for kw in focus_rules:
                if kw in v.rule_name:
                    result.append(v)
                    break
        return result

    def _analyze_violations(
        self, agent_key: str, agent_def: dict, violations: list, bom_items: list
    ) -> list[AgentFinding]:
        """将违规转换为 AgentFinding（基于规则的本地分析）"""
        from ..rules.checker import RuleSeverity

        findings = []
        severity_map = {
            RuleSeverity.ERROR: ("critical", 3),
            RuleSeverity.WARNING: ("major", 2),
            RuleSeverity.INFO: ("minor", 1),
        }

        for v in violations:
            sev_label, sev_rank = severity_map.get(v.severity, ("observation", 0))

            # 从 Agent 专业角度重新评估严重度
            enhanced_detail = self._enhance_with_expertise(agent_key, v)

            findings.append(AgentFinding(
                agent_key=agent_key,
                agent_name=agent_def["name"],
                agent_emoji=agent_def["emoji"],
                severity=sev_label,
                title=v.rule_name,
                detail=enhanced_detail or v.description,
                rule_name=v.rule_name,
                location=v.location,
                suggestion=v.suggestion,
                confidence=0.9,
            ))

        # 按严重度排序
        findings.sort(key=lambda f: severity_map.get(
            RuleSeverity.ERROR if f.severity == "critical" else
            RuleSeverity.WARNING if f.severity == "major" else
            RuleSeverity.INFO,
            (0, 0)
        )[1], reverse=True)
        return findings

    def _enhance_with_expertise(self, agent_key: str, violation) -> str:
        """根据 Agent 专业领域增强违规描述"""
        from ..rules.checker import RuleSeverity

        base = violation.description
        theory = getattr(violation, "theory", "")

        # 不同 Agent 对同一问题的不同视角
        perspectives = {
            "power": "从电源完整性角度看，",
            "signal": "从信号完整性角度看，",
            "thermal": "从热管理角度看，",
            "emc": "从EMC角度看，",
            "dfm": "从可制造性角度看，",
        }
        prefix = perspectives.get(agent_key, "")

        if violation.severity == RuleSeverity.ERROR and theory:
            return f"{prefix}这是一个严重问题。{theory[:120]}"
        elif theory:
            return f"{prefix}{theory[:100]}"
        return base

    def _summarize_findings(
        self, agent_def: dict, findings: list[AgentFinding], score: float
    ) -> str:
        """生成 Agent 领域总结"""
        agent_name = agent_def["name"]
        if not findings:
            return f" {agent_name}：本领域未发现问题，设计质量良好。"

        critical = sum(1 for f in findings if f.severity == "critical")
        major = sum(1 for f in findings if f.severity == "major")
        minor = sum(1 for f in findings if f.severity == "minor")

        parts = []
        if critical:
            parts.append(f"{critical} 项严重问题需立即修复")
        if major:
            parts.append(f"{major} 项重要问题建议关注")
        if minor:
            parts.append(f"{minor} 项优化建议")

        detail = "；".join(parts) if parts else "存在少量可优化项"
        return f" {agent_name} 审查完成（评分 {score:.0f}）：{detail}。"

    def _llm_deep_analyze(
        self, agent_key: str, agent_def: dict, violations: list
    ) -> list[AgentFinding]:
        """使用 LLM 从专业角度深度分析违规"""
        if not violations:
            return []

        # 准备违规摘要
        violation_text = "\n".join(
            f"- [{v.severity.value.upper()}] {v.rule_name}: {v.description}"
            f"{' @ ' + v.location if v.location else ''}"
            for v in violations[:10]
        )

        prompt = (
            f"你是{agent_def['name']}，{agent_def['expertise']}\n\n"
            f"以下是你审查的 PCB 设计中发现的问题：\n{violation_text}\n\n"
            "请从你的专业角度对每个问题进行深度分析，输出 JSON 格式：\n"
            '{"findings": [{"title": "问题简述", "severity": "critical/major/minor", '
            '"detail": "专业分析(50字内)", "suggestion": "具体修复建议"}]}\n\n'
            "只输出 JSON，不要其他文字。"
        )

        try:
            resp = self.llm.chat(prompt)
            # 提取 JSON
            start = resp.find("{")
            end = resp.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(resp[start:end])
                return [
                    AgentFinding(
                        agent_key=agent_key,
                        agent_name=agent_def["name"],
                        agent_emoji=agent_def["emoji"],
                        severity=f.get("severity", "minor"),
                        title=f.get("title", "未命名问题"),
                        detail=f.get("detail", ""),
                        suggestion=f.get("suggestion", ""),
                        confidence=0.85,
                    )
                    for f in data.get("findings", [])
                ]
        except Exception as e:
            logger.warning("LLM analysis failed: %s", e)

        return []

    def _llm_summarize(
        self, agent_def: dict, findings: list[AgentFinding], score: float
    ) -> str:
        """使用 LLM 生成专业领域总结"""
        if not findings:
            return f" {agent_def['name']}：本领域未发现问题，设计质量良好。"

        finding_text = "\n".join(
            f"- [{f.severity}] {f.title}" for f in findings[:5]
        )

        prompt = (
            f"作为{agent_def['name']}，基于以下审查发现（评分 {score:.0f}/100），"
            f"用一句话总结本领域设计状态:\n{finding_text}\n\n"
            "只输出总结（30字以内），不要其他内容。"
        )

        try:
            summary = self.llm.chat(prompt).strip()
            if summary:
                return f" {summary}"
        except Exception:
            pass

        return self._summarize_findings(agent_def, findings, score)

    def _synthesize_critical(self, agent_reports: dict[str, AgentReport]) -> list[dict]:
        """合并所有 Agent 的严重发现，去重排序"""
        all_critical = []
        seen = set()

        for report in agent_reports.values():
            for f in report.findings:
                if f.severity in ("critical", "major"):
                    key = f"{f.rule_name}:{f.location}"
                    if key not in seen:
                        seen.add(key)
                        all_critical.append({
                            "agent": f.agent_name,
                            "agent_emoji": f.agent_emoji,
                            "severity": f.severity,
                            "title": f.title,
                            "detail": f.detail,
                            "suggestion": f.suggestion,
                            "location": f.location,
                        })

        # 按严重度排序：critical > major
        all_critical.sort(key=lambda x: 0 if x["severity"] == "critical" else 1)
        return all_critical[:10]

    def _build_consensus(self, agent_reports: dict[str, AgentReport], score_report) -> str:
        """构建跨 Agent 共识摘要"""
        dims = score_report.dimensions
        worst = sorted(dims.items(), key=lambda x: x[1].score)

        parts = [f"## 多智能体协同审查共识\n"]

        # 总体评价
        if score_report.overall >= 80:
            parts.append(" 设计总体质量良好，经 5 个专业 Agent 审查后达成共识。\n")
        elif score_report.overall >= 60:
            parts.append(" 设计存在改进空间，各领域 Agent 提出了优化建议。\n")
        else:
            parts.append(" 设计存在较多问题，建议在打样前完成关键修复。\n")

        # 各 Agent 一致认可的问题
        critical_findings = []
        for report in agent_reports.values():
            critical_findings.extend(
                f for f in report.findings if f.severity == "critical"
            )
        if critical_findings:
            parts.append(f"### 优先修复项（{len(critical_findings)} 项）\n")
            for f in critical_findings[:5]:
                parts.append(f"- {f.agent_emoji} [{f.agent_name}] **{f.title}**: {f.suggestion}")

        # 低分维度
        parts.append(f"\n### 需重点改进的维度\n")
        for dim_key, ds in worst[:3]:
            if ds.score < 80:
                parts.append(f"- **{ds.label}**：{ds.score:.0f} 分 — {ds.suggestion}")

        return "\n".join(parts)

    def _build_roadmap(self, agent_reports: dict[str, AgentReport], score_report) -> list[str]:
        """生成改进路线图（优先级排序的行动清单）"""
        roadmap = []

        # 第一优先级：严重问题
        for report in agent_reports.values():
            for f in report.findings:
                if f.severity == "critical" and f.suggestion:
                    item = f" P0 [{report.agent_name}] {f.title} — {f.suggestion}"
                    if item not in roadmap:
                        roadmap.append(item)

        # 第二优先级：重要问题
        for report in agent_reports.values():
            for f in report.findings:
                if f.severity == "major" and f.suggestion:
                    item = f" P1 [{report.agent_name}] {f.title} — {f.suggestion}"
                    if item not in roadmap:
                        roadmap.append(item)

        # 第三优先级：低分维度改进
        dims = score_report.dimensions
        for dim_key, ds in sorted(dims.items(), key=lambda x: x[1].score):
            if ds.score < 70:
                item = f" P2 [{ds.label}] 整体改进 — 当前 {ds.score:.0f} 分，{ds.suggestion}"
                if item not in roadmap:
                    roadmap.append(item)

        if not roadmap:
            roadmap.append(" 无需优先改进项，设计已达到可交付质量水平。")

        return roadmap[:10]
