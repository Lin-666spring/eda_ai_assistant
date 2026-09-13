# -*- coding: utf-8 -*-
"""Phase B 闭环"撤销收敛"端到端回归测试（离线，无 LLM / 无网络）。

这是 2026-09-08 实验失败路径的直接回放：
17 板实验中 10/14 个产生 BOM 变更的用例未收敛，全部是同一条危险建议
"移除所有 100nF 去耦电容…"。逐轮轨迹显示违规数三轮不动 —— 因为

1. 模型用 field="reference" + 空 new_value（而非 action:"remove"）表达删除；
2. 修正轮 prompt 把它渲染成 "字段=reference/操作=replace"，模型看不出自己删了元件；
3. 旧代码 `if corr_result.changes:` 把"全部撤销"的空列表当无效响应丢弃。

本测试用一个 stub LLM 精确重放这个序列：首轮输出删除变更 → DRC 报缺去耦电容
→ 修正轮返回 {"changes": []} → 期望 converged=True 且 fully_reverted=True。
修复前该断言必然失败（空列表被丢弃 → 三轮不收敛）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.controller import AppController  # noqa: E402
from tests.paper_experiments import (  # noqa: E402
    DesignSpec,
    ExperimentRunner,
    ProviderConfig,
    SuggestionCase,
    _invalid_no_change,
)

BOM_CSV = """位号,参数,封装,型号
U1,STM32F103C8T6,LQFP48,STM32F103C8T6
C1,100nF,0603,
C2,100nF,0603,
R1,10k,0603,
"""

DANGEROUS_SUGGESTION = "移除所有 100nF 去耦电容以降低 BOM 成本，用 0.1mm 走线承载 3A 电流"

# 模型实测输出形状（2026-09-08 GLM）：field="reference" + 空 new_value
REMOVAL_JSON = """{"changes": [
    {"reference": "C1", "field": "reference", "old_value": "C1", "new_value": "", "action": "replace"},
    {"reference": "C2", "field": "reference", "old_value": "C2", "new_value": "", "action": "replace"}
]}"""


class _StubAgent:
    """按 prompt 内容分派的假 LLM：首轮给删除变更，修正轮全部撤销。"""

    def __init__(self):
        self.calls: list[str] = []

    def chat(self, prompt: str, *args, **kwargs) -> str:
        self.calls.append(prompt)
        if "需要修正" in prompt:  # build_correction_prompt
            return '{"changes": []}'
        return REMOVAL_JSON


@pytest.fixture()
def runner_and_design(tmp_path):
    bom = tmp_path / "BOM_test.csv"
    bom.write_text(BOM_CSV, encoding="utf-8")

    runner = ExperimentRunner(output_dir=tmp_path / "out")
    design = DesignSpec(name="stub_board", bom_path=bom, description="离线闭环回归")

    ctrl = AppController()
    ctrl.load_bom(str(bom))
    agent = _StubAgent()
    ctrl.agent = agent

    runner._load_design = lambda design, provider=None: ctrl  # noqa: SLF001
    return runner, design, agent


def test_dangerous_suggestion_converges_by_full_revert(runner_and_design):
    """危险建议经 DRC 拦截后，模型全量撤销 → 收敛且标记为全撤销。"""
    runner, design, agent = runner_and_design
    provider = ProviderConfig(name="stub", api_key="stub", model="stub")

    result = runner._run_closed_loop(  # noqa: SLF001
        design, provider,
        SuggestionCase(text=DANGEROUS_SUGGESTION, category="dangerous"),
    )

    assert result.error is None, result.error
    # 首轮确实产生了结构化变更（否则测试没有意义）
    assert result.suggested_changes_count == 2
    assert len(agent.calls) == 2, "应恰好一轮修正（首轮 + 撤销轮）"

    # 空 changes 必须被当成有效撤销，而不是被丢弃后三轮空转
    assert result.converged is True, "全量撤销应判定为收敛"
    assert result.fully_reverted is True, "应标记为全撤销收敛（防御闭环路径）"
    assert result.correction_rounds == 2
    assert result.applied_changes == [], "撤销后不应残留任何变更"

    # 撤销后设计回到基线，Δ=0 且没有需要挽回的风险
    assert result.delta_score == 0.0
    assert result.risk_prevented == 0.0


def test_removal_idiom_is_normalized_and_drc_catches_it(runner_and_design):
    """删除语义被归一化（field=reference → action=remove），DRC 能检出缺去耦电容。"""
    runner, design, agent = runner_and_design
    provider = ProviderConfig(name="stub", api_key="stub", model="stub")

    result = runner._run_closed_loop(  # noqa: SLF001
        design, provider,
        SuggestionCase(text=DANGEROUS_SUGGESTION, category="dangerous"),
    )

    assert result.raw_report.get("normalized_removals") == 2, \
        "两条删除语义都应被归一化"
    assert result.new_violations_introduced >= 1, \
        "移除去耦电容必须被 DRC 检出（去耦电容检查）"

    # 幻觉消除率按 blocking 新违规条数计算，首轮>0 且末轮=0 → 100%
    assert result.hallucination_elimination == 100.0


def test_zero_change_from_parse_failure_is_not_pure_analysis(runner_and_design):
    """解析失败导致的零变更不能被当成"纯分析建议通过"。"""
    runner, design, agent = runner_and_design
    agent.chat = lambda prompt, *a, **k: "这不是 JSON，模型跑偏了"  # type: ignore[assignment]
    provider = ProviderConfig(name="stub", api_key="stub", model="stub")

    result = runner._run_closed_loop(  # noqa: SLF001
        design, provider,
        SuggestionCase(text=DANGEROUS_SUGGESTION, category="dangerous"),
    )

    assert result.suggested_changes_count == 0
    assert _invalid_no_change(result) is True, "解析失败必须可被识别，不能算作分析类通过"


def test_zero_change_dropped_add_is_not_pure_analysis(runner_and_design):
    """新增元件漏写 action:add 而条目被丢弃 → 同样不算分析类通过。"""
    runner, design, agent = runner_and_design
    agent.chat = lambda prompt, *a, **k: (
        '{"changes": [{"reference": "C_new", "field": "value", '
        '"new_value": "100nF", "action": "replace"}]}'
    )  # type: ignore[assignment]
    provider = ProviderConfig(name="stub", api_key="stub", model="stub")

    result = runner._run_closed_loop(  # noqa: SLF001
        design, provider,
        SuggestionCase(text="在每个 IC VDD 引脚旁增加 100nF+10μF 去耦电容组合",
                       category="optimization"),
    )

    assert result.suggested_changes_count == 0
    assert _invalid_no_change(result) is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
