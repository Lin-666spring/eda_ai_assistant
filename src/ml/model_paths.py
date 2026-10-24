"""模型产物路径解析 —— 校准产物优先。

2026-10-24（验收 P1-24）：calibrate.py 产出的 ``*_calibrated.pt`` 此前运行时
无人加载——校准做了等于没做。所有运行时加载点改经 :func:`calibrated_first`：
校准产物在场则优先，缺失则回落基础模型（打包/裁剪环境无校准产物）。
"""

from __future__ import annotations

from pathlib import Path


def calibrated_first(base_path: str) -> str:
    """返回应加载的模型路径：``*_calibrated.pt`` 存在则优先，否则 ``base_path``。"""
    p = Path(base_path)
    calibrated = p.with_name(f"{p.stem}_calibrated{p.suffix}")
    return str(calibrated) if calibrated.is_file() else base_path
