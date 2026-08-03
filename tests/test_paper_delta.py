"""闭环前后综合评分 Δ 数据链路测试（2026-08-03 新增）。

覆盖 paper_experiments.py 的 Δ 指标：baseline_score / final_score / delta_score，
以及 paper_delta_scores.py 分析脚本的基线模式。用 mock LLM 走完整闭环路径。
"""

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

import tests.paper_experiments as pe
from src.agent.llm_client import LLMClient
from src.core.design_scorer import DesignScorer
from src.rules.checker import DesignRuleChecker


@pytest.fixture
def mock_llm(monkeypatch):
    """Mock LLM：parse 建议→BOM 变更 JSON；correction 轮返回空（不再修改）。"""

    def mock_chat(self, prompt, *args, **kwargs):
        if "修正" in prompt or "引入" in prompt:
            return '{"changes": []}'
        return '{"changes": [{"reference": "C1", "field": "value", "old_value": "100nF", "new_value": "1uF"}]}'

    monkeypatch.setattr(LLMClient, "chat", mock_chat)
    return mock_chat


def _runner(tmp_path) -> pe.ExperimentRunner:
    return pe.ExperimentRunner(output_dir=tmp_path / "run")


def _power_supply() -> pe.DesignSpec:
    return pe.DesignSpec(name="Power_Supply", bom_path=Path("tests/sample_bom_power.csv"))


class TestClosedLoopDelta:
    def test_no_change_delta_zero(self, tmp_path):
        """纯分析建议（无 BOM 变更）：delta=0，baseline_score 正确。"""
        runner = _runner(tmp_path)
        design = _power_supply()
        ctrl = runner._load_design(design)
        base_v = DesignRuleChecker().check_all(
            ctrl.context.bom_items, ctrl.context.positions, pcb_data=None
        )
        manual = DesignScorer().score(base_v, ctrl.context.bom_items).overall
        suggestion = pe.SuggestionCase(category="optimization", text="分析去耦", description="t")
        provider = SimpleNamespace(name="test", model="test-model")
        r = runner._verify_no_change_result(design, provider, suggestion, base_v, 0.0)
        assert r.baseline_score == pytest.approx(manual)
        assert r.final_score == pytest.approx(manual)
        assert r.delta_score == 0.0
        assert r.applied_changes == []

    def test_closed_loop_delta_filled(self, tmp_path, mock_llm):
        """闭环路径：baseline/final/delta 全部填充，applied_changes 记录变更。"""
        runner = _runner(tmp_path)
        design = _power_supply()
        provider = SimpleNamespace(name="deepseek", api_key="sk-test", base_url="", model="test")
        suggestion = pe.SuggestionCase(category="optimization", text="将 C1 从 100nF 改为 1uF", description="t")
        r = runner._run_closed_loop(design, provider, suggestion)
        assert r.baseline_score is not None
        assert r.final_score is not None
        assert r.delta_score is not None
        assert r.applied_changes, "应记录应用的 BOM 变更"
        assert r.applied_changes[0]["reference"] == "C1"

    def test_analysis_script_baseline(self, capsys):
        """paper_delta_scores.py --designs 模式对 4 块真实板输出基线评分。"""
        from tests.paper_delta_scores import baseline_table
        rows = baseline_table()
        assert len(rows) >= 3  # 4 块真实板（缺 BOM 时跳过）
        for r in rows:
            assert 0 <= r["overall"] <= 100
            assert r["grade"] in ("A+", "A", "B+", "B", "C", "D", "F")
        capsys.readouterr()  # 丢弃 print 输出
