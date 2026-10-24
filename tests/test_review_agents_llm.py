"""review_agents LLM 路径回归测试。

钉死两个历史 P0（2026-10-24 验收报告 A-3/A-4）：
- A-3: LLM findings 的 rule_name/location 均为空串，_synthesize_critical
  去重键塌缩成 ":"，跨 Agent 关键问题被当重复丢弃只剩 1 条。
- A-4: _llm_deep_analyze 把网络异常/坏 JSON 吞成 []，短路了
  _process_agent_llm 的规则回退 —— 有 ERROR 违规的板子被报成
  「本领域未发现问题，设计质量良好」。
"""

import json

import pytest

from src.agent.review_agents import MultiAgentReviewer
from src.rules.base import RuleSeverity, RuleViolation


def _violation(rule_name: str, sev=RuleSeverity.ERROR) -> RuleViolation:
    return RuleViolation(
        rule_name=rule_name,
        description=f"{rule_name}：测试用违规描述",
        severity=sev,
        location="R1",
        suggestion="测试用修复建议",
    )


class _FakeLLM:
    """chat() 返回预置 JSON（或抛异常）。"""

    def __init__(self, response: str = "", error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls = 0

    def chat(self, prompt: str) -> str:
        self.calls += 1
        if self._error:
            raise self._error
        return self._response


def _findings_json(*items: dict) -> str:
    return json.dumps({"findings": list(items)}, ensure_ascii=False)


POWER_FINDINGS = _findings_json(
    {"title": "去耦电容缺失", "severity": "critical",
     "detail": "…", "suggestion": "…"},
    {"title": "电源线宽不足", "severity": "critical",
     "detail": "…", "suggestion": "…"},
    {"title": "滤波电容容值偏小", "severity": "major",
     "detail": "…", "suggestion": "…"},
)


class TestSynthesizeCriticalDedup:
    """A-3：LLM findings 去重不得塌缩。"""

    def test_llm_findings_not_collapsed_by_empty_key(self):
        llm = _FakeLLM(POWER_FINDINGS)
        reviewer = MultiAgentReviewer(llm_client=llm)
        report = reviewer.review_with_llm([_violation("去耦电容缺失")])
        power = report.agent_reports["power"]
        assert len(power.findings) == 3
        # 修复前：三条 findings 去重键全是 ":"，critical_issues 只剩 1 条
        critical = report.critical_issues
        titles = [c["title"] for c in critical]
        assert "去耦电容缺失" in titles
        assert "电源线宽不足" in titles
        assert "滤波电容容值偏小" in titles

    def test_rule_findings_still_dedup_across_agents(self):
        """规则模式：同一 rule_name+location 跨 Agent 仍应去重（不因修复回退）。"""
        reviewer = MultiAgentReviewer(llm_client=None)
        report = reviewer.review([_violation("去耦电容缺失")])
        titles = [c["title"] for c in report.critical_issues]
        assert titles.count("去耦电容缺失") == 1


class TestLLMFailureFallsBackToRules:
    """A-4：LLM 失败必须回退规则分析，不得报告『未发现问题』。"""

    def test_network_error_falls_back(self):
        llm = _FakeLLM(error=ConnectionError("boom"))
        reviewer = MultiAgentReviewer(llm_client=llm)
        report = reviewer.review_with_llm([_violation("去耦电容缺失")])
        power = report.agent_reports["power"]
        # 回退规则分析：该违规按 focus_rules 归 power 域
        assert len(power.findings) == 1
        assert power.findings[0].rule_name == "去耦电容缺失"
        assert "未发现问题" not in power.summary
        assert report.critical_issues, "回退后关键问题不得为空"

    def test_non_json_response_falls_back(self):
        llm = _FakeLLM("抱歉，我无法分析这个设计。")
        reviewer = MultiAgentReviewer(llm_client=llm)
        report = reviewer.review_with_llm([_violation("去耦电容缺失")])
        power = report.agent_reports["power"]
        assert len(power.findings) == 1
        assert "未发现问题" not in power.summary

    def test_malformed_json_falls_back(self):
        llm = _FakeLLM('{"findings": [{"title": "半截')
        reviewer = MultiAgentReviewer(llm_client=llm)
        report = reviewer.review_with_llm([_violation("去耦电容缺失")])
        power = report.agent_reports["power"]
        assert len(power.findings) == 1

    def test_clean_domain_reports_no_findings(self):
        """无任何违规时『未发现问题』是正确结论，不应误报。"""
        llm = _FakeLLM(POWER_FINDINGS)
        reviewer = MultiAgentReviewer(llm_client=llm)
        report = reviewer.review_with_llm([])
        for rep in report.agent_reports.values():
            assert rep.findings == []
            assert rep.summary  # 各域均为空结论


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
