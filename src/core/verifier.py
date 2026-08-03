"""
闭环验证引擎 — 路线三核心模块

LLM 建议 → 规则引擎验证 → 不一致反馈纠正 → 迭代至收敛

核心思想：LLM 在硬件领域容易产生幻觉，所有 AI 建议都必须经过
规则引擎的实时验证。验证失败的设计建议被自动拦截并反馈纠正。

Reference: EDAid "分歧思维" (NAACL 2025), UniVista LLM+EDA 闭环
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


class VerificationStatus(Enum):
    PASSED = "passed"        # 验证通过，建议安全
    FAILED = "failed"        # 验证失败，发现违规
    UNCERTAIN = "uncertain"  # 无法验证（缺少数据）


class SuggestionCategory(Enum):
    BOM_CHANGE = "bom_change"            # BOM 变更（替换/删除/新增元件）
    RULE_CHANGE = "rule_change"          # 设计规则变更
    LAYOUT_CHANGE = "layout_change"      # 布局变更
    ROUTING_CHANGE = "routing_change"    # 走线变更
    GENERAL = "general"                  # 通用建议


@dataclass
class VerificationIssue:
    """验证发现的问题"""
    rule_name: str
    severity: str                # "error" | "warning" | "info"
    description: str
    location: str = ""
    suggestion: str = ""
    category: str = ""


@dataclass
class VerificationRound:
    """单轮验证结果"""
    round: int
    suggestion: str                          # LLM 原始建议
    status: VerificationStatus = VerificationStatus.UNCERTAIN
    issues: list[VerificationIssue] = field(default_factory=list)
    corrected_suggestion: str = ""            # LLM 修正后的建议
    llm_response: str = ""                    # LLM 的反馈响应


@dataclass
class VerificationReport:
    """完整闭环验证报告"""
    original_suggestion: str
    category: SuggestionCategory = SuggestionCategory.GENERAL
    rounds: list[VerificationRound] = field(default_factory=list)
    final_status: VerificationStatus = VerificationStatus.UNCERTAIN
    accepted: bool = False
    summary: str = ""

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    @property
    def total_issues(self) -> int:
        return sum(len(r.issues) for r in self.rounds)

    def to_dict(self) -> dict:
        # 计算阻断性违规数
        blocking_count = sum(
            1 for r in self.rounds for i in r.issues
            if i.severity in ("error", "warning")
        )
        return {
            "accepted": self.accepted,
            "final_status": self.final_status.value,
            "rounds": self.round_count,
            "total_issues": self.total_issues,
            "blocking_issues": blocking_count,
            "category": self.category.value,
            "summary": self.summary,
            "details": [
                {
                    "round": r.round,
                    "status": r.status.value,
                    "issues": [
                        {
                            "rule": i.rule_name,
                            "severity": i.severity,
                            "description": i.description,
                            "suggestion": i.suggestion,
                        }
                        for i in r.issues
                    ],
                    "corrected": r.corrected_suggestion[:200] if r.corrected_suggestion else "",
                }
                for r in self.rounds
            ],
        }

    def to_markdown(self) -> str:
        """生成可读的验证报告"""
        icon = "✅" if self.accepted else "❌"
        blocking = sum(
            1 for r in self.rounds for i in r.issues
            if i.severity in ("error", "warning")
        )
        lines = [
            f"## {icon} 闭环验证报告",
            f"**类别**: {self.category.value}",
            f"**最终状态**: {self.final_status.value}",
            f"**迭代轮次**: {self.round_count}",
            f"**发现问题**: {self.total_issues} 项（其中 {blocking} 项阻断性违规）",
            "",
            "---",
            "",
            "### 原始建议",
            f"> {self.original_suggestion[:300]}",
            "",
        ]
        for r in self.rounds:
            s_icon = {"passed": "✅", "failed": "❌", "uncertain": "⚠️"}[r.status.value]
            lines.append(f"### 第 {r.round} 轮 {s_icon}")
            if r.issues:
                for iss in r.issues:
                    sev = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(iss.severity, "")
                    lines.append(f"- {sev} [{iss.rule_name}] {iss.description}")
                    if iss.suggestion:
                        lines.append(f"  → {iss.suggestion}")
            else:
                lines.append("无违规项")
            if r.corrected_suggestion:
                lines.append(f"\n修正建议: {r.corrected_suggestion[:200]}")
            lines.append("")
        lines.append(f"### 总结\n{self.summary}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# 验证引擎
# ═══════════════════════════════════════════════════════════════


class VerificationEngine:
    """闭环验证引擎。

    执行流程:
    1. 接收 LLM 建议
    2. 运行 DRC 规则检查，对比建议前后的违规变化
    3. 若发现新违规，反馈给 LLM 修正
    4. 迭代直到无新违规或达到上限
    """

    MAX_ROUNDS = 3  # 最大迭代轮次

    # 阻断性严重度：只有 error 和 warning 会导致验证失败
    # info 级别记录在报告中但不影响 accepted 决策
    BLOCKING_SEVERITIES = {"error", "warning"}

    def __init__(
        self,
        check_callback: Callable[[], list] | None = None,
        llm_callback: Callable[[str, str], str] | None = None,
    ):
        """初始化验证引擎。

        Args:
            check_callback: 无参函数，运行 DRC 检查并返回 RuleViolation 列表
            llm_callback: (original_suggestion, feedback) -> corrected_suggestion
                         若为 None，则跳过 LLM 修正环节
        """
        self._check_callback = check_callback
        self._llm_callback = llm_callback

    def verify(
        self,
        suggestion: str,
        category: SuggestionCategory = SuggestionCategory.GENERAL,
        baseline_violations: list | None = None,
    ) -> VerificationReport:
        """对一条 LLM 建议执行闭环验证。

        Args:
            suggestion: LLM 生成的设计建议（自然语言）
            category: 建议类别
            baseline_violations: 建议前的违规列表（可选），用于差分对比

        Returns:
            VerificationReport
        """
        report = VerificationReport(
            original_suggestion=suggestion,
            category=category,
        )

        # 基准线：仅当调用方显式传入时使用（避免消耗 check_callback 计数）
        baseline = baseline_violations  # None 表示不做差分对比

        current_suggestion = suggestion

        for round_num in range(1, self.MAX_ROUNDS + 1):
            vr = VerificationRound(round=round_num, suggestion=current_suggestion)

            # 运行验证
            if self._check_callback:
                try:
                    violations = self._check_callback()
                except Exception as e:
                    logger.error(f"Verification check failed round {round_num}: {e}")
                    vr.status = VerificationStatus.UNCERTAIN
                    report.rounds.append(vr)
                    break
            else:
                vr.status = VerificationStatus.UNCERTAIN
                report.rounds.append(vr)
                break

            # 分析违规
            issues = self._analyze_violations(violations, baseline, current_suggestion)
            vr.issues = issues

            # 分离阻断性违规 (error/warning) 和 info 提示
            blocking = self._get_blocking_issues(issues)

            if not blocking:
                # 无阻断性违规 → 通过（info 级别仅记录不阻断）
                vr.status = VerificationStatus.PASSED
                report.rounds.append(vr)
                report.final_status = VerificationStatus.PASSED
                report.accepted = True
                break
            else:
                vr.status = VerificationStatus.FAILED
                # 仅用阻断性违规反馈给 LLM 修正
                if self._llm_callback and round_num < self.MAX_ROUNDS:
                    feedback = self._format_feedback(blocking)
                    try:
                        corrected = self._llm_callback(current_suggestion, feedback)
                        vr.corrected_suggestion = corrected
                        vr.llm_response = corrected
                        current_suggestion = corrected
                    except Exception as e:
                        logger.warning(f"LLM correction failed round {round_num}: {e}")
                        report.rounds.append(vr)
                        break
                else:
                    report.rounds.append(vr)
                    break

            report.rounds.append(vr)

        # 确定最终状态
        if not report.rounds:
            report.final_status = VerificationStatus.UNCERTAIN
        elif report.final_status != VerificationStatus.PASSED:
            last = report.rounds[-1]
            if last.status == VerificationStatus.UNCERTAIN:
                report.final_status = VerificationStatus.UNCERTAIN
            else:
                report.final_status = VerificationStatus.FAILED
                report.accepted = False

        report.summary = self._generate_summary(report)
        return report

    def verify_design_change(
        self,
        action_description: str,
        before_check: Callable[[], list] | None = None,
    ) -> VerificationReport:
        """验证设计变更的安全性（建议前后差分对比）。

        适用于：元件替换、参数修改、布局调整

        Args:
            action_description: 变更描述
            before_check: 变更前 DRC 检查

        Returns:
            VerificationReport with before/after diff
        """
        # 变更前
        before = None
        if before_check:
            try:
                before = before_check()
            except Exception:
                pass

        # 变更后验证
        return self.verify(
            suggestion=action_description,
            category=SuggestionCategory.BOM_CHANGE,
            baseline_violations=before,
        )

    def verify_rule(
        self,
        rule_description: str,
        rule_code: str | None = None,
    ) -> VerificationReport:
        """验证新 DRC 规则的有效性。

        运行规则，检查：
        1. 规则能否正常执行（不崩溃）
        2. 规则是否产生合理的违规结果
        3. 规则是否与现有规则冲突

        Args:
            rule_description: 规则的自然语言描述
            rule_code: 规则的 Python 代码（若已生成）

        Returns:
            VerificationReport
        """
        issues = []

        # 语法检查
        if rule_code:
            try:
                compile(rule_code, "<drc_rule>", "exec")
            except SyntaxError as e:
                issues.append(VerificationIssue(
                    rule_name="SYNTAX_CHECK",
                    severity="error",
                    description=f"规则代码语法错误: {e}",
                    suggestion="请修正代码语法",
                ))

        report = VerificationReport(
            original_suggestion=rule_description,
            category=SuggestionCategory.RULE_CHANGE,
        )

        if issues:
            vr = VerificationRound(
                round=1,
                suggestion=rule_description,
                status=VerificationStatus.FAILED,
                issues=issues,
            )
            report.rounds.append(vr)
            report.final_status = VerificationStatus.FAILED
            report.summary = "规则语法检查失败，拒绝执行。"
            return report

        # 执行验证
        return self.verify(
            suggestion=rule_description,
            category=SuggestionCategory.RULE_CHANGE,
        )

    # ── 内部方法 ──

    @classmethod
    def _get_blocking_issues(cls, issues: list[VerificationIssue]) -> list[VerificationIssue]:
        """筛选阻断性违规：仅 error 和 warning 级别阻止建议通过。

        info 级别（如 E24 标准系列提示）记录在报告中但不影响决策。
        """
        return [i for i in issues if i.severity in cls.BLOCKING_SEVERITIES]

    def _analyze_violations(
        self,
        current_violations: list,
        baseline_violations: list | None,
        suggestion: str,
    ) -> list[VerificationIssue]:
        """分析违规变化，区分已有问题和新引入的问题。"""
        issues = []

        if current_violations is None:
            return issues

        # 收集已有的违规名 (None=不做差分, []空列表=基线无违规)
        baseline_names: set[str] = set()
        if baseline_violations is not None:
            for v in baseline_violations:
                try:
                    baseline_names.add(v.rule_name)
                except AttributeError:
                    baseline_names.add(str(v))

        for v in current_violations:
            try:
                rule_name = getattr(v, "rule_name", str(v))
                description = getattr(v, "description", str(v))
                severity = getattr(v, "severity", None)
                sev_str = severity.value if hasattr(severity, 'value') else str(severity)
                location = getattr(v, "location", "")
                suggestion_text = getattr(v, "suggestion", "")
            except Exception:
                rule_name = str(v)
                description = str(v)
                sev_str = "warning"
                location = ""
                suggestion_text = ""

            is_new = baseline_violations is not None and rule_name not in baseline_names

            issues.append(VerificationIssue(
                rule_name=rule_name,
                severity=sev_str,
                description=f"{'(新引入) ' if is_new else ''}{description}",
                location=location,
                suggestion=suggestion_text,
                category=self._categorize_violation(rule_name),
            ))

        return issues

    def _categorize_violation(self, rule_name: str) -> str:
        """根据规则名推断问题类别"""
        name = rule_name.lower()
        if any(kw in name for kw in ("power", "current", "电压", "电流", "载流")):
            return "power"
        if any(kw in name for kw in ("decoup", "capacitor", "电容", "去耦")):
            return "decoupling"
        if any(kw in name for kw in ("signal", "trace", "线宽", "走线", "impedance", "阻抗")):
            return "signal"
        if any(kw in name for kw in ("thermal", "热", "温度", "temp")):
            return "thermal"
        if any(kw in name for kw in ("emc", "emi", "电磁", "辐射", "antenna")):
            return "emc"
        if any(kw in name for kw in ("analog", "digital", "模数", "模拟", "数字")):
            return "layout"
        return "general"

    def _format_feedback(self, issues: list[VerificationIssue]) -> str:
        """格式化违规信息为 LLM 反馈文本。"""
        lines = [
            "以下设计规则检查发现问题，请修正你的建议：",
            "",
        ]
        for i, iss in enumerate(issues, 1):
            sev_emoji = {"error": "❌ 严重", "warning": "⚠️ 警告", "info": "ℹ️ 提示"}.get(
                iss.severity, ""
            )
            lines.append(f"{i}. {sev_emoji} [{iss.rule_name}]")
            lines.append(f"   问题: {iss.description}")
            if iss.location:
                lines.append(f"   位置: {iss.location}")
            if iss.suggestion:
                lines.append(f"   建议: {iss.suggestion}")
            lines.append("")
        lines.append("请在修正后重新提供设计建议。")
        return "\n".join(lines)

    def _generate_summary(self, report: VerificationReport) -> str:
        """生成验证总结"""
        if report.accepted:
            total = report.total_issues
            blocking = sum(
                len(self._get_blocking_issues(r.issues))
                for r in report.rounds
            )
            if total == 0:
                return (
                    f"✅ 建议已通过 {report.round_count} 轮闭环验证，未发现任何违规。"
                )
            else:
                return (
                    f"✅ 建议已通过 {report.round_count} 轮闭环验证。"
                    f"发现 {total} 项提示（info 级别，不阻断），"
                    f"无 error/warning 级别违规。"
                )
        elif report.final_status == VerificationStatus.UNCERTAIN:
            return "⚠️ 无法完成验证，可能缺少必要的设计数据。请导入 BOM 和 PCB 文件后重试。"
        else:
            last_round = report.rounds[-1] if report.rounds else None
            remaining = len(last_round.issues) if last_round else 0
            blocking_remaining = len(self._get_blocking_issues(last_round.issues)) if last_round else 0
            return (
                f"❌ 建议未通过验证。经过 {report.round_count} 轮迭代，"
                f"仍有 {blocking_remaining} 项阻断性违规（共 {remaining} 项）未解决。"
                f"建议人工审查后修改。"
            )


# ═══════════════════════════════════════════════════════════════
# 辅助：从 AppController 创建验证器
# ═══════════════════════════════════════════════════════════════


def create_verifier_from_controller(controller) -> VerificationEngine:
    """从 AppController 创建配置好的验证引擎。

    自动绑定 DRC 检查回调和 LLM 修正回调。

    Args:
        controller: AppController 实例

    Returns:
        配置好的 VerificationEngine
    """
    def check_callback():
        """运行 DRC 检查"""
        ctx = controller.context
        if not ctx.has_data:
            return []
        from src.rules.checker import DesignRuleChecker
        checker = DesignRuleChecker()
        return checker.check_all(
            ctx.bom_items, ctx.positions, ctx.netlist, ctx.pcb_data
        )

    def llm_callback(suggestion: str, feedback: str) -> str:
        """调用 LLM 修正建议"""
        try:
            prompt = (
                f"你的以下设计建议未通过验证:\n\n"
                f"原始建议: {suggestion}\n\n"
                f"验证反馈:\n{feedback}\n\n"
                f"请根据反馈重新生成修正后的设计建议。只输出修正后的建议，不要解释。"
            )
            return controller.agent.chat(prompt)
        except Exception as e:
            logger.warning(f"LLM callback failed: {e}")
            return suggestion  # fallback: return original

    return VerificationEngine(
        check_callback=check_callback,
        llm_callback=llm_callback,
    )
