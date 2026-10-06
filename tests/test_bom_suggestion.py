# -*- coding: utf-8 -*-
"""Phase B 闭环实验的 BOM 变更契约回归测试（纯逻辑，无 LLM / 无 DRC IO）。

背景（2026-09-10 补测）：
2026-09-08 的 17 板 GLM 实验里，Phase B 闭环收敛率只有 4/14=29%、幻觉消除率
35.7%，根因有三条，且都发生在"LLM 输出 → 结构化变更"这一层：

1. 模型不按 prompt 约定输出删除操作：76/77 条变更用
   {"field": "reference", "new_value": "", "action": "replace"} 表达"删除元件"，
   而 prompt 写的是 action:"remove"。
2. 修正轮 prompt 把上述变更渲染成 "字段=reference / 当前值=(空) / 操作=replace"，
   模型看不出自己删了元件，无法作出"撤销"决策。
3. 旧代码把"空 changes（全部撤销）"当成无效响应丢弃，危险建议在数学上不可能
   通过撤销收敛；且零变更用例不区分"分析类"与"解析失败/条目被丢弃"。

这组测试锁住修复后的契约，防止回归。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bom.parser import BOMItem  # noqa: E402
from tests.bom_suggestion import (  # noqa: E402
    apply_bom_changes,
    build_bom_change_prompt,
    build_correction_prompt,
    parse_llm_bom_changes,
    validate_bom_changes,
)


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

def _bom() -> list[BOMItem]:
    return [
        BOMItem(reference="C1", value="100nF", package="0603", part_number=""),
        BOMItem(reference="C2", value="100nF", package="0603", part_number=""),
        BOMItem(reference="U1", value="STM32F103", package="LQFP48", part_number=""),
    ]


# ═══════════════════════════════════════════════════════════════
#  1. 删除语义归一化（本次核心修复）
# ═══════════════════════════════════════════════════════════════

def test_model_removal_idiom_is_normalized_to_canonical_remove():
    """模型用 field='reference' + 空 new_value 表达删除 → 归一化为 action='remove'。"""
    raw = """{"changes": [
        {"reference": "C1", "field": "reference", "old_value": "C1",
         "new_value": "", "action": "replace"}
    ]}"""
    result = parse_llm_bom_changes(raw)
    assert result.parse_error is None
    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.action == "remove", "删除语义必须归一化为 canonical remove"
    assert change.field == "value", "canonical remove 的 field 不应是 reference"
    assert change.new_value == ""
    assert result.normalized_removals == 1


def test_action_remove_without_field_is_canonical():
    """显式 action='remove'（prompt 约定写法）不产生归一化计数。"""
    raw = '{"changes": [{"reference": "C1", "new_value": "", "action": "remove"}]}'
    result = parse_llm_bom_changes(raw)
    assert result.changes[0].action == "remove"
    assert result.changes[0].field == "value"
    assert result.normalized_removals == 0


def test_add_operation_preserved():
    """action='add' 的新元件（位号不在 BOM 中）必须原样保留。"""
    raw = """{"changes": [
        {"reference": "C101", "field": "value", "new_value": "100nF", "action": "add"}
    ]}"""
    result = parse_llm_bom_changes(raw)
    assert result.changes[0].action == "add"
    assert result.changes[0].reference == "C101"
    assert result.normalized_removals == 0


def test_replace_operation_preserved():
    """action='replace' 的参数修改不受归一化影响。"""
    raw = """{"changes": [
        {"reference": "C1", "field": "value", "old_value": "100nF",
         "new_value": "1uF", "action": "replace"}
    ]}"""
    result = parse_llm_bom_changes(raw)
    assert result.changes[0].action == "replace"
    assert result.changes[0].field == "value"
    assert result.changes[0].new_value == "1uF"


def test_missing_action_defaults_to_replace():
    """action 缺失 → 退化为 replace（不猜测语义，避免把幻觉位号变成新增）。"""
    raw = '{"changes": [{"reference": "C1", "field": "value", "new_value": "1uF"}]}'
    result = parse_llm_bom_changes(raw)
    assert result.changes[0].action == "replace"


# ═══════════════════════════════════════════════════════════════
#  2. 空 changes = 合法撤销（危险建议的收敛路径）
# ═══════════════════════════════════════════════════════════════

def test_empty_changes_is_valid_revert_not_parse_error():
    """{"changes": []} 是合法且推荐的收敛结果，不能报 parse_error。

    旧代码 `if corr_result.changes:` 会丢弃空列表 → 危险建议永远无法通过
    撤销收敛（2026-09-08 实验 10/14 未收敛的机制性根因之一）。
    """
    result = parse_llm_bom_changes('{"changes": []}')
    assert result.parse_error is None
    assert result.changes == []


def test_fenced_empty_changes_also_valid():
    raw = "```json\n{\"changes\": []}\n```"
    result = parse_llm_bom_changes(raw)
    assert result.parse_error is None
    assert result.changes == []


def test_applying_empty_changes_yields_equivalent_bom():
    """全量撤销后 BOM 应回到基线 → DRC 无新违规 → 收敛。"""
    bom = _bom()
    reverted = apply_bom_changes(bom, [])
    assert [i.value for i in reverted] == [i.value for i in bom]
    assert reverted is not bom, "必须返回副本，不得就地修改原始 BOM"


# ═══════════════════════════════════════════════════════════════
#  3. 解析健壮性
# ═══════════════════════════════════════════════════════════════

def test_fenced_json_with_trailing_comma():
    raw = """```json
{
  "changes": [
    {"reference": "C1", "field": "value", "new_value": "1uF", "action": "replace"},
  ]
}
```"""
    result = parse_llm_bom_changes(raw)
    assert result.parse_error is None
    assert result.changes[0].new_value == "1uF"


def test_json_wrapped_in_prose_is_extracted():
    raw = '好的，结果如下：{"changes": [{"reference": "C1", "field": "value", ' \
          '"new_value": "1uF", "action": "replace"}]} 以上。'
    result = parse_llm_bom_changes(raw)
    assert result.parse_error is None
    assert len(result.changes) == 1


def test_truncated_json_reports_parse_error():
    """截断的响应必须报 parse_error —— 零变更 ≠ 分析类建议。"""
    raw = '{"changes": [{"reference": "C1", "field": "reference", "ol'
    result = parse_llm_bom_changes(raw)
    assert result.parse_error is not None
    assert result.changes == []


# ═══════════════════════════════════════════════════════════════
#  4. 校验：区分"位号不存在"与"疑似新增但漏写 action"
# ═══════════════════════════════════════════════════════════════

def test_unknown_reference_with_value_flagged_as_suspect_add():
    """带 new_value 的 replace + 位号不在 BOM → 疑似漏写 action:add，需可识别。

    2026-09-08 实验里 17/17 条"增加去耦电容"优化建议产出 0 变更，就是这类条目
    被静默丢弃、最终统计成"纯分析建议通过"。
    """
    result = parse_llm_bom_changes(
        '{"changes": [{"reference": "C_new", "field": "value", '
        '"new_value": "100nF", "action": "replace"}]}'
    )
    valid, warnings = validate_bom_changes(result.changes, _bom())
    assert valid == []
    assert any("疑似新增" in w for w in warnings), warnings


def test_unknown_reference_without_value_is_plain_drop():
    """无 new_value 的未知位号（如幻觉位号做删除）走普通丢弃分支。"""
    result = parse_llm_bom_changes(
        '{"changes": [{"reference": "C999", "field": "value", '
        '"new_value": "", "action": "remove"}]}'
    )
    valid, warnings = validate_bom_changes(result.changes, _bom())
    assert valid == []
    assert warnings and "疑似新增" not in warnings[0]


def test_add_change_bypasses_reference_existence_check():
    valid, warnings = validate_bom_changes(
        parse_llm_bom_changes(
            '{"changes": [{"reference": "C101", "field": "value", '
            '"new_value": "100nF", "action": "add"}]}'
        ).changes,
        _bom(),
    )
    assert len(valid) == 1 and warnings == []


def test_add_with_colliding_reference_is_rejected():
    """add 的位号已存在于 BOM → 拒绝，避免把现有元件变成重复行。"""
    valid, warnings = validate_bom_changes(
        parse_llm_bom_changes(
            '{"changes": [{"reference": "C1", "field": "value", '
            '"new_value": "1uF", "action": "add"}]}'
        ).changes,
        _bom(),
    )
    assert valid == []
    assert any("已存在" in w for w in warnings), warnings


def test_duplicate_adds_for_same_new_reference_merge_into_one_component():
    """同一新元件被拆成 value + package 两条 add → 必须合并成一个元件。

    2026-09-10 实测缺陷：模型为每个新电容输出两条 add（value / package），
    旧 apply_bom_changes 各 append 一个 → 6 个电容变成 12 行残缺元件。
    """
    changes = parse_llm_bom_changes(
        '{"changes": ['
        '{"reference": "C101", "field": "value", "new_value": "100nF", "action": "add"},'
        '{"reference": "C101", "field": "package", "new_value": "0603", "action": "add"}'
        ']}'
    ).changes
    valid, _ = validate_bom_changes(changes, _bom())
    assert len(valid) == 2, "校验层应两条都放行（C101 不在原 BOM 中）"

    modified = apply_bom_changes(_bom(), valid)
    added = [i for i in modified if i.reference == "C101"]
    assert len(added) == 1, "同一新位号只能产生一个元件"
    assert added[0].value == "100nF" and added[0].package == "0603", \
        "value 与 package 应合并到同一条"


def test_add_does_not_corrupt_original_bom_order():
    """新增元件追加在末尾，不改动原有元件。"""
    changes = parse_llm_bom_changes(
        '{"changes": [{"reference": "C101", "field": "value", '
        '"new_value": "100nF", "action": "add"}]}'
    ).changes
    bom = _bom()
    modified = apply_bom_changes(bom, changes)
    assert len(modified) == len(bom) + 1
    assert [i.reference for i in modified[:len(bom)]] == [i.reference for i in bom]


def test_initial_prompt_requires_single_add_per_component():
    """prompt 必须禁止"同一新元件再输出一条 package add"（本次修复的缺陷源）。"""
    p = build_bom_change_prompt("在每个 IC VDD 引脚旁增加 100nF 去耦电容", _bom())
    assert "每个新元件只输出一条 add" in p
    assert "package" in p
    assert "C101" in p


def test_field_reference_with_value_is_rejected_or_kept_consistently():
    """field='reference' 且带 new_value（改位号）不得被误当成删除。"""
    result = parse_llm_bom_changes(
        '{"changes": [{"reference": "C1", "field": "reference", '
        '"new_value": "C10", "action": "replace"}]}'
    )
    assert result.changes[0].action == "replace"
    assert result.normalized_removals == 0


# ═══════════════════════════════════════════════════════════════
#  5. 应用变更
# ═══════════════════════════════════════════════════════════════

def test_removal_marks_component_removed():
    changes = parse_llm_bom_changes(
        '{"changes": [{"reference": "C1", "field": "reference", '
        '"new_value": "", "action": "replace"}]}'
    ).changes
    valid, _ = validate_bom_changes(changes, _bom())
    modified = apply_bom_changes(_bom(), valid)
    assert modified[0].value == "[REMOVED]"
    assert modified[1].value == "100nF", "其他元件不受影响"


def test_original_bom_not_mutated():
    bom = _bom()
    changes = parse_llm_bom_changes(
        '{"changes": [{"reference": "C1", "field": "value", '
        '"new_value": "1uF", "action": "replace"}]}'
    ).changes
    apply_bom_changes(bom, changes)
    assert bom[0].value == "100nF"


# ═══════════════════════════════════════════════════════════════
#  6. Prompt 契约（首轮 + 修正轮）
# ═══════════════════════════════════════════════════════════════

def test_initial_prompt_documents_three_operations_with_examples():
    p = build_bom_change_prompt("移除所有 100nF 去耦电容", _bom())
    assert '"action": "replace"' in p
    assert '"action": "remove"' in p
    assert '"action": "add"' in p
    assert "永远不能是" in p and "reference" in p


def test_initial_prompt_forbids_field_reference_as_removal_idiom():
    p = build_bom_change_prompt("删除 C1", _bom())
    assert "field" in p and "reference" in p
    assert "禁止用 field" in p or "不能是" in p


def test_correction_prompt_renders_removal_readably():
    """修正轮必须让人（和模型）一眼看出"这条变更删除了哪个元件"。"""
    changes = parse_llm_bom_changes(
        '{"changes": [{"reference": "C1", "field": "reference", '
        '"new_value": "", "action": "replace"}]}'
    ).changes
    p = build_correction_prompt(
        suggestion="移除所有 100nF 去耦电容",
        current_changes=changes,
        new_violations=[],
        original_bom=_bom(),
    )
    # 操作标签用人类可读文字（2026-10-03 起不再带 emoji 图标）
    assert "删除该元件" in p
    # 旧的误导性渲染不应再出现
    assert "| 位号 | 字段 | 原值 | 当前值 | 操作 |" not in p


def test_correction_prompt_authorizes_full_revert_and_replacement_semantics():
    p = build_correction_prompt(
        suggestion="移除所有 100nF 去耦电容",
        current_changes=[],
        new_violations=[],
        original_bom=_bom(),
    )
    assert '{"changes": []}' in p
    assert "全量替换" in p
    assert "撤销" in p


def test_correction_prompt_includes_violation_fix_hints():
    class _V:
        rule_name = "去耦电容检查"
        description = "IC U1 缺少 100nF 高频去耦电容"
        severity = "error"
        location = "U1"
        suggestion = "在 U1 的 VDD 引脚旁补一个 100nF 电容"

    p = build_correction_prompt(
        suggestion="移除所有 100nF 去耦电容",
        current_changes=[],
        new_violations=[_V()],
        original_bom=_bom(),
    )
    assert "修法:" in p
    assert "100nF" in p


def test_correction_prompt_shows_score_drop_signal():
    p = build_correction_prompt(
        suggestion="移除所有 100nF 去耦电容",
        current_changes=[],
        new_violations=[],
        original_bom=_bom(),
        baseline_score=96.7,
        modified_score=93.1,
    )
    assert "综合评分" in p and "3.6" in p


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
