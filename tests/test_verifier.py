"""Tests for closed-loop verification engine."""

import pytest
from src.core.verifier import (
    VerificationEngine,
    VerificationReport,
    VerificationRound,
    VerificationStatus,
    VerificationIssue,
    SuggestionCategory,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

class FakeViolation:
    """Minimal fake that mimics RuleViolation attributes."""
    def __init__(self, rule_name, description="test", severity="warning", location="", suggestion=""):
        self.rule_name = rule_name
        self.description = description
        self.severity = type("Sev", (), {"value": severity})()
        self.location = location
        self.suggestion = suggestion


def _make_engine(issues_per_round=None, llm_response="fixed"):
    """Create a VerificationEngine with controlled check/llm callbacks."""
    call_count = [0]

    def check():
        call_count[0] += 1
        r = call_count[0]
        if issues_per_round and r <= len(issues_per_round):
            return issues_per_round[r - 1]
        return []

    def llm(suggestion, feedback):
        return llm_response

    engine = VerificationEngine(check_callback=check, llm_callback=llm)
    engine.call_count = call_count  # attach for assertions
    return engine


# ═══════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════

class TestVerificationEngine:
    def test_passes_with_no_issues(self):
        """Clean BOM → verification passes in 1 round."""
        engine = _make_engine(issues_per_round=[[]])
        report = engine.verify("Add a 100nF decoupling cap near U1")
        assert report.accepted
        assert report.final_status == VerificationStatus.PASSED
        assert report.round_count == 1

    def test_fails_with_issues_no_llm(self):
        """Violations found, no LLM callback → fails."""
        issues = [
            FakeViolation("DECOUPLING_MISSING", "Missing 100nF near U1", "error"),
        ]
        engine = VerificationEngine(check_callback=lambda: issues, llm_callback=None)
        report = engine.verify("Remove all decoupling caps")
        assert not report.accepted
        assert report.final_status == VerificationStatus.FAILED

    def test_iterates_with_llm_correction(self):
        """Round 1: 1 issue → LLM corrects → Round 2: clean → passed."""
        engine = _make_engine(
            issues_per_round=[
                [FakeViolation("DECOUPLING_MISSING", "Missing cap")],  # round 1
                [],  # round 2 — fixed
            ],
            llm_response="Add a 100nF cap near U1 (corrected)"
        )
        report = engine.verify("Don't add any caps")
        assert report.accepted
        assert report.round_count == 2

    def test_max_rounds_stops(self):
        """Max 3 rounds, all fail → final status FAILED."""
        issues = [FakeViolation("ALWAYS_FAIL", "persistent")]
        engine = _make_engine(
            issues_per_round=[issues, issues, issues],
            llm_response="still wrong"
        )
        report = engine.verify("Bad suggestion")
        assert not report.accepted
        assert report.final_status == VerificationStatus.FAILED
        assert report.round_count == 3

    def test_uncertain_without_callbacks(self):
        """No check callback at all → UNCERTAIN."""
        engine = VerificationEngine()
        report = engine.verify("Some suggestion")
        assert report.final_status == VerificationStatus.UNCERTAIN

    def test_passes_with_only_info_level_issues(self):
        """Info-level violations are NOT blocking — accepted=True."""
        issues = [
            FakeViolation("E24_CHECK", "100nF not in E24 series", "info"),
            FakeViolation("E24_CHECK", "100Ω not in E24 series", "info"),
        ]
        engine = VerificationEngine(check_callback=lambda: issues, llm_callback=None)
        report = engine.verify("Keep BOM as-is")
        assert report.accepted is True
        assert report.final_status == VerificationStatus.PASSED
        assert report.round_count == 1
        # All issues still recorded
        assert report.total_issues == 2
        # But zero blocking
        d = report.to_dict()
        assert d["blocking_issues"] == 0

    def test_fails_with_mixed_severity(self):
        """Error + info → still fails due to error."""
        issues = [
            FakeViolation("E24_CHECK", "100nF not in E24 series", "info"),
            FakeViolation("POWER_TRACE", "Trace too thin for 5A", "error"),
        ]
        engine = VerificationEngine(check_callback=lambda: issues, llm_callback=None)
        report = engine.verify("Use thin trace for power")
        assert report.accepted is False
        assert report.final_status == VerificationStatus.FAILED
        # 2 total, 1 blocking
        d = report.to_dict()
        assert d["total_issues"] == 2
        assert d["blocking_issues"] == 1

    def test_llm_feedback_only_includes_blocking(self):
        """LLM correction feedback only contains error/warning, not info."""
        issues = [
            FakeViolation("E24_CHECK", "Not E24 series", "info"),
            FakeViolation("DECOUPLING", "Missing cap", "error"),
        ]
        call_count = [0]
        last_feedback = [""]

        def check():
            call_count[0] += 1
            if call_count[0] == 1:
                return issues
            return []

        def llm_cb(suggestion, feedback):
            last_feedback[0] = feedback
            return "Fixed"

        engine = VerificationEngine(check_callback=check, llm_callback=llm_cb)
        engine.verify("Test")
        # Feedback should mention DECOUPLING but not E24_CHECK
        assert "DECOUPLING" in last_feedback[0]
        assert "E24_CHECK" not in last_feedback[0]

    def test_report_to_dict(self):
        engine = _make_engine(issues_per_round=[[]])
        report = engine.verify("Safe suggestion")
        d = report.to_dict()
        assert d["accepted"] is True
        assert d["final_status"] == "passed"
        assert d["rounds"] == 1
        assert "blocking_issues" in d
        assert d["blocking_issues"] == 0

    def test_report_to_markdown(self):
        engine = _make_engine(issues_per_round=[[]])
        report = engine.verify("Safe suggestion")
        md = report.to_markdown()
        assert "闭环验证报告" in md
        assert "Safe suggestion" in md
        assert "阻断性违规" in md


class TestVerificationRound:
    def test_default_status(self):
        vr = VerificationRound(round=1, suggestion="test")
        assert vr.status == VerificationStatus.UNCERTAIN
        assert vr.issues == []


class TestVerificationReport:
    def test_empty_report(self):
        r = VerificationReport(original_suggestion="test")
        assert r.round_count == 0
        assert r.total_issues == 0
        assert not r.accepted
        assert r.final_status == VerificationStatus.UNCERTAIN


class TestSuggestionCategory:
    def test_all_categories_exist(self):
        assert SuggestionCategory.BOM_CHANGE.value == "bom_change"
        assert SuggestionCategory.RULE_CHANGE.value == "rule_change"
        assert SuggestionCategory.LAYOUT_CHANGE.value == "layout_change"
        assert SuggestionCategory.ROUTING_CHANGE.value == "routing_change"
        assert SuggestionCategory.GENERAL.value == "general"


class TestVerificationEngineVerifyRule:
    def test_valid_code_passes(self):
        """Syntactically valid rule code passes syntax check."""
        engine = _make_engine(issues_per_round=[[]])
        report = engine.verify_rule(
            "Check for missing pull-ups on I2C",
            rule_code="def check():\n    pass\n"
        )
        assert report.accepted

    def test_invalid_code_fails(self):
        """Syntax error in rule code → immediate failure."""
        engine = VerificationEngine()
        report = engine.verify_rule(
            "Broken rule",
            rule_code="def check(:\n    pass\n"  # syntax error
        )
        assert not report.accepted
        assert report.final_status == VerificationStatus.FAILED
        assert report.round_count == 1
        # Should have a syntax issue
        assert any("语法" in i.description for i in report.rounds[0].issues)


class TestVerificationEngineDiff:
    def test_diff_detects_new_issues(self):
        """Baseline has no issues, after change has issues → detected."""
        baseline = []
        after = [FakeViolation("NEW_ISSUE", "Introduced by change", "error")]

        engine = VerificationEngine(check_callback=lambda: after)
        report = engine.verify_design_change(
            "Remove critical resistor",
            before_check=lambda: baseline,
        )
        assert not report.accepted
        assert any("NEW_ISSUE" == i.rule_name
                   for r in report.rounds for i in r.issues)


# ═══════════════════════════════════════════════════════════════
# Convergence integration (engine-level state machine)
# ═══════════════════════════════════════════════════════════════

from src.core.convergence import ConvergenceStatus  # noqa: E402


class TestVerificationEngineConvergence:
    """Engine-level coverage of converged / stagnated / oscillated / diverged paths."""

    @staticmethod
    def _constant_issue_engine(llm_response, rounds_supported=6):
        """Engine with a persistent blocking violation and a constant LLM echo."""
        call_count = [0]

        def check():
            call_count[0] += 1
            return [FakeViolation("ALWAYS_FAIL", "persistent")]

        def llm(_suggestion, _feedback):
            return llm_response

        return VerificationEngine(
            check_callback=check, llm_callback=llm, max_rounds=rounds_supported
        )

    def test_stagnation_detected_before_max_rounds(self):
        """LLM返回与上一轮相同建议 → STAGNATED，提前在 3 轮终止（max=5）。"""
        engine = self._constant_issue_engine(llm_response="unchanged fix", rounds_supported=5)
        report = engine.verify("Bad advice")
        # round1=orig, round2="unchanged fix"(fp differs from orig), round3="unchanged fix"(=round2 fp)
        assert report.final_status == VerificationStatus.FAILED
        assert report.round_count == 3
        assert report.convergence is not None
        assert report.convergence.status == ConvergenceStatus.STAGNATED
        # 第三轮因停滞中断，不再调用 LLM → 共 2 次修正调用
        assert report.convergence.total_llm_calls == 2

    def test_max_rounds_when_suggestions_all_differ(self):
        """每轮建议指纹都不同且不收敛 → MAX_ROUNDS。"""
        engine = self._constant_issue_engine(llm_response="cycle-0", rounds_supported=2)
        # max=2, round1 orig → fix "cycle-0", round2 "cycle-0" (same as round1 fix)
        # round2 fp==round1 fix fp → 停滞在 round2 → 但仍是 STAGNATED 而非 MAX_ROUNDS
        # 为得到 MAX_ROUNDS 必须每轮建议都不同；用递增返回值构造
        state = [0]

        def check():
            return [FakeViolation("ALWAYS_FAIL", "x")]

        def llm(_s, _f):
            state[0] += 1
            return f"fix-v{state[0]}"

        engine = VerificationEngine(check_callback=check, llm_callback=llm, max_rounds=3)
        report = engine.verify("origin-suggestion")
        assert report.convergence is not None
        assert report.convergence.status == ConvergenceStatus.MAX_ROUNDS
        assert report.round_count == 3

    def test_oscillation_detected(self):
        """LLM在两个建议间来回摆动 → OSCILLATING。"""
        calls = [0]

        def check():
            return [FakeViolation("ALWAYS_FAIL", "x")]

        def llm(_s, _f):
            calls[0] += 1
            return "A" if calls[0] % 2 == 1 else "B"

        engine = VerificationEngine(check_callback=check, llm_callback=llm, max_rounds=6)
        report = engine.verify("origin")
        # founder A→B→A: round1 orig; round2 A; round3 B; round4 A (=round2) → 周期2 振荡
        assert report.convergence is not None
        assert report.convergence.status == ConvergenceStatus.OSCILLATING

    def test_divergence_detected(self):
        """阻断违规数严格递增 → DIVERGED。"""
        checks = [0]

        def check():
            checks[0] += 1
            return [FakeViolation(f"R{checks[0]}", f"v{checks[0]}") for _ in range(checks[0])]

        engine = VerificationEngine(check_callback=check, llm_callback=lambda s, f: s + " v", max_rounds=5)
        report = engine.verify("start")
        assert report.convergence is not None
        assert report.convergence.status == ConvergenceStatus.DIVERGED

    def test_converged_result_has_metrics(self):
        """收敛报告包含收敛轮次与缩减曲线。"""
        engine = _make_engine(
            issues_per_round=[[FakeViolation("A", "x", "error")], []],
            llm_response="fixed",
        )
        report = engine.verify("Bad suggestion")
        assert report.accepted
        assert report.convergence is not None
        assert report.convergence.status == ConvergenceStatus.CONVERGED
        assert report.convergence.converged_round == 2
        assert report.convergence.issue_reduction_curve == (1, 0)
        assert report.convergence.correction_efficiency == 1.0

    def test_degenerate_no_callback_has_no_convergence(self):
        """无 check callback 的退化路径：convergence 保持 None（未启用监控）。"""
        engine = VerificationEngine()
        report = engine.verify("Some suggestion")
        assert report.final_status == VerificationStatus.UNCERTAIN
        assert report.convergence is None

    def test_report_to_dict_includes_convergence_block(self):
        engine = _make_engine(issues_per_round=[[]])
        d = engine.verify("Safe suggestion").to_dict()
        assert "convergence" in d
        assert d["convergence"]["status"] == "converged"

    def test_report_to_markdown_includes_convergence_section(self):
        engine = _make_engine(
            issues_per_round=[[FakeViolation("A", "x", "error")], []],
            llm_response="fixed",
        )
        md = engine.verify("Bad suggestion").to_markdown()
        assert "收敛分析" in md
        assert "收敛轮次" in md
        assert "阻断违规曲线" in md

    def test_max_rounds_configurable(self):
        """max_rounds 可在构造时配置，独立于类默认。"""
        engine = self._constant_issue_engine(llm_response="zzz", rounds_supported=5)
        assert engine._max_rounds == 5
        assert VerificationEngine.MAX_ROUNDS == 3  # 类默认不变

    def test_invalid_max_rounds_raises(self):
        try:
            VerificationEngine(max_rounds=0)
            assert False
        except ValueError:
            pass
