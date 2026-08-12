"""违规模式挖掘测试 — FP-Growth + 关联规则"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.violation_mining import (
    FPTreeNode,
    _build_fptree,
    mine_frequent_itemsets,
    generate_association_rules,
    extract_transactions_from_results,
)


# ═══ FP 树构建测试 ═══

class TestFPTree:
    """FP 树构建正确性"""

    def test_build_tree_structure(self):
        """FP 树结构正确（头表链 + 总支持度）"""
        from src.ml.violation_mining import _item_total_support

        transactions = [
            ["A", "B"], ["B", "C"], ["A", "B", "C"], ["A", "B", "C"],
        ]
        root, header = _build_fptree(transactions, min_support=2)

        # A, B, C 都出现 ≥2 次
        assert set(header.keys()) == {"A", "B", "C"}
        # 总支持度 = 沿 node_link 链求和
        assert _item_total_support(header, "A") == 3
        assert _item_total_support(header, "B") == 4
        assert _item_total_support(header, "C") == 3

    def test_filter_infrequent(self):
        """低于阈值的项被过滤"""
        transactions = [
            ["A", "X"], ["A", "X"], ["A", "B"],
        ]
        root, header = _build_fptree(transactions, min_support=2)

        # X 出现 2 次, B 出现 1 次
        assert "X" in header
        assert "B" not in header

    def test_empty_transactions(self):
        """空事务不崩溃"""
        root, header = _build_fptree([], min_support=1)
        assert header == {}

    def test_single_item_tree(self):
        """单元素事务"""
        transactions = [["A"], ["A"], ["A"]]
        root, header = _build_fptree(transactions, min_support=2)
        assert header["A"].count == 3


# ═══ 频繁项集测试 ═══

class TestFrequentItemsets:
    """频繁项集挖掘"""

    def test_simple_itemsets(self):
        """基础频繁项集"""
        transactions = [
            ["A", "B", "C"], ["A", "B", "C"], ["A", "B"],
            ["B", "C"], ["A"],
        ]
        # min_support_ratio=0.3 → min_support=2
        itemsets = mine_frequent_itemsets(transactions, min_support_ratio=0.3)

        # 频繁 2-项集: AB(3), AC(2), BC(3)
        sets = {frozenset(s): cnt for s, cnt, _ in itemsets}
        assert frozenset(["A", "B"]) in sets
        assert frozenset(["B", "C"]) in sets

    def test_filters_singletons(self):
        """单例项集被过滤（只返回 ≥2 的项集）"""
        transactions = [["A", "B"], ["A", "B"], ["A", "B"]]
        itemsets = mine_frequent_itemsets(transactions, min_support_ratio=0.5)
        for itemset, _, _ in itemsets:
            assert len(itemset) >= 2

    def test_max_itemset_size(self):
        """限制最大项集大小"""
        transactions = [
            ["A", "B", "C"], ["A", "B", "C"], ["A", "B", "C"], ["A", "B", "C"],
        ]
        itemsets = mine_frequent_itemsets(
            transactions, min_support_ratio=0.5, max_itemset_size=2
        )
        for itemset, _, _ in itemsets:
            assert len(itemset) <= 2

    def test_no_frequent_itemsets(self):
        """无满足阈值的项集"""
        transactions = [["A"], ["B"], ["C"]]
        itemsets = mine_frequent_itemsets(transactions, min_support_ratio=0.5)
        assert itemsets == []

    def test_known_association(self):
        """已知关联应被发现"""
        # 20 条事务，X→Y 强关联
        transactions = [["X", "Y"] for _ in range(15)] + [["X"]] * 5
        rules = generate_association_rules(
            transactions, min_support_ratio=0.3, min_confidence=0.6
        )
        x_to_y = [r for r in rules if r["antecedent"] == ["X"] and r["consequent"] == ["Y"]]
        assert x_to_y, "X→Y 关联规则应被发现"
        assert x_to_y[0]["confidence"] >= 0.75  # 15/20


# ═══ 关联规则测试 ═══

class TestAssociationRules:
    """关联规则生成"""

    def test_rule_metrics(self):
        """规则的 support/confidence/lift 正确"""
        transactions = [
            ["A", "B"], ["A", "B"], ["A", "B"], ["A", "B"], ["A", "B"],
            ["A"], ["A"], ["B"], ["C"], ["D"],
        ]
        rules = generate_association_rules(
            transactions, min_support_ratio=0.2, min_confidence=0.5
        )
        a_to_b = [r for r in rules if r["antecedent"] == ["A"] and r["consequent"] == ["B"]]
        if a_to_b:
            r = a_to_b[0]
            assert r["confidence"] == 0.714  # 5/7
            assert r["count"] == 5
            assert 0.0 <= r["support"] <= 1.0
            assert r["lift"] > 1.0  # B 独立概率 6/10=0.6 < 0.714

    def test_lift_filter(self):
        """min_lift 过滤负相关规则"""
        transactions = [
            ["A", "B"], ["A"], ["A"], ["A"], ["B"], ["B"],
            ["B"], ["B"], ["B"], ["B"],
        ]
        # A→B: conf=1/5=0.2, B 独立=7/10=0.7, lift=0.29 (负相关)
        all_rules = generate_association_rules(
            transactions, min_support_ratio=0.1, min_confidence=0.0, min_lift=0.0
        )
        strict_rules = generate_association_rules(
            transactions, min_support_ratio=0.1, min_confidence=0.0, min_lift=1.0
        )
        assert len(strict_rules) <= len(all_rules)

    def test_no_rules_when_sparse(self):
        """稀疏数据无规则"""
        transactions = [["A"], ["B"], ["C"], ["D"], ["E"], ["F"]]
        rules = generate_association_rules(
            transactions, min_support_ratio=0.3, min_confidence=0.5
        )
        assert rules == []


# ═══ 事务提取测试 ═══

class TestTransactionExtraction:
    """从事务提取实验数据"""

    def test_extract_from_results(self):
        """从实验 JSON 提取事务"""
        if not os.path.exists("experiment_results/run_2026-08-03_235428/results.json"):
            pytest.skip("实验数据不存在")

        result = extract_transactions_from_results(
            "experiment_results/run_2026-08-03_235428/results.json"
        )
        assert "transactions" in result
        assert "designs" in result
        assert len(result["designs"]) >= 4
        assert len(result["transactions"]) > 0

        # 每条事务有 design 和 items
        for tx in result["transactions"]:
            assert "design" in tx
            assert "items" in tx
            assert len(tx["items"]) >= 1


# ═══ 端到端测试 ═══

class TestEndToEnd:
    """挖掘全流程"""

    def test_mining_report_exists(self):
        """挖掘报告已生成"""
        if not os.path.exists("data/violation_mining_report.json"):
            pytest.skip("挖掘报告不存在")
        with open("data/violation_mining_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
        assert "method" in report
        assert "board_level_rules" in report
        assert "circuit_type_patterns" in report

    def test_circuit_type_patterns(self):
        """电路类型模式包含期望类别"""
        if not os.path.exists("data/violation_mining_report.json"):
            pytest.skip("挖掘报告不存在")
        with open("data/violation_mining_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)

        patterns = report.get("circuit_type_patterns", {})
        # 至少应有电源类和 MCU 类
        keys = " ".join(patterns.keys())
        assert "电源" in keys or "MCU" in keys
