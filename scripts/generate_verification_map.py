#!/usr/bin/env python
"""
AI Verification Map CLI — 从实验结果 JSON + BOM 数据生成交互式可视化仪表盘。

用法:
    # 从 results.json 生成（需要配套的 BOM + 坐标文件）
    python scripts/generate_verification_map.py \\
        --results experiment_results/run_2026-07-12_full/results.json \\
        --design-dir test_data/pcb_designs/ \\
        --output output/verification_map.html

    # 指定单个设计的 BOM 和坐标
    python scripts/generate_verification_map.py \\
        --results experiment_results/run_2026-07-12_full/results.json \\
        --bom test_data/pcb_designs/stm32f103_devboard/BOM.csv \\
        --positions test_data/pcb_designs/stm32f103_devboard/PickAndPlace.csv \\
        --design stm32f103_devboard \\
        --output output/vmap_stm32.html

    # 从已有 DRC 数据直接生成（不依赖 results.json）
    python scripts/generate_verification_map.py \\
        --bom my_bom.csv --positions my_positions.csv \\
        --output my_vmap.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.html_bom.verification_map import (
    VerificationMapGenerator,
    VerificationMapConfig,
)
from src.rules.checker import DesignRuleChecker, group_violations_by_component


def load_results_json(path: Path) -> dict:
    """Load experiment results.json."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_bom_csv(path: Path) -> list:
    """Load BOM from CSV using AppController loader."""
    from src.core.controller import AppController
    ctrl = AppController()
    ctrl.load_bom(str(path))
    return ctrl.context.bom_items


def load_positions_csv(path: Path) -> dict:
    """Load Pick & Place positions from CSV."""
    from src.core.controller import AppController
    ctrl = AppController()
    ctrl.load_positions(str(path))
    return ctrl.context.positions


def find_design_files(design_dir: Path, design_name: str) -> tuple[Optional[Path], Optional[Path]]:
    """Find BOM and positions files for a named design."""
    bom_path, pos_path = None, None

    design_subdir = design_dir / design_name
    if design_subdir.is_dir():
        for f in design_subdir.iterdir():
            name_lower = f.name.lower()
            if f.suffix.lower() in (".csv", ".xlsx"):
                if "bom" in name_lower:
                    bom_path = f
                elif "pick" in name_lower or "position" in name_lower or "pnplace" in name_lower:
                    pos_path = f

    # Fallback: search the whole design_dir
    if not bom_path:
        for f in design_dir.rglob(f"*{design_name}*"):
            if f.suffix.lower() in (".csv", ".xlsx") and "bom" in f.name.lower():
                bom_path = f
                break

    if not pos_path:
        for f in design_dir.rglob(f"*{design_name}*"):
            if f.suffix.lower() in (".csv", ".xlsx") and any(
                kw in f.name.lower() for kw in ("pick", "position", "pnplace")
            ):
                pos_path = f
                break

    return bom_path, pos_path


def build_overlay_from_results(
    results: dict,
    design_name: Optional[str] = None,
) -> dict:
    """Extract and prepare overlay data from results.json."""
    drc_results = None
    verify_list = results.get("verify_results", [])
    ma_list = results.get("ma_results", [])
    defect_list = results.get("defect_results", [])

    # Filter by design if specified
    if design_name:
        verify_list = [r for r in verify_list if r.get("design") == design_name]
        ma_list = [r for r in ma_list if r.get("design") == design_name]
        defect_list = [r for r in defect_list if r.get("design") == design_name]

    # Find matching DRC result
    for dr in results.get("drc_results", []):
        if design_name is None or dr.get("design") == design_name:
            drc_results = dr
            break

    return VerificationMapGenerator._prepare_overlay_data(
        drc_results=drc_results,
        verify_results=verify_list,
        ma_results=ma_list,
        defect_results=defect_list,
    )


def build_overlay_from_drc_only(bom_items: list, positions: dict) -> dict:
    """Build overlay data using only DRC (no experiment results)."""
    checker = DesignRuleChecker()
    violations = checker.check_all(bom_items, positions)

    errors = sum(1 for v in violations if v.severity.value == "error")
    warnings = sum(1 for v in violations if v.severity.value == "warning")
    infos = sum(1 for v in violations if v.severity.value == "info")
    by_rule: dict[str, int] = {}
    for v in violations:
        by_rule[v.rule_name] = by_rule.get(v.rule_name, 0) + 1
    by_component = group_violations_by_component(violations)

    drc = {
        "design": "standalone",
        "total_violations": len(violations),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "violations_by_rule": dict(sorted(by_rule.items(), key=lambda x: -x[1])),
        "violations_by_component": by_component,
    }

    return VerificationMapGenerator._prepare_overlay_data(
        drc_results=drc,
        verify_results=[],
        ma_results=[],
        defect_results=[],
    )


def main():
    parser = argparse.ArgumentParser(
        description="AI Verification Map — 交互式 PCB 验证可视化仪表盘生成器"
    )
    parser.add_argument("--results", type=str, default=None,
                       help="实验结果 results.json 路径")
    parser.add_argument("--design", type=str, default=None,
                       help="要可视化的设计名称（如 stm32f103_devboard），不指定则用第一个")
    parser.add_argument("--design-dir", type=str, default=None,
                       help="PCB 设计目录（含 BOM + PickAndPlace 子目录）")
    parser.add_argument("--bom", type=str, default=None,
                       help="BOM CSV 文件路径")
    parser.add_argument("--positions", type=str, default=None,
                       help="Pick & Place 坐标 CSV 文件路径")
    parser.add_argument("--output", type=str, default="output/verification_map.html",
                       help="输出 HTML 文件路径 (默认: output/verification_map.html)")
    parser.add_argument("--title", type=str, default="AI Verification Map",
                       help="页面标题")
    parser.add_argument("--dark", action="store_true", default=True,
                       help="暗色模式 (默认开启)")
    args = parser.parse_args()

    # ── Load data ──
    bom_items = []
    positions = {}
    overlay_data = {}

    if args.bom:
        bom_path = Path(args.bom)
        if not bom_path.exists():
            print(f"❌ BOM 文件不存在: {bom_path}")
            sys.exit(1)
        print(f"📦 加载 BOM: {bom_path}")
        bom_items = load_bom_csv(bom_path)

    if args.positions:
        pos_path = Path(args.positions)
        if not pos_path.exists():
            print(f"❌ 坐标文件不存在: {pos_path}")
            sys.exit(1)
        print(f"📍 加载坐标: {pos_path}")
        positions = load_positions_csv(pos_path)

    if args.results:
        results_path = Path(args.results)
        if not results_path.exists():
            print(f"❌ 结果文件不存在: {results_path}")
            sys.exit(1)
        print(f"📊 加载实验结果: {results_path}")
        results = load_results_json(results_path)

        design_name = args.design
        if not design_name and results.get("drc_results"):
            design_name = results["drc_results"][0]["design"]
            print(f"🎯 自动选择设计: {design_name}")

        # Try to find BOM/positions from design-dir if not explicitly given
        if not bom_items and args.design_dir and design_name:
            design_dir = Path(args.design_dir)
            bom_found, pos_found = find_design_files(design_dir, design_name)
            if bom_found:
                print(f"📦 自动定位 BOM: {bom_found}")
                bom_items = load_bom_csv(bom_found)
            if pos_found:
                print(f"📍 自动定位坐标: {pos_found}")
                positions = load_positions_csv(pos_found)

        overlay_data = build_overlay_from_results(results, design_name)

    elif bom_items:
        # DRC-only mode: generate overlay from BOM alone
        print("🔍 运行 DRC 检查（无实验结果数据）...")
        overlay_data = build_overlay_from_drc_only(bom_items, positions)

    if not bom_items:
        print("❌ 需要提供 --bom 文件或 --results + --design-dir")
        print("   示例: python scripts/generate_verification_map.py --bom my_bom.csv --positions my_pos.csv")
        sys.exit(1)

    # ── Generate ──
    config = VerificationMapConfig(
        title=args.title,
        dark_mode=args.dark,
    )
    generator = VerificationMapGenerator(config=config)

    output_path = args.output
    html = generator.generate(
        bom_items=bom_items,
        positions=positions,
        overlay_data=overlay_data,
        output_path=output_path,
    )

    print(f"✅ AI Verification Map 已生成: {output_path}")
    print(f"   文件大小: {len(html):,} 字符")
    print(f"   在浏览器中打开查看: file:///{Path(output_path).resolve()}")


if __name__ == "__main__":
    main()
