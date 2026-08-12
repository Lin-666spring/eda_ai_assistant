"""跨设计违规关联规则挖掘 — FP-Growth + 关联规则

从多块 PCB 的 DRC 违规数据中自动发现设计知识：
  1. 规则共现模式（哪些违规总是同时出现）
  2. 电路类型 → 违规模式（什么电路容易犯什么错）
  3. 可解释的关联规则（support / confidence / lift）

算法参考:
  Han et al. (2000) "Mining Frequent Patterns without Candidate Generation" (FP-Growth)

使用方式:
    # 从实验 JSON 提取事务
    python src/ml/violation_mining.py --results experiment_results/run_2026-08-03_235428/results.json

    # 直接跑真实板 DRC（更完整）
    python src/ml/violation_mining.py --boards test_data/pcb_designs/

    # 仅输出报告
    python src/ml/violation_mining.py --report-only

输出:
    data/violation_mining_report.json — 挖掘报告
    data/violation_association_rules.md — 可读规则表（论文用）
"""

import argparse
import json
import logging
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from scipy.stats import fisher_exact
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ═══ FP-Growth 实现 ═══

class FPTreeNode:
    """FP 树节点"""

    __slots__ = ("item", "count", "parent", "children", "node_link")

    def __init__(self, item: str, count: int, parent: "Optional[FPTreeNode]" = None):
        self.item = item
        self.count = count
        self.parent = parent
        self.children: dict[str, FPTreeNode] = {}
        self.node_link: Optional[FPTreeNode] = None


def _build_fptree(
    transactions: list[list[str]], min_support: int
) -> tuple[FPTreeNode, dict[str, FPTreeNode]]:
    """构建 FP 树

    Returns:
        (root, header_table)
    """
    # 1. 统计单项支持度
    item_counts: Counter = Counter()
    for tx in transactions:
        item_counts.update(set(tx))  # 去重计次

    # 过滤低于阈值的项
    freq_items = {item: cnt for item, cnt in item_counts.items() if cnt >= min_support}
    if not freq_items:
        return FPTreeNode(None, 0), {}

    # 2. 按支持度降序排列（作为项头表顺序）
    sorted_items = sorted(freq_items, key=lambda it: (-freq_items[it], it))
    item_rank = {it: i for i, it in enumerate(sorted_items)}

    # 3. 构建 FP 树
    root = FPTreeNode(None, 0)
    header_table: dict[str, FPTreeNode] = {}

    for tx in transactions:
        # 过滤 + 排序事务项
        filtered = sorted(
            [it for it in set(tx) if it in freq_items],
            key=lambda it: item_rank[it],
        )
        if not filtered:
            continue

        # 插入树
        current = root
        for item in filtered:
            if item in current.children:
                current.children[item].count += 1
                current = current.children[item]
            else:
                new_node = FPTreeNode(item, 1, current)
                current.children[item] = new_node
                # 更新头表链
                if item in header_table:
                    node = header_table[item]
                    while node.node_link:
                        node = node.node_link
                    node.node_link = new_node
                else:
                    header_table[item] = new_node
                current = new_node

    return root, header_table


def _item_total_support(header_table: dict[str, FPTreeNode], item: str) -> int:
    """沿 node_link 链求和，得到 item 的总支持度"""
    total = 0
    node = header_table[item]
    while node:
        total += node.count
        node = node.node_link
    return total


def _mine_patterns(
    header_table: dict[str, FPTreeNode],
    prefix: list[str],
    min_support: int,
    patterns: list[tuple[list[str], int]],
) -> None:
    """递归挖掘条件模式基"""
    # 按支持度降序遍历头表项
    items = sorted(
        header_table,
        key=lambda it: _item_total_support(header_table, it),
        reverse=True,
    )

    for item in items:
        new_prefix = prefix + [item]
        node = header_table[item]
        support = _item_total_support(header_table, item)
        patterns.append((new_prefix, support))

        # 收集条件模式基（所有前缀路径）
        cond_patterns = []
        curr = node
        while curr:
            prefix_path = []
            p = curr.parent
            while p and p.item is not None:
                prefix_path.append(p.item)
                p = p.parent
            if prefix_path:
                cond_patterns.extend([prefix_path] * curr.count)
            curr = curr.node_link

        # 递归构建条件 FP 树
        if cond_patterns:
            cond_root, cond_header = _build_fptree(cond_patterns, min_support)
            if cond_header:
                _mine_patterns(cond_header, new_prefix, min_support, patterns)


def mine_frequent_itemsets(
    transactions: list[list[str]],
    min_support_ratio: float = 0.2,
    max_itemset_size: int = 3,
) -> list[tuple[frozenset, int, float]]:
    """挖掘频繁项集

    Returns:
        [(itemset, support_count, support_ratio), ...] 按支持度降序
    """
    n = len(transactions)
    if n == 0:
        return []

    min_support = max(1, int(min_support_ratio * n))
    logger.info("事务数=%d, min_support=%d (%.0f%%)",
                n, min_support, min_support_ratio * 100)

    root, header_table = _build_fptree(transactions, min_support)
    if not header_table:
        logger.info("无满足阈值的频繁项集")
        return []

    patterns: list[tuple[list[str], int]] = []
    _mine_patterns(header_table, [], min_support, patterns)

    # 过滤大小并转换为 frozenset
    itemsets = []
    for itemset, count in patterns:
        if len(itemset) > max_itemset_size:
            continue
        if len(itemset) < 2:
            continue
        itemsets.append((frozenset(itemset), count, count / n))

    # 去重 + 排序
    seen = set()
    unique = []
    for itemset, count, ratio in sorted(itemsets, key=lambda x: -x[1]):
        if itemset not in seen:
            seen.add(itemset)
            unique.append((itemset, count, ratio))

    return unique


def _fisher_significance(
    antecedent: frozenset,
    consequent: frozenset,
    transactions: list[list[str]],
) -> Optional[float]:
    """Fisher 精确检验：关联是否统计显著

    2×2 列联表:
                consequent=True  consequent=False
    ant=True      a                 b
    ant=False     c                 d

    Returns:
        p-value（单尾），数据不足时 None
    """
    if not _HAS_SCIPY:
        return None

    tx_sets = [set(t) for t in transactions]
    n = len(tx_sets)

    a = sum(1 for s in tx_sets if antecedent.issubset(s) and consequent.issubset(s))
    b = sum(1 for s in tx_sets if antecedent.issubset(s) and not consequent.issubset(s))
    c = sum(1 for s in tx_sets if not antecedent.issubset(s) and consequent.issubset(s))
    d = n - a - b - c

    if a == 0:
        return None

    # 单尾：检验"前提与结果正相关"（alternative='greater'）
    try:
        odds_ratio, p_value = fisher_exact(
            [[a, b], [c, d]], alternative="greater"
        )
        return float(p_value)
    except Exception:
        return None


def generate_association_rules(
    transactions: list[list[str]],
    min_support_ratio: float = 0.15,
    min_confidence: float = 0.6,
    max_itemset_size: int = 3,
    min_lift: float = 1.0,
    max_p_value: Optional[float] = None,
) -> list[dict]:
    """生成关联规则

    Args:
        min_lift: lift 最小阈值，过滤非显著关联（lift<1 表示负相关）
        max_p_value: Fisher 精确检验 p 值阈值。非 None 时只保留显著规则
            （如 0.05）。小样本下大幅过滤虚假规则。

    Returns:
        [{"antecedent": [...], "consequent": [...],
          "support": float, "confidence": float, "lift": float,
          "count": int, "p_value": Optional[float]}, ...]
    """
    n = len(transactions)

    # 单项支持度
    item_counts: Counter = Counter()
    for tx in transactions:
        item_counts.update(set(tx))

    itemsets = mine_frequent_itemsets(
        transactions, min_support_ratio, max_itemset_size
    )

    rules = []
    for itemset, count, support in itemsets:
        items = list(itemset)
        # 生成所有 2 划分：{antecedent} -> {consequent}
        if len(items) < 2:
            continue

        for i in range(len(items)):
            antecedent = frozenset([items[i]])
            consequent = frozenset(items[:i] + items[i + 1:])

            ant_count = item_counts[items[i]]
            conf = count / ant_count if ant_count > 0 else 0.0

            if conf >= min_confidence:
                # lift = conf / support(consequent)
                cons_count = sum(
                    1 for tx in transactions
                    if consequent.issubset(set(tx))
                )
                cons_support = cons_count / n if n > 0 else 0.0
                lift = conf / cons_support if cons_support > 0 else 0.0

                if lift >= min_lift:
                    p_value = _fisher_significance(antecedent, consequent, transactions)
                    if max_p_value is not None and p_value is not None:
                        if p_value > max_p_value:
                            continue
                    rules.append({
                        "antecedent": list(antecedent),
                        "consequent": list(consequent),
                        "support": round(support, 3),
                        "confidence": round(conf, 3),
                        "lift": round(lift, 3),
                        "count": int(count),
                        "p_value": round(p_value, 5) if p_value is not None else None,
                    })

    # 去重 + 按 lift 降序
    seen = set()
    unique_rules = []
    for r in sorted(rules, key=lambda x: -x["lift"]):
        key = (tuple(r["antecedent"]), tuple(r["consequent"]))
        if key not in seen:
            seen.add(key)
            unique_rules.append(r)

    return unique_rules


# ═══ 事务提取 ═══

def extract_transactions_from_results(results_path: str) -> dict:
    """从实验 JSON 提取事务

    Returns:
        {
            "transactions": [{"design": str, "items": [...], "level": "board|component"}, ...],
            "designs": [str, ...],
        }
    """
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    transactions = []
    designs = []

    for d in data.get("drc_results", []):
        design = d.get("design", "unknown")
        designs.append(design)

        # Board 级：该板所有触发规则
        board_rules = set(d.get("violations_by_rule", {}).keys())
        if board_rules:
            transactions.append({
                "design": design, "items": sorted(board_rules),
                "level": "board",
            })

        # Component 级：每个元件触发的规则集
        for comp, vlist in d.get("violations_by_component", {}).items():
            rules = {v.get("rule", "") for v in vlist if isinstance(v, dict)}
            rules.discard("")
            if len(rules) >= 2:  # 需要 ≥2 规则才有意义
                transactions.append({
                    "design": design, "items": sorted(rules),
                    "level": "component", "component": comp,
                })

    logger.info("提取 %d 条事务（%d 个设计）", len(transactions), len(designs))
    return {"transactions": transactions, "designs": designs}


def extract_transactions_from_boards(board_dir: str) -> dict:
    """直接运行 DRC 从真实板提取事务（更完整）"""
    import glob
    from src.core.controller import AppController
    from src.rules.checker import DesignRuleChecker

    transactions = []
    designs = []

    board_paths = sorted(Path(board_dir).glob("*/"))
    for board_path in board_paths:
        if not board_path.is_dir():
            continue
        bom = glob.glob(str(board_path / "BOM*.xlsx"))
        if not bom:
            continue
        design = board_path.name
        designs.append(design)

        try:
            ctrl = AppController()
            ctrl.load_bom(bom[0])
            violations = DesignRuleChecker().check_all(
                ctrl.context.bom_items,
                ctrl.context.positions,
                pcb_data=ctrl.context.pcb_data,
            )
        except Exception as e:
            logger.warning("跳过 %s: %s", design, e)
            continue

        # Board 级
        board_rules = set(v.rule_name for v in violations)
        if board_rules:
            transactions.append({
                "design": design, "items": sorted(board_rules),
                "level": "board",
            })

        # Component 级
        from src.rules.checker import RuleViolation
        comp_groups: dict[str, set] = defaultdict(set)
        for v in violations:
            loc = v.location.split(",")[0] if v.location else ""
            if loc:
                comp_groups[loc].add(v.rule_name)
        for comp, rules in comp_groups.items():
            if len(rules) >= 2:
                transactions.append({
                    "design": design, "items": sorted(rules),
                    "level": "component", "component": comp,
                })

    logger.info("从 %d 块板提取 %d 条事务", len(designs), len(transactions))
    return {"transactions": transactions, "designs": designs}


# ═══ 报告生成 ═══

def circuit_type_patterns(transactions: list[dict], designs: list[str]) -> dict:
    """电路类型 → 违规模式分析"""
    # 基于设计名启发式分类
    def classify_design(name: str) -> str:
        name_lower = name.lower()
        if any(k in name_lower for k in ("dcdc", "power_supply", "power")):
            return "电源类"
        if any(k in name_lower for k in ("stm32", "esp32", "mcu", "devboard", "minimal")):
            return "MCU类"
        if any(k in name_lower for k in ("bldc", "motor", "esc")):
            return "电机驱动类"
        if "bad" in name_lower:
            return "缺陷注入"
        if "audio" in name_lower:
            return "音频类"
        return "其他"

    type_tx: dict[str, list] = defaultdict(list)
    for tx in transactions:
        if tx["level"] == "board":
            type_tx[classify_design(tx["design"])].append(tx["items"])

    patterns = {}
    for ctype, items_list in type_tx.items():
        if not items_list:
            continue
        # 每类电路所有触发规则的频率
        rule_freq: Counter = Counter()
        for items in items_list:
            rule_freq.update(items)
        total = len(items_list)
        top_rules = [
            {"rule": rule, "occurrence": cnt, "ratio": round(cnt / total, 3)}
            for rule, cnt in rule_freq.most_common(8)
        ]
        patterns[ctype] = {
            "board_count": total,
            "top_rules": top_rules,
        }

    return patterns


def format_rules_markdown(rules: list[dict], title: str = "关联规则") -> str:
    """格式化规则表为 Markdown"""
    lines = [
        f"## {title}",
        "",
        "| 前提规则 | 结果规则 | 支持度 | 置信度 | Lift | 次数 |",
        "|---------|---------|--------|--------|------|------|",
    ]
    for r in rules:
        ant = " + ".join(r["antecedent"])
        cons = " + ".join(r["consequent"])
        lines.append(
            f"| {ant} | {cons} | {r['support']:.3f} | "
            f"{r['confidence']:.3f} | {r['lift']:.3f} | {r['count']} |"
        )
    if not rules:
        lines.append("| (无规则) | | | | | |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="跨设计违规关联规则挖掘")
    parser.add_argument("--results", type=str, default=None,
                        help="实验 JSON 路径（提取事务）")
    parser.add_argument("--boards", type=str, default=None,
                        help="真实板目录（直接跑 DRC）")
    parser.add_argument("--min-support", type=float, default=0.15,
                        help="最小支持度 (default: 0.15)")
    parser.add_argument("--min-confidence", type=float, default=0.6,
                        help="最小置信度 (default: 0.6)")
    parser.add_argument("--max-itemset", type=int, default=3,
                        help="最大项集大小 (default: 3)")
    parser.add_argument("--min-lift", type=float, default=1.2,
                        help="最小 lift，过滤非显著关联 (default: 1.2)")
    parser.add_argument("--p-value", type=float, default=0.05,
                        help="Fisher 检验 p 值阈值 (default: 0.05, 设为 1 关闭)")
    parser.add_argument("--report-only", action="store_true",
                        help="仅读取已有报告")
    args = parser.parse_args()

    if args.report_only:
        with open("data/violation_mining_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # ── 提取事务 ──
    if args.boards:
        extraction = extract_transactions_from_boards(args.boards)
    elif args.results:
        extraction = extract_transactions_from_results(args.results)
    else:
        # 默认：真实板 + 实验
        default_results = "experiment_results/run_2026-08-03_235428/results.json"
        if os.path.exists(default_results):
            extraction = extract_transactions_from_results(default_results)
        else:
            logger.error("请指定 --results 或 --boards")
            sys.exit(1)

    transactions = extraction["transactions"]
    designs = extraction["designs"]

    # ── 挖掘（board 级事务）──
    board_tx = [tx["items"] for tx in transactions if tx["level"] == "board"]
    all_tx = [tx["items"] for tx in transactions]

    logger.info("Board 级事务: %d, 全量事务: %d", len(board_tx), len(all_tx))

    # 小样本下 Fisher 检验阈值放宽（Bonferroni 保守校正不适用小板数）
    max_p = args.p_value
    board_rules = generate_association_rules(
        board_tx, args.min_support, args.min_confidence,
        args.max_itemset, args.min_lift, max_p
    )
    comp_rules = generate_association_rules(
        all_tx, args.min_support, args.min_confidence,
        args.max_itemset, args.min_lift, max_p
    )

    # ── 电路类型模式 ──
    patterns = circuit_type_patterns(transactions, designs)

    # ── 规则统计 ──
    rule_freq_board: Counter = Counter()
    for tx in board_tx:
        rule_freq_board.update(tx)

    # ── 报告 ──
    report = {
        "timestamp": datetime.now().isoformat(),
        "method": "FP-Growth + Association Rules",
        "data": {
            "designs": designs,
            "board_transactions": len(board_tx),
            "total_transactions": len(all_tx),
        },
        "params": {
            "min_support": args.min_support,
            "min_confidence": args.min_confidence,
            "max_itemset": args.max_itemset,
            "min_lift": args.min_lift,
            "max_p_value": args.p_value,
        },
        "board_level_rules": board_rules,
        "component_level_rules": comp_rules,
        "circuit_type_patterns": patterns,
        "rule_frequency": [
            {"rule": rule, "boards": cnt}
            for rule, cnt in rule_freq_board.most_common()
        ],
    }

    Path("data").mkdir(parents=True, exist_ok=True)
    with open("data/violation_mining_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("报告已保存: data/violation_mining_report.json")

    # Markdown 输出
    md_lines = [
        "# PCB 违规模式挖掘报告",
        "",
        f"生成时间: {report['timestamp']}",
        f"方法: {report['method']}",
        "",
        f"数据: {len(designs)} 个设计, {len(board_tx)} 条板级事务, {len(all_tx)} 条元件级事务",
        "",
    ]
    md_lines.append(format_rules_markdown(board_rules, "板级关联规则"))
    md_lines.append("")
    md_lines.append(format_rules_markdown(comp_rules, "元件级关联规则"))
    md_lines.append("")

    md_lines.append("## 电路类型违规模式")
    md_lines.append("")
    for ctype, info in patterns.items():
        md_lines.append(f"### {ctype} ({info['board_count']} 板)")
        md_lines.append("")
        md_lines.append("| 规则 | 出现次数 | 比例 |")
        md_lines.append("|------|---------|------|")
        for r in info["top_rules"]:
            md_lines.append(f"| {r['rule']} | {r['occurrence']} | {r['ratio']:.0%} |")
        md_lines.append("")

    md_path = "data/violation_association_rules.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    logger.info("Markdown 已保存: %s", md_path)

    # 打印摘要
    print("\n" + "=" * 60)
    print("违规模式挖掘结果")
    print("=" * 60)
    print(f"设计数: {len(designs)}")
    print(f"板级事务: {len(board_tx)}, 元件级事务: {len(all_tx)}")
    print(f"\n板级关联规则: {len(board_rules)} 条")
    for r in board_rules[:10]:
        print(f"  {'+'.join(r['antecedent'])} → {'+'.join(r['consequent'])} "
              f"(conf={r['confidence']:.2f}, lift={r['lift']:.2f})")
    print(f"\n元件级关联规则: {len(comp_rules)} 条")
    for r in comp_rules[:10]:
        print(f"  {'+'.join(r['antecedent'])} → {'+'.join(r['consequent'])} "
              f"(conf={r['confidence']:.2f}, lift={r['lift']:.2f})")


if __name__ == "__main__":
    main()
