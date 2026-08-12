"""变更风险预检集成测试 — 验证闭环验证中预检字段"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPreflightIntegration:
    """预检在闭环验证中的集成"""

    def test_verify_result_has_preflight_fields(self):
        """VerifyResult 应包含预检字段"""
        from tests.paper_experiments import VerifyResult

        vr = VerifyResult(
            design="test", provider="mock", model="m",
            suggestion_category="safe", suggestion_text="", suggestion_desc="",
            accepted=True, final_status="passed", rounds=1,
            total_issues=0, blocking_issues=0, info_issues=0,
            max_severity="none", llm_correction_rounds=0,
        )
        assert hasattr(vr, "preflight_risk")
        assert hasattr(vr, "preflight_risk_max")
        assert hasattr(vr, "preflight_flagged")
        assert vr.preflight_risk is None  # 默认 None

    def test_preflight_check_method_exists(self):
        """ExperimentRunner 有 _preflight_check 方法"""
        from tests.paper_experiments import ExperimentRunner

        assert hasattr(ExperimentRunner, "_preflight_check")

    def test_preflight_check_low_risk(self):
        """低风险变更不触发拦截"""
        from tests.paper_experiments import ExperimentRunner

        runner = ExperimentRunner.__new__(ExperimentRunner)  # 跳过 __init__
        runner._log = lambda *a, **k: None

        class FakeChange:
            reference = "R1"
            field = "value"
            old_value = "10k"
            new_value = "10.5k"
            action = "replace"

        avg, mx, flagged = runner._preflight_check(
            [FakeChange()], baseline_score=90.0, context=None
        )
        assert 0.0 <= avg <= 1.0
        assert 0.0 <= mx <= 1.0
        assert isinstance(flagged, bool)

    def test_preflight_check_high_risk(self):
        """高风险的晶振+已有违规变更应触发拦截标记"""
        from tests.paper_experiments import ExperimentRunner

        runner = ExperimentRunner.__new__(ExperimentRunner)
        runner._log = lambda *a, **k: None

        class FakeChange:
            reference = "X1"
            field = "value"
            old_value = "8MHz"
            new_value = "16MHz"
            action = "replace"

        # 晶振改频 + 低分 → 风险应较高
        avg, mx, flagged = runner._preflight_check(
            [FakeChange()], baseline_score=60.0, context=None
        )
        assert mx > 0.5

    def test_preflight_serializes(self):
        """预检字段可序列化到 JSON"""
        from tests.paper_experiments import VerifyResult

        vr = VerifyResult(
            design="t", provider="p", model="m",
            suggestion_category="safe", suggestion_text="", suggestion_desc="",
            accepted=True, final_status="passed", rounds=1,
            total_issues=0, blocking_issues=0, info_issues=0,
            max_severity="none", llm_correction_rounds=0,
            preflight_risk=0.42, preflight_risk_max=0.9, preflight_flagged=True,
        )
        data = json.loads(json.dumps(vr.__dict__, default=str))
        assert data["preflight_risk"] == 0.42
        assert data["preflight_flagged"] is True
