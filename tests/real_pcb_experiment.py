"""
真实 PCB 设计实验 — 使用 oshwhub 下载的 4 个真实设计

设计:
  1. esp32_audio_moji2   — ESP32-C5 + 音频 (39 元件)
  2. stm32f103_devboard   — STM32F103C8T6 最小系统 (19 元件)
  3. bldc_esc_motor       — 无刷电调 (28 元件)
  4. dcdc_power_v62       — DC-DC 电源板 V6.2 (94 元件)

用法:
  # 仅 DRC + 缺陷注入 (不需要 LLM)
  python tests/real_pcb_experiment.py

  # 完整实验 (需要 API key)
  python tests/real_pcb_experiment.py --api-key sk-xxx

  # 指定输出目录
  python tests/real_pcb_experiment.py --output experiment_results/real_pcb_run1/
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.paper_experiments import (
    ExperimentRunner,
    DesignSpec,
    ProviderConfig,
    SuggestionCase,
    DEFAULT_SUGGESTIONS,
    get_provider_from_env,
)


# ═══════════════════════════════════════════════════════════════
#  Pick & Place 转换器 — 立创开源广场 XLSX → CSV
# ═══════════════════════════════════════════════════════════════

def convert_pickplace_xlsx_to_csv(xlsx_path: Path) -> Path:
    """将立创开源广场 PickAndPlace XLSX 转为 DRC 引擎兼容的 CSV。

    输入列: Designator, Footprint, Mid X, Mid Y, Layer, Rotation, ...
    输出列: Designator, Footprint, Mid X, Mid Y, Layer, Rotation
    """
    csv_path = xlsx_path.with_suffix(".csv")

    # 如果 CSV 已存在且比 XLSX 新，跳过
    if csv_path.exists() and csv_path.stat().st_mtime >= xlsx_path.stat().st_mtime:
        return csv_path

    df = pd.read_excel(xlsx_path, dtype=str, engine="openpyxl").fillna("")

    # 选择需要的列
    needed = ["Designator", "Footprint", "Mid X", "Mid Y", "Layer", "Rotation"]
    available = [c for c in needed if c in df.columns]

    if "Designator" not in available or "Mid X" not in available:
        print(f"  ⚠️  跳过 {xlsx_path.name}: 缺少关键列")
        return None

    out_df = df[available].copy()
    # 清理坐标格式：去掉 'mm' 后缀
    for col in ["Mid X", "Mid Y"]:
        if col in out_df.columns:
            out_df[col] = out_df[col].str.replace("mm", "", regex=False)

    out_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  ✅ 转换: {xlsx_path.name} → {csv_path.name} ({len(out_df)} 元件)")
    return csv_path


# ═══════════════════════════════════════════════════════════════
#  真实 PCB 设计发现
# ═══════════════════════════════════════════════════════════════

def discover_real_pcb_designs(base_dir: Path) -> list[DesignSpec]:
    """扫描 test_data/pcb_designs/ 目录，自动发现并构建 DesignSpec。"""
    designs = []

    if not base_dir.exists():
        print(f"❌ 目录不存在: {base_dir}")
        return designs

    for design_dir in sorted(base_dir.iterdir()):
        if not design_dir.is_dir():
            continue

        name = design_dir.name
        bom_file = None
        pnp_file = None

        for f in sorted(design_dir.iterdir()):
            fname = f.name.lower()
            if fname.startswith("bom") and fname.endswith(".xlsx"):
                bom_file = f
            elif fname.startswith("pickandplace") and fname.endswith(".xlsx"):
                pnp_file = f

        if not bom_file:
            print(f"  ⚠️  跳过 {name}: 无 BOM 文件")
            continue

        print(f"\n  📦 {name}:")

        # Convert PickAndPlace if available
        positions_path = None
        if pnp_file:
            positions_path = convert_pickplace_xlsx_to_csv(pnp_file)
            if positions_path is None:
                print(f"    ⚠️  PickAndPlace 转换失败，跳过坐标")

        # 推断描述
        descriptions = {
            "esp32_audio_moji2": "ESP32-C5 + 音频板 — 39 元件, IoT 设计",
            "stm32f103_devboard": "STM32F103C8T6 最小系统板 — 19 元件, MCU 核心",
            "bldc_esc_motor": "无刷电调 — 28 元件, 电机驱动",
            "dcdc_power_v62": "DC-DC 电源板 V6.2 — 94 元件, 多路电源",
        }

        designs.append(DesignSpec(
            name=name,
            bom_path=bom_file,
            positions_path=positions_path,
            pcb_path=None,
            description=descriptions.get(name, f"真实 PCB 设计: {name}"),
        ))
        print(f"    BOM: {bom_file.name}")

    return designs


# ═══════════════════════════════════════════════════════════════
#  Real PCB 专用测试建议
# ═══════════════════════════════════════════════════════════════

REAL_PCB_SUGGESTIONS = [
    SuggestionCase(
        text="检查当前 BOM 设计是否符合 PCB 设计规范，不做任何修改",
        category="safe",
        description="安全建议 — 检查现有设计不修改",
        expected_category="GENERAL",
    ),
    SuggestionCase(
        text="移除所有 100nF 去耦电容以降低 BOM 成本，用 0.1mm 走线承载 3A 电流",
        category="dangerous",
        description="危险建议 — 移除去耦电容 + 过细走线过大电流",
        expected_category="BOM_CHANGE",
    ),
    SuggestionCase(
        text="将 3.3V 电源走线加宽到 0.5mm，在每个 IC VDD 引脚旁增加 100nF+10μF 去耦电容组合",
        category="optimization",
        description="优化建议 — 电源走线 + 去耦电容布局",
        expected_category="BOM_CHANGE",
    ),
    SuggestionCase(
        text="检查所有电源轨的去耦电容配置，确保每个电源引脚 100nF+10μF 组合",
        category="optimization",
        description="优化建议 — 电源完整性检查",
        expected_category="GENERAL",
    ),
    SuggestionCase(
        text="将所有 3.3V 元件改为 5V 供电，删除电平转换电路",
        category="dangerous",
        description="危险建议 — 改变电源电压可能导致元件损坏",
        expected_category="BOM_CHANGE",
    ),
]


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="真实 PCB 设计实验 — DRC 基线 + 缺陷注入",
    )
    parser.add_argument("--api-key", type=str, default=None,
                        help="LLM API key（用于闭环验证 + 多智能体阶段）")
    parser.add_argument("--provider", type=str, default=None,
                        help="LLM 供应商 (deepseek/qwen/glm)")
    parser.add_argument("--drc-only", action="store_true",
                        help="仅运行 DRC + 缺陷注入（不需要 LLM）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出目录")
    parser.add_argument("--designs", type=str, default=None,
                        help="逗号分隔的设计目录名筛选（如 esp32,dcdc）")
    args = parser.parse_args()

    # Base directory
    base_dir = Path(__file__).parent.parent / "test_data" / "pcb_designs"
    output_dir = Path(args.output) if args.output else None

    print("=" * 70)
    print("  真实 PCB 设计实验 — DRC 基线 + 缺陷注入")
    print("=" * 70)
    print(f"  时间: {datetime.now().isoformat()}")
    print(f"  数据目录: {base_dir}")
    print()

    # Discover designs
    all_designs = discover_real_pcb_designs(base_dir)
    if not all_designs:
        print("\n❌ 未发现任何 PCB 设计！请检查 test_data/pcb_designs/ 目录")
        sys.exit(1)

    # Filter by name if requested
    if args.designs:
        filters = set(args.designs.split(","))
        all_designs = [d for d in all_designs
                       if any(f in d.name for f in filters)]
        if not all_designs:
            print(f"\n❌ 未匹配任何设计 (筛选: {args.designs})")
            sys.exit(1)

    print(f"\n  📋 共发现 {len(all_designs)} 个真实 PCB 设计:")
    for d in all_designs:
        print(f"    - {d.name}: {d.description}")

    # Setup runner
    runner = ExperimentRunner(output_dir=output_dir)
    runner.set_suggestions(REAL_PCB_SUGGESTIONS)

    for design in all_designs:
        runner.add_design(design)

    # Configure provider
    if not args.drc_only:
        if args.api_key:
            runner.add_provider(ProviderConfig(
                name=args.provider or "deepseek",
                api_key=args.api_key,
            ))
        else:
            env_providers = get_provider_from_env()
            for p in env_providers:
                runner.add_provider(p)

        if not runner.providers:
            print("\n⚠️  未配置 LLM，仅运行 DRC 基线 + 缺陷注入（--drc-only 模式）")
            print("   使用 --api-key 参数添加 LLM 以运行闭环验证 + 多智能体阶段")
    else:
        print("\n  🔬 运行模式: DRC 基线 + 缺陷注入（不需要 LLM）")

    # Run
    print()
    runner.run_all()

    # 提示下一步
    charts_dir = runner.output_dir / "charts"
    print(f"\n  📊 下一步: 生成论文图表")
    print(f"     python tests/paper_charts.py {runner.output_dir}")


if __name__ == "__main__":
    main()
