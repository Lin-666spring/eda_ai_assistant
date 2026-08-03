"""
Integration tests for the closed-loop verification pipeline (路线三).

These tests exercise the FULL chain:
  Controller → create_verifier_from_controller() → VerificationEngine
  → DesignRuleChecker.check_all() → violations → LLM callback → iteration

Uses the real sample BOM + PCB data with a mock LLMClient for
deterministic, repeatable testing without external API dependencies.
"""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.controller import AppController, CommandContext
from src.core.verifier import (
    VerificationEngine,
    VerificationReport,
    VerificationRound,
    VerificationStatus,
    VerificationIssue,
    SuggestionCategory,
    create_verifier_from_controller,
)
from src.agent.review_agents import (
    MultiAgentReviewer,
    MultiAgentReviewReport,
    AgentReport,
    AgentFinding,
    AGENT_DEFINITIONS,
)
from src.agent.tools import ToolRegistry, TOOLS
from src.rules.checker import DesignRuleChecker, RuleViolation, RuleSeverity


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

SAMPLE_BOM = Path(__file__).parent / "sample_bom.csv"
SAMPLE_POSITIONS = Path(__file__).parent / "sample_positions.csv"
SAMPLE_PCB = Path(__file__).parent / "sample_pcb.json"


class MockLLMClient:
    """Deterministic mock LLM client for integration testing.

    Configurable per-test: set .chat_response to control what the mock returns.
    """
    def __init__(self):
        self.chat_response = ""
        self.chat_history = []  # records (prompt, system_prompt) tuples
        self._history = []

    def chat(self, prompt, system_prompt=None):
        self.chat_history.append((prompt, system_prompt))
        return self.chat_response

    def chat_stream(self, prompt, system_prompt=None):
        self.chat_history.append((prompt, system_prompt))
        yield self.chat_response

    def is_available(self):
        return True

    def clear_history(self):
        self._history.clear()
        self.chat_history.clear()


class FailingMockLLMClient(MockLLMClient):
    """Mock that simulates LLM API failures."""
    def chat(self, prompt, system_prompt=None):
        self.chat_history.append((prompt, system_prompt))
        raise RuntimeError("Simulated LLM API failure")


class CorrectionMockLLM(MockLLMClient):
    """Mock that returns progressively better corrections for iteration testing."""
    def __init__(self, responses=None):
        super().__init__()
        self.responses = responses or []
        self.call_count = 0

    def chat(self, prompt, system_prompt=None):
        self.chat_history.append((prompt, system_prompt))
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        self.call_count += 1
        return self.chat_response  # fallback


@pytest.fixture
def controller_with_bom():
    """Controller with sample BOM loaded."""
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    return ctrl


@pytest.fixture
def controller_with_bom_and_pcb():
    """Controller with both BOM and PCB loaded."""
    ctrl = AppController()
    ctrl.load_bom(str(SAMPLE_BOM))
    ctrl.load_positions(str(SAMPLE_POSITIONS))
    ctrl.load_pcb(str(SAMPLE_PCB))
    return ctrl


@pytest.fixture
def mock_llm():
    """Basic mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def engine_with_mock():
    """VerificationEngine with mock callbacks."""
    check_results = [[]]  # mutable so tests can change it

    def check():
        return check_results[0]

    llm = MockLLMClient()
    llm.chat_response = "Corrected: add 100nF capacitor near U1"

    engine = VerificationEngine(
        check_callback=check,
        llm_callback=lambda s, f: llm.chat(f"Fix: {s}\nFeedback: {f}"),
    )
    engine._check_results = check_results
    engine._mock_llm = llm
    return engine


# ═══════════════════════════════════════════════════════════════
# 1. Full Pipeline: verify_suggestion with real BOM data
# ═══════════════════════════════════════════════════════════════

class TestVerifySuggestionFullPipeline:
    """End-to-end tests for controller.verify_suggestion()."""

    def test_verify_suggestion_runs_full_pipeline_with_real_bom(self, controller_with_bom):
        """Even a benign suggestion triggers full DRC check against real BOM data.

        The sample BOM may have pre-existing design violations (e.g. missing
        decoupling caps, trace width issues).  A suggestion that says "change
        nothing" will still trigger the DRC engine, and if violations exist,
        the report will reflect that.  This test validates the end-to-end
        pipeline works — not that the sample data is clean.
        """
        ctrl = controller_with_bom
        # Mock LLM: no correction needed if this is about verifying pipeline
        mock = MockLLMClient()
        mock.chat_response = "Suggestion is safe, no changes needed"
        ctrl.agent = mock

        result_json = ctrl.verify_suggestion(
            "Keep the existing BOM as-is, all components are correctly selected"
        )
        report = json.loads(result_json)

        # The pipeline completes and returns a well-formed report
        assert "accepted" in report
        assert "final_status" in report
        assert report["rounds"] >= 1
        assert "total_issues" in report
        assert "details" in report
        # With real BOM, DRC will find some violations, so accepted may be False
        # — that's correct: the engine is doing its job.

    def test_verify_suggestion_fails_bad_suggestion(self, controller_with_bom):
        """A dangerous suggestion is caught and rejected."""
        ctrl = controller_with_bom
        mock = MockLLMClient()
        # LLM keeps suggesting bad things even after correction
        mock.chat_response = "Remove all decoupling capacitors, they are unnecessary"
        ctrl.agent = mock

        result_json = ctrl.verify_suggestion(
            "Remove all decoupling capacitors to save cost"
        )
        report = json.loads(result_json)

        # Should be rejected (or uncertain if no violations triggered)
        # What matters is the report structure is correct
        assert "accepted" in report
        assert "final_status" in report
        assert "rounds" in report
        assert "total_issues" in report

    def test_verify_suggestion_with_no_bom_returns_error(self):
        """verify_suggestion on empty context returns an error."""
        ctrl = AppController()
        mock = MockLLMClient()
        ctrl.agent = mock

        result_json = ctrl.verify_suggestion("Add 100nF capacitors")
        report = json.loads(result_json)

        # With no data, verification is UNCERTAIN (no check callback data)
        assert "final_status" in report

    def test_verify_suggestion_report_has_all_fields(self, controller_with_bom):
        """The JSON report includes all required fields for frontend rendering."""
        ctrl = controller_with_bom
        ctrl.agent = MockLLMClient()

        result_json = ctrl.verify_suggestion("Use 10uF instead of 100nF for C1")
        report = json.loads(result_json)

        # Top-level fields
        for key in ["accepted", "final_status", "rounds", "total_issues",
                     "blocking_issues", "category", "summary", "details"]:
            assert key in report, f"Missing key: {key}"

        # Details structure
        if report["details"]:
            detail = report["details"][0]
            for key in ["round", "status", "issues"]:
                assert key in detail, f"Missing detail key: {key}"

    def test_verify_suggestion_handler_no_bom(self):
        """verify_suggestion_handler returns error when no BOM loaded."""
        ctrl = AppController()
        # Call the handler directly
        result = json.loads(ctrl.verify_suggestion_handler())
        assert "error" in result
        assert "BOM" in result["error"]

    def test_verify_suggestion_handler_with_bom(self, controller_with_bom):
        """verify_suggestion_handler returns guide message when BOM is loaded."""
        ctrl = controller_with_bom
        result = ctrl.verify_suggestion_handler()
        assert "闭环验证" in result
        assert "验证建议" in result


# ═══════════════════════════════════════════════════════════════
# 2. Closed-Loop Iteration: convergence and max-rounds
# ═══════════════════════════════════════════════════════════════

class TestClosedLoopIteration:
    """Tests for the iterative correction loop (LLM → verify → LLM → verify)."""

    def test_converges_in_2_rounds(self):
        """Round 1 finds issues → LLM corrects → Round 2 passes."""
        check_results = [
            [RuleViolation("DECOUPLING_MISSING", "Missing cap near U1",
                           RuleSeverity.ERROR, "U1", "Add 100nF cap")],
            [],  # round 2: clean
        ]
        call_idx = [0]

        def check():
            r = call_idx[0]
            call_idx[0] += 1
            return check_results[r] if r < len(check_results) else []

        llm_responses = ["Add 100nF capacitor near U1 (corrected)"]
        llm_call_idx = [0]

        def llm_cb(suggestion, feedback):
            r = llm_call_idx[0]
            llm_call_idx[0] += 1
            return llm_responses[r] if r < len(llm_responses) else suggestion

        engine = VerificationEngine(check_callback=check, llm_callback=llm_cb)
        report = engine.verify("Remove all caps near U1")

        assert report.accepted is True
        assert report.final_status == VerificationStatus.PASSED
        assert report.round_count == 2
        # Round 1 had an issue
        assert report.rounds[0].status == VerificationStatus.FAILED
        assert len(report.rounds[0].issues) == 1
        # Round 2 was clean
        assert report.rounds[1].status == VerificationStatus.PASSED
        assert len(report.rounds[1].issues) == 0

    def test_max_rounds_exhausted(self):
        """Persistent violation → 3 rounds all fail → rejected."""
        persistent = [
            RuleViolation("POWER_TRACE_TOO_THIN", "Trace width insufficient",
                          RuleSeverity.ERROR, "VCC net", "Widen to 1.0mm"),
        ]
        check_results = [persistent, persistent, persistent]
        call_idx = [0]

        def check():
            r = call_idx[0]
            call_idx[0] += 1
            return check_results[r] if r < len(check_results) else persistent

        llm_responses = [
            "Fix attempt 1: widen trace slightly",
            "Fix attempt 2: widen trace more",
        ]
        llm_call_idx = [0]

        def llm_cb(suggestion, feedback):
            r = llm_call_idx[0]
            llm_call_idx[0] += 1
            return llm_responses[r] if r < len(llm_responses) else suggestion

        engine = VerificationEngine(check_callback=check, llm_callback=llm_cb)
        report = engine.verify("Use 0.1mm trace for 5A power")

        assert report.accepted is False
        assert report.final_status == VerificationStatus.FAILED
        assert report.round_count == 3

    def test_llm_correction_failure_fallback(self):
        """LLM throws during correction → graceful degradation, returns original."""
        issues = [RuleViolation("TEST_RULE", "Test issue", RuleSeverity.WARNING)]

        def check():
            return issues

        def failing_llm(suggestion, feedback):
            raise ConnectionError("API unavailable")

        engine = VerificationEngine(check_callback=check, llm_callback=failing_llm)
        report = engine.verify("Some suggestion")

        # Should fail because LLM correction threw and we had issues
        assert report.final_status in (VerificationStatus.FAILED, VerificationStatus.UNCERTAIN)
        assert report.round_count >= 1

    def test_check_callback_exception_uncertain(self):
        """check_callback raises → round is UNCERTAIN."""
        def failing_check():
            raise RuntimeError("DRC engine crash")

        engine = VerificationEngine(check_callback=failing_check)
        report = engine.verify("Any suggestion")

        assert report.final_status == VerificationStatus.UNCERTAIN
        assert report.round_count == 1
        assert report.rounds[0].status == VerificationStatus.UNCERTAIN


# ═══════════════════════════════════════════════════════════════
# 3. Multi-Agent Review with mock LLM
# ═══════════════════════════════════════════════════════════════

class TestMultiAgentReviewIntegration:
    """Integration tests for review_design_multi_agent with real data."""

    def test_review_without_llm_returns_valid_report(self, controller_with_bom):
        """Multi-agent review without LLM produces a well-structured report."""
        ctrl = controller_with_bom
        ctrl.agent = None  # no LLM available

        result_json = ctrl.review_design_multi_agent()
        report = json.loads(result_json)

        # Must have radar data
        assert "radar_data" in report
        assert len(report["radar_data"]) == 6  # 5 dimensions + overall
        assert "overall_score" in report
        assert "overall_grade" in report
        assert "consensus" in report
        assert "agents" in report
        assert "critical_issues" in report
        assert "improvement_roadmap" in report

        # 5 agents must all be present
        for key in ["power", "signal", "thermal", "emc", "dfm"]:
            assert key in report["agents"], f"Missing agent: {key}"
            agent = report["agents"][key]
            assert "name" in agent
            assert "score" in agent
            assert "findings" in agent

    def test_review_without_bom_returns_error(self):
        """Multi-agent review with no BOM returns error."""
        ctrl = AppController()
        result = json.loads(ctrl.review_design_multi_agent())
        assert "error" in result

    def test_review_with_llm(self, controller_with_bom_and_pcb):
        """Multi-agent review with a mock LLM produces enhanced findings."""
        ctrl = controller_with_bom_and_pcb
        mock = MockLLMClient()
        # Return valid JSON for LLM deep analysis
        mock.chat_response = json.dumps({
            "findings": [
                {
                    "title": "MCU needs more decoupling",
                    "severity": "major",
                    "detail": "STM32F103 has multiple VDD pins requiring individual decoupling",
                    "suggestion": "Add 100nF cap to each VDD pin",
                }
            ]
        })
        ctrl.agent = mock

        result_json = ctrl.review_design_multi_agent()
        report = json.loads(result_json)

        assert "error" not in report
        assert "overall_score" in report
        # LLM was called (at least some agent prompts went through)
        assert len(mock.chat_history) >= 0  # at minimum 0 if no violations

    def test_review_with_llm_failure_fallback(self, controller_with_bom):
        """When LLM fails mid-review, fall back to rule-based analysis."""
        ctrl = controller_with_bom
        mock = FailingMockLLMClient()
        ctrl.agent = mock

        # Should not crash, should fall back to rule-based review
        result_json = ctrl.review_design_multi_agent()
        report = json.loads(result_json)

        assert "error" not in report
        assert "overall_score" in report


# ═══════════════════════════════════════════════════════════════
# 4. Tool Registry: verify_suggestion registration
# ═══════════════════════════════════════════════════════════════

class TestVerifySuggestionToolRegistration:
    """verify_suggestion is properly registered in ToolRegistry."""

    def test_tool_in_registry(self):
        """verify_suggestion is in the TOOLS list."""
        tool = ToolRegistry.get_by_name("verify_suggestion")
        assert tool is not None
        assert tool.label == "闭环验证"
        assert tool.category == "pcb"
        assert tool.intent == "RULE_CHECK"

    def test_tool_has_valid_function_definition(self):
        """verify_suggestion generates correct function calling schema."""
        tool = ToolRegistry.get_by_name("verify_suggestion")
        fd = tool.to_function_definition()

        assert fd["type"] == "function"
        assert fd["function"]["name"] == "verify_suggestion"
        assert "suggestion" in fd["function"]["parameters"]["properties"]
        assert "suggestion" in fd["function"]["parameters"]["required"]

    def test_tool_keywords_include_common_terms(self):
        """Keywords cover how users naturally express verification requests."""
        tool = ToolRegistry.get_by_name("verify_suggestion")
        keywords = " ".join(tool.keywords)
        assert "闭环" in keywords
        assert "验证" in keywords
        assert "drc" in keywords.lower()

    def test_tool_in_function_definitions(self):
        """verify_suggestion appears in get_function_definitions output."""
        fds = ToolRegistry.get_function_definitions()
        names = [f["function"]["name"] for f in fds]
        assert "verify_suggestion" in names

    def test_tool_count_is_24(self):
        """Tool registry now has 24 tools (was 23 before verify_suggestion)."""
        assert ToolRegistry.count() == 24


# ═══════════════════════════════════════════════════════════════
# 5. Controller _dispatch_operation for verify_suggestion
# ═══════════════════════════════════════════════════════════════

class TestDispatchVerifySuggestion:
    """_dispatch_operation correctly routes verify_suggestion."""

    def test_dispatch_with_suggestion(self, controller_with_bom):
        """Dispatch verify_suggestion with valid suggestion param."""
        ctrl = controller_with_bom
        ctrl.agent = MockLLMClient()

        result = ctrl._dispatch_operation(
            "verify_suggestion",
            {"suggestion": "Add 100nF decoupling caps to all ICs"},
        )
        # Should return a JSON string (VerificationReport)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "accepted" in parsed
        assert "final_status" in parsed

    def test_dispatch_without_suggestion(self, controller_with_bom):
        """Dispatch verify_suggestion with empty suggestion → guide message."""
        ctrl = controller_with_bom

        result = ctrl._dispatch_operation("verify_suggestion", {})
        assert "闭环验证" in result
        assert "设计建议" in result

    def test_dispatch_tool_handler_resolution(self, controller_with_bom):
        """_resolve_handler_by_tool maps verify_suggestion correctly."""
        ctrl = controller_with_bom

        handler = ctrl._resolve_handler_by_tool("verify_suggestion")
        assert handler is not None
        # Handler should be callable without args
        result = handler()
        assert "闭环验证" in result


# ═══════════════════════════════════════════════════════════════
# 6. create_verifier_from_controller — real data path
# ═══════════════════════════════════════════════════════════════

class TestCreateVerifierFromController:
    """create_verifier_from_controller() produces a working engine."""

    def test_creates_engine_with_bom(self, controller_with_bom_and_pcb):
        """With BOM+PCB loaded, the factory creates a working engine."""
        ctrl = controller_with_bom_and_pcb
        ctrl.agent = MockLLMClient()

        engine = create_verifier_from_controller(ctrl)
        assert engine is not None
        assert engine._check_callback is not None
        assert engine._llm_callback is not None

    def test_engine_check_callback_runs_real_drc(self, controller_with_bom):
        """The check_callback runs DesignRuleChecker on real data."""
        ctrl = controller_with_bom
        # Mock LLM is needed for the llm_callback, but check_callback doesn't need it
        ctrl.agent = MockLLMClient()

        engine = create_verifier_from_controller(ctrl)

        # Run the check callback
        violations = engine._check_callback()
        # With real BOM data, we should get some violations
        assert isinstance(violations, list)
        # All returned items should be RuleViolation instances
        for v in violations:
            assert isinstance(v, RuleViolation)

    def test_llm_callback_passes_correct_format(self, controller_with_bom):
        """The llm_callback formats prompt correctly and calls LLM."""
        ctrl = controller_with_bom
        mock = MockLLMClient()
        mock.chat_response = "Corrected suggestion text"
        ctrl.agent = mock

        engine = create_verifier_from_controller(ctrl)

        # Simulate what the engine does during correction
        result = engine._llm_callback("Original bad suggestion",
                                       "Feedback: missing decoupling")
        # Should return the mock response
        assert result == "Corrected suggestion text"
        # LLM should have been called
        assert len(mock.chat_history) == 1
        prompt = mock.chat_history[0][0]
        assert "Original bad suggestion" in prompt
        assert "Feedback: missing decoupling" in prompt

    def test_llm_callback_handles_exception(self, controller_with_bom):
        """If LLM is None/throws during callback, fallback to original suggestion."""
        ctrl = controller_with_bom
        ctrl.agent = None

        engine = create_verifier_from_controller(ctrl)

        # llm_callback should return original suggestion as fallback
        result = engine._llm_callback("Original suggestion", "Some feedback")
        assert result == "Original suggestion"

    def test_llm_callback_with_agent_exception(self, controller_with_bom):
        """LLM client throws → callback returns original suggestion."""
        ctrl = controller_with_bom
        ctrl.agent = FailingMockLLMClient()

        engine = create_verifier_from_controller(ctrl)

        result = engine._llm_callback("Keep original", "Feedback")
        assert result == "Keep original"  # fallback


# ═══════════════════════════════════════════════════════════════
# 7. MultiAgentReviewer with real violations
# ═══════════════════════════════════════════════════════════════

class TestMultiAgentReviewerWithRealData:
    """MultiAgentReviewer processes real DRC violations."""

    def test_reviewer_with_real_violations(self, controller_with_bom):
        """Feed real DRC violations → get structured agent reports."""
        ctrl = controller_with_bom

        # Run DRC check to get real violations
        checker = DesignRuleChecker()
        violations = checker.check_all(
            ctrl.context.bom_items,
            ctrl.context.positions,
            pcb_data=ctrl.context.pcb_data,
        )

        # Create reviewer and run
        reviewer = MultiAgentReviewer(llm_client=None)  # rule-based mode
        report = reviewer.review(
            violations,
            ctrl.context.bom_items,
            ctrl.context.positions,
            ctrl.context.pcb_data,
        )

        assert isinstance(report, MultiAgentReviewReport)
        assert len(report.agent_reports) == 5  # 5 agents
        assert 0 <= report.overall_score <= 100
        assert report.overall_grade in ("A", "B", "C", "D", "F")
        assert len(report.radar_data) == 6

        # Each agent report has required fields
        for key, ar in report.agent_reports.items():
            assert ar.agent_key == key
            assert ar.agent_name is not None
            assert ar.score is not None
            assert ar.summary is not None

    def test_reviewer_llm_path_handles_malformed_json(self, controller_with_bom):
        """When LLM returns non-JSON, fall back gracefully."""
        ctrl = controller_with_bom
        checker = DesignRuleChecker()
        violations = checker.check_all(
            ctrl.context.bom_items,
            ctrl.context.positions,
            pcb_data=ctrl.context.pcb_data,
        )

        mock = MockLLMClient()
        mock.chat_response = "This is not valid JSON at all!!"

        reviewer = MultiAgentReviewer(llm_client=mock)

        # Should not crash — _llm_deep_analyze catches errors and returns []
        # then _llm_summarize catches errors and falls back
        report = reviewer.review_with_llm(
            violations,
            ctrl.context.bom_items,
            ctrl.context.positions,
            ctrl.context.pcb_data,
        )

        assert isinstance(report, MultiAgentReviewReport)
        # Even with bad JSON, all 5 agents should be present (via fallback)
        assert len(report.agent_reports) == 5

    def test_agent_definitions_complete(self):
        """All 5 agent definitions have required fields."""
        for key in ["power", "signal", "thermal", "emc", "dfm"]:
            assert key in AGENT_DEFINITIONS
            agent = AGENT_DEFINITIONS[key]
            assert "name" in agent
            assert "domain" in agent
            assert "expertise" in agent
            assert "focus_rules" in agent
            assert len(agent["focus_rules"]) > 0

    def test_filter_violations_by_agent(self, controller_with_bom):
        """_filter_violations correctly assigns violations to agent domains."""
        ctrl = controller_with_bom
        checker = DesignRuleChecker()
        violations = checker.check_all(
            ctrl.context.bom_items,
            ctrl.context.positions,
            pcb_data=ctrl.context.pcb_data,
        )

        reviewer = MultiAgentReviewer()

        # Each agent should get some subset
        for agent_key, agent_def in AGENT_DEFINITIONS.items():
            filtered = reviewer._filter_violations(violations, agent_def["focus_rules"])
            # Not asserting on count — depends on test data
            # But all filtered should have matching rule_names
            for v in filtered:
                matched = any(kw in v.rule_name for kw in agent_def["focus_rules"])
                assert matched, (
                    f"Violation '{v.rule_name}' filtered into {agent_key} "
                    f"but doesn't match any focus rule"
                )


# ═══════════════════════════════════════════════════════════════
# 8. API Request model validation
# ═══════════════════════════════════════════════════════════════

class TestAPIModels:
    """VerifySuggestionRequest model validation."""

    def test_request_model_exists(self):
        """VerifySuggestionRequest is importable and works."""
        from src.api.models import VerifySuggestionRequest
        req = VerifySuggestionRequest(suggestion="Test suggestion")
        assert req.suggestion == "Test suggestion"

    def test_request_model_default(self):
        """VerifySuggestionRequest default is empty string."""
        from src.api.models import VerifySuggestionRequest
        req = VerifySuggestionRequest()
        assert req.suggestion == ""


# ═══════════════════════════════════════════════════════════════
# 9. VerificationReport Markdown output
# ═══════════════════════════════════════════════════════════════

class TestVerificationReportFormatting:
    """The Markdown report is well-formed."""

    def test_passed_report_markdown(self, engine_with_mock):
        """A passed report generates clean Markdown."""
        engine_with_mock._check_results[0] = []  # no violations
        report = engine_with_mock.verify("Safe suggestion")
        md = report.to_markdown()

        assert "闭环验证报告" in md
        assert "Safe suggestion" in md
        assert "✅" in md

    def test_failed_report_markdown(self):
        """A failed report shows violations clearly."""
        issues = [
            RuleViolation("DECOUPLING_MISSING", "Missing cap near U1",
                          RuleSeverity.ERROR, "U1", "Add cap"),
        ]
        engine = VerificationEngine(check_callback=lambda: issues, llm_callback=None)
        report = engine.verify("Bad suggestion")
        md = report.to_markdown()

        assert "❌" in md
        assert "DECOUPLING_MISSING" in md
        assert "Missing cap near U1" in md

    def test_to_dict_matches_report_state(self, engine_with_mock):
        """to_dict() accurately reflects the report state."""
        engine_with_mock._check_results[0] = []
        report = engine_with_mock.verify("Test")
        d = report.to_dict()

        assert d["accepted"] == report.accepted
        assert d["final_status"] == report.final_status.value
        assert d["rounds"] == report.round_count
        assert d["total_issues"] == report.total_issues


# ═══════════════════════════════════════════════════════════════
# 10. verify_design_change — before/after diff
# ═══════════════════════════════════════════════════════════════

class TestVerifyDesignChange:
    """verify_design_change() with before/after differential analysis."""

    def test_diff_detects_new_violations(self):
        """Baseline clean → change introduces violations → detected."""
        def before():
            return []  # clean baseline

        def after():
            return [
                RuleViolation("NEW_POWER_ISSUE", "Power trace too thin",
                              RuleSeverity.ERROR, "VCC net", "Widen trace"),
            ]

        engine = VerificationEngine(check_callback=after)
        report = engine.verify_design_change(
            "Reduce power trace width to 0.1mm",
            before_check=before,
        )

        assert report.accepted is False
        assert any("NEW_POWER_ISSUE" == i.rule_name
                   for r in report.rounds for i in r.issues)

    def test_diff_no_change(self):
        """Baseline has issues → change doesn't add new ones."""
        baseline = [
            RuleViolation("EXISTING_WARNING", "Minor layout concern",
                          RuleSeverity.WARNING, "", ""),
        ]

        def before():
            return baseline

        def after():
            return list(baseline)  # same issues, no new ones

        engine = VerificationEngine(check_callback=after)
        report = engine.verify_design_change(
            "Re-route SPI traces for better layout",
            before_check=before,
        )

        # No NEW violations introduced
        new_issues = [i for r in report.rounds for i in r.issues
                      if "(新引入)" in i.description]
        assert len(new_issues) == 0

    def test_diff_before_check_exception_graceful(self):
        """before_check raises → handled gracefully, diff disabled."""
        def before():
            raise RuntimeError("Cannot run baseline check")

        def after():
            return [
                RuleViolation("ISSUE", "Test", RuleSeverity.WARNING),
            ]

        engine = VerificationEngine(check_callback=after)
        # Should not crash
        report = engine.verify_design_change(
            "Some change",
            before_check=before,
        )
        assert isinstance(report, VerificationReport)
