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

    def test_report_to_dict(self):
        engine = _make_engine(issues_per_round=[[]])
        report = engine.verify("Safe suggestion")
        d = report.to_dict()
        assert d["accepted"] is True
        assert d["final_status"] == "passed"
        assert d["rounds"] == 1

    def test_report_to_markdown(self):
        engine = _make_engine(issues_per_round=[[]])
        report = engine.verify("Safe suggestion")
        md = report.to_markdown()
        assert "闭环验证报告" in md
        assert "Safe suggestion" in md


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
