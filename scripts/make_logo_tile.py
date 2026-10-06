#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把生图工具产出的 logo 处理成启动界面能直接用的方块图。

用法:
    python scripts/make_logo_tile.py "C:/Users/lin/Downloads/logo.jpeg"
    python scripts/make_logo_tile.py logo.jpeg --out web/img/logo-mark.png --size 1024

只做取景与格式，不改画面内容:
  1. 找出白色标记的包围盒，以它的中心裁一个「不越界的最大正方形」
     （生图常见的「标记偏左上」在这里被摆正 —— 64px 显示时偏几个像素就很明显）；
  2. LANCZOS 缩放到目标边长；
  3. 存 PNG（JPEG 的压缩噪点在深色底上会看出来）。

⚠️ 圆角由 CSS 的 border-radius 负责，所以这张图**必须**是直角满幅：
   自己在图里画圆角，两层圆角对不齐会露出底色。
"""

import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("需要 pillow + numpy：pip install pillow numpy")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "web" / "img" / "logo-mark.png"
WHITE_THRESHOLD = 180          # 标记是纯白，背景是饱和蓝（红通道很低）


def mark_bbox(rgb: "np.ndarray") -> tuple[int, int, int, int]:
    """白色标记的包围盒 (x0, y0, x1, y1)。"""
    mask = ((rgb[..., 0] > WHITE_THRESHOLD)
            & (rgb[..., 1] > WHITE_THRESHOLD)
            & (rgb[..., 2] > WHITE_THRESHOLD))
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise SystemExit("图里没找到白色标记 —— 是不是标记不是白色？")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def make_tile(src_path: Path, out_path: Path, size: int = 1024) -> dict:
    src = Image.open(src_path).convert("RGB")
    w, h = src.size
    x0, y0, x1, y1 = mark_bbox(np.asarray(src).astype(np.int16))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    # 以标记中心为心的最大内接正方形（越界就裁到边界为止）
    side = int(2 * min(cx, w - cx, cy, h - cy))
    box = (round(cx - side / 2), round(cy - side / 2),
           round(cx + side / 2), round(cy + side / 2))
    tile = src.crop(box).resize((size, size), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tile.save(out_path, optimize=True)

    px = np.asarray(tile).astype(np.int16)
    mx0, my0, mx1, my1 = mark_bbox(px)
    return {
        "src_size": (w, h),
        "mark_bbox": (x0, y0, x1, y1),
        "mark_offset_from_center": (round(cx - w / 2), round(cy - h / 2)),
        "crop_box": box,
        "mark_size_in_tile": (mx1 - mx0 + 1, my1 - my0 + 1),
        "mark_height_ratio": round((my1 - my0 + 1) / size, 3),
        "file_kb": round(out_path.stat().st_size / 1024),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="生图 logo → 启动界面用的方块图")
    ap.add_argument("source", help="生图产出的图片（jpeg/png 都行）")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"输出路径（默认 {DEFAULT_OUT}）")
    ap.add_argument("--size", type=int, default=1024, help="输出边长，默认 1024")
    args = ap.parse_args()

    info = make_tile(Path(args.source), Path(args.out), args.size)
    print(f"源图 {info['src_size'][0]}x{info['src_size'][1]}，"
          f"标记包围盒 {info['mark_bbox']}，"
          f"相对画面中心偏移 {info['mark_offset_from_center']}")
    print(f"裁切 {info['crop_box']} → {args.size}x{args.size}  "
          f"标记 {info['mark_size_in_tile'][0]}x{info['mark_size_in_tile'][1]}px"
          f"（占高 {info['mark_height_ratio']:.0%}）")
    print(f"已写入 {args.out}  ({info['file_kb']} KB)")


if __name__ == "__main__":
    main()
