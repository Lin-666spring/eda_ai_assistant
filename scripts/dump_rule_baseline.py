"""规则输出基线 dump —— 性能优化批次的前后一致性校验工具。

对仓库内全部实验板跑一遍 DesignRuleChecker.check_all，把每块板的违规
输出（规则名/严重度/描述/位置/建议/理论）原样 dump 成 JSON。性能优化
（ML 分类缓存、空间索引）必须保持输出逐位一致：优化前 dump 一份、
优化后 dump 一份、diff 为空即通过。

板源:
  1. test_data/_incoming_epro2/78/**/*.epro2（金样语料，本地目录，缺席跳过）
  2. test_data/pcb_designs/*（真实设计: BOM xlsx + PickAndPlace csv + PCB json）

用法:
    python scripts/dump_rule_baseline.py experiment_results/rule_baseline_before.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def dump_violations(violations) -> list[dict]:
    return [
        {
            "rule": v.rule_name,
            "severity": v.severity.value,
            "description": v.description,
            "location": v.location,
            "suggestion": v.suggestion,
            "theory": v.theory,
        }
        for v in violations
    ]


def iter_golden_boards():
    """金样 .epro2 板（与 tests/test_golden_snapshot.py 同口径）。"""
    from src.pcb.epro2_parser import Epro2Parser, bom_rows_to_items
    from src.rules.checker import DesignRuleChecker

    golden_dir = PROJECT_ROOT / "test_data" / "_incoming_epro2" / "78"
    if not golden_dir.is_dir():
        print("  （金样语料不在场，跳过）")
        return 0
    parser = Epro2Parser()
    checker = DesignRuleChecker()
    n = 0
    for f in sorted(golden_dir.rglob("*.epro2")):
        try:
            pcb = parser.parse(str(f))
        except Exception:
            continue
        bom_items = bom_rows_to_items(pcb.bom_items)
        positions = {
            ref: {"x": v.get("x", 0), "y": v.get("y", 0), "rotation": v.get("rotation", 0),
                  "layer": v.get("side") or v.get("layer", ""), "package": v.get("footprint_name", "")}
            for ref, v in pcb.component_positions.items()
        }
        netlist = {name: list(net.pins) for name, net in pcb.nets.items() if net.pins}
        violations = checker.check_all(bom_items, positions, netlist=netlist, pcb_data=pcb)
        if checker.rule_errors:
            raise RuntimeError(f"{f.name}: 规则异常 {checker.rule_errors}")
        yield f"golden/{f.stem}", dump_violations(violations)
        n += 1
    if n:
        print(f"  金样板: {n}")


def iter_real_designs():
    """test_data/pcb_designs 真实设计（与 scripts/real_pcb_experiment.py 同口径）。"""
    from src.core.controller import AppController

    designs_dir = PROJECT_ROOT / "test_data" / "pcb_designs"
    for design_dir in sorted(p for p in designs_dir.iterdir() if p.is_dir()):
        bom_xlsx = next(design_dir.glob("BOM*.xlsx"), None)
        if bom_xlsx is None:
            continue
        ctrl = AppController()
        ctrl.load_bom(str(bom_xlsx))
        pos_csv = next(design_dir.glob("PickAndPlace*.csv"), None)
        if pos_csv is not None:
            ctrl.load_positions(str(pos_csv))
        pcb_json = next(design_dir.rglob("*.json"), None)
        if pcb_json is not None:
            ctrl.load_pcb(str(pcb_json))
        from src.rules.checker import DesignRuleChecker
        checker = DesignRuleChecker()
        violations = checker.check_all(
            ctrl.context.bom_items, ctrl.context.positions,
            pcb_data=ctrl.context.pcb_data)
        if checker.rule_errors:
            raise RuntimeError(f"{design_dir.name}: 规则异常 {checker.rule_errors}")
        yield f"real/{design_dir.name}", dump_violations(violations)


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        PROJECT_ROOT / "experiment_results" / "rule_baseline.json")
    t0 = time.perf_counter()
    result: dict[str, list[dict]] = {}
    for name, rows in iter_golden_boards():
        result[name] = rows
    for name, rows in iter_real_designs():
        result[name] = rows
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    n_boards = len(result)
    n_violations = sum(len(v) for v in result.values())
    print(f"dump 完成: {n_boards} 板 / {n_violations} 条违规 → {out_path.name} "
          f"({time.perf_counter() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
