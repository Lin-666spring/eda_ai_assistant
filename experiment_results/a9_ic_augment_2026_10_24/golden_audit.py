# -*- coding: utf-8 -*-
"""金样触发计数审计 —— 2026-10-24 A-9 ic_* 数据增强重训批次。

复刻 tests/test_golden_snapshot.py::test_golden_trigger_counts 的计数逻辑，
把逐规则触发数落盘 golden_counts.json（供主代理对照旧 _SNAPSHOT 决定重定基线）。
用法（项目根）：
    .venv/Scripts/python.exe experiment_results/a9_ic_augment_2026_10_24/golden_audit.py
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from src.pcb.epro2_parser import Epro2Parser, bom_rows_to_items  # noqa: E402
from src.rules.checker import DesignRuleChecker  # noqa: E402

GOLDEN_DIR = PROJECT_ROOT / "test_data" / "_incoming_epro2" / "78"
OUT = Path(__file__).resolve().parent / "golden_counts.json"


def main() -> int:
    parser = Epro2Parser()
    checker = DesignRuleChecker()
    counts: Counter = Counter()
    rule_errors: Counter = Counter()
    boards = 0
    for f in sorted(GOLDEN_DIR.rglob("*.epro2")):
        try:
            pcb = parser.parse(str(f))
        except Exception:
            continue
        boards += 1
        bom_items = bom_rows_to_items(pcb.bom_items)
        positions = {
            ref: {"x": v.get("x", 0), "y": v.get("y", 0), "rotation": v.get("rotation", 0),
                  "layer": v.get("side") or v.get("layer", ""), "package": v.get("footprint_name", "")}
            for ref, v in pcb.component_positions.items()
        }
        netlist = {name: list(net.pins) for name, net in pcb.nets.items() if net.pins}
        violations = checker.check_all(bom_items, positions, netlist=netlist, pcb_data=pcb)
        for v in violations:
            counts[v.rule_name] += 1
        for e in checker.rule_errors:
            rule_errors[e["rule"]] += 1

    assert boards == 78, f"金样板数变化: {boards} != 78"
    assert not rule_errors, f"规则异常必须为 0: {dict(rule_errors)}"

    result = {"boards": boards, "counts": dict(sorted(counts.items()))}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"78 板审计完成 → {OUT}")
    print(f"规则总数: {len(counts)}, 触发总数: {sum(counts.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
