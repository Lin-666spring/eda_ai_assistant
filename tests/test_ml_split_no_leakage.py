"""ML 训练数据切分无泄漏回归测试（验收报告 A-9）。

修复前：模板展开后才做样本级随机切分，同一文本可同时落进 train/val
（实测 NLU 验证集 81%、元件集 26% 与训练集逐字重复），val_acc 在测记忆。
修复后：同一模板的全部变体进同一侧 + 跨侧逐字去重。
"""

import json

import pytest

from src.ml.generate_component_data import generate_data as gen_component
from src.ml.generate_nlu_data import generate_data as gen_nlu


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _assert_no_leakage(train, val, label_key):
    train_texts = {s["text"] for s in train}
    val_texts = [s["text"] for s in val]
    # 核心断言：验证集与训练集逐字不重叠，且验证集自身无重复
    assert not (train_texts & set(val_texts)), "验证集存在与训练集逐字相同的样本"
    assert len(val_texts) == len(set(val_texts)), "验证集存在重复文本"
    # 分层保持：每个类别两侧都有样本
    assert {s[label_key] for s in train} == {s[label_key] for s in val}
    # 内部 _template 字段不得泄漏进数据文件
    assert all("_template" not in s for s in train + val)


class TestNLUSplit:
    def test_train_val_disjoint(self, tmp_path):
        gen_nlu(count_per_class=60,
                output_path=str(tmp_path / "nlu_train.json"),
                val_split=0.15, seed=42)
        train = _load(tmp_path / "nlu_train_train.json")
        val = _load(tmp_path / "nlu_train_val.json")
        _assert_no_leakage(train, val, "intent")
        assert len(val) > 0

    def test_different_seeds_still_disjoint(self, tmp_path):
        for seed in (7, 99):
            gen_nlu(count_per_class=30,
                    output_path=str(tmp_path / f"nlu_{seed}.json"),
                    val_split=0.2, seed=seed)
            train = _load(tmp_path / f"nlu_{seed}_train.json")
            val = _load(tmp_path / f"nlu_{seed}_val.json")
            _assert_no_leakage(train, val, "intent")


class TestComponentSplit:
    def test_train_val_disjoint(self, tmp_path):
        gen_component(count_per_class=60,
                      output_path=str(tmp_path / "comp_train.json"),
                      val_split=0.15, seed=42)
        train = _load(tmp_path / "comp_train_train.json")
        val = _load(tmp_path / "comp_train_val.json")
        _assert_no_leakage(train, val, "type")
        assert len(val) > 0


class TestSplitByTemplateUnit:
    def test_same_template_same_side(self):
        from src.ml.split_utils import split_by_template

        items = [
            {"text": f"运行DRC变体{i}", "intent": "DRC", "_template": "运行DRC"}
            for i in range(5)
        ] + [
            {"text": f"查库存变体{i}", "intent": "DRC", "_template": "查库存"}
            for i in range(5)
        ]
        train, val = split_by_template(items, val_split=0.5, label_key="intent")
        assert train and val
        for s in train + val:
            assert "_template" not in s
        # 模板完整性：任一侧不得混入另一模板的样本（5 条全在一侧）
        assert len(train) == 5 and len(val) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
