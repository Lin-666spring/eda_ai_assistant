# -*- coding: utf-8 -*-
"""生成软著登记用《源程序》PDF（前30页 + 后30页，每页50行，页眉+页码）。

用法:
    python scripts/gen_copyright_source_pdf.py

产物: 软著材料/源程序_*.pdf 及 文件清单/行数统计（打印到控制台）。
名称/版本/日期改下方常量后重跑即可。
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ===== 申请信息（改这里） =====
SOFTWARE_NAME = "智绘PCB——AI智能PCB设计助手"
VERSION = "V1.0"
COMPLETION_DATE = "2026-10-13"
# =============================

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "软著材料"

LINES_PER_PAGE = 50
FIRST_PAGES = 30
LAST_PAGES = 30
MAX_LINE_WIDTH = 100  # 显示宽度上限（ASCII=1，CJK=2），超宽折行

# 程序正文文件清单：入口 → 后端 → 前端 → 插件；排除测试/vendor/构建产物
INCLUDE_PATTERNS = [
    ("main.py", True),
    ("src/**/*.py", True),
    ("web/index.html", True),
    ("web/js/**/*.js", True),
    ("web/css/**/*.css", True),
    ("lceda_plugin/src/**/*.ts", True),
]
EXCLUDE_PARTS = {"tests", "test", "__pycache__", "vendor", "dist", "node_modules", "build"}
EXCLUDE_SUFFIXES = {".min.js"}


def collect_files() -> list[Path]:
    seen: list[Path] = []
    for pattern, _ in INCLUDE_PATTERNS:
        for p in sorted(REPO.glob(pattern)):
            rel = p.relative_to(REPO)
            if any(part in EXCLUDE_PARTS for part in rel.parts):
                continue
            if any(rel.name.endswith(suf) for suf in EXCLUDE_SUFFIXES):
                continue
            if p not in seen:
                seen.append(p)
    return seen


def read_lines(path: Path) -> list[str]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    out = []
    for line in text.splitlines():
        out.append(line.replace("\t", "    ").rstrip())
    return out


def display_width(s: str) -> int:
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in s)


def wrap_line(line: str) -> list[str]:
    if display_width(line) <= MAX_LINE_WIDTH:
        return [line]
    parts, cur, w = [], [], 0
    for ch in line:
        cw = 2 if ord(ch) > 0x2E80 else 1
        if w + cw > MAX_LINE_WIDTH:
            parts.append("".join(cur))
            cur, w = [ch], cw
        else:
            cur.append(ch)
            w += cw
    if cur:
        parts.append("".join(cur))
    return parts


def build_listing(files: list[Path]) -> tuple[list[str], int]:
    """返回(全部行, 总行数)。每文件前加一行路径注释作分隔。"""
    lines: list[str] = []
    total = 0
    for p in files:
        rel = p.relative_to(REPO).as_posix()
        comment = "# " if rel.endswith((".py",)) else ("// " if rel.endswith((".js", ".ts")) else "<!-- ")
        body = read_lines(p)
        total += len(body)
        if rel.endswith(".html"):
            lines.append(f"<!-- ==== {rel} ==== -->")
        else:
            lines.append(f"{comment}==== {rel} ====")
        lines.extend(body)
    return lines, total


def paginate(lines: list[str]) -> list[list[str]]:
    pages = [lines[i : i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    if not pages:
        pages = [["(empty)"]]
    if len(pages) > FIRST_PAGES + LAST_PAGES:
        pages = pages[:FIRST_PAGES] + pages[-LAST_PAGES:]
    return pages


def register_fonts() -> str:
    for name, path, idx in [
        ("MSYH", r"C:\Windows\Fonts\msyh.ttc", 0),
        ("MSYHBD", r"C:\Windows\Fonts\msyhbd.ttc", 0),
    ]:
        try:
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
        except Exception:
            pass
    return "MSYH"


def draw(c: canvas.Canvas, page: list[str], page_no: int, total_pages: int, font: str) -> None:
    w, h = A4
    header = f"{SOFTWARE_NAME}{VERSION} 源程序"
    c.setFont("MSYHBD", 9)
    c.drawString(15 * mm, h - 12 * mm, header)
    c.setFont(font, 9)
    c.drawRightString(w - 15 * mm, h - 12 * mm, f"第 {page_no} 页 / 共 {total_pages} 页")
    c.line(15 * mm, h - 14 * mm, w - 15 * mm, h - 14 * mm)

    y = h - 20 * mm
    line_height = (h - 20 * mm - 15 * mm) / LINES_PER_PAGE
    c.setFont(font, 7.8)
    for line in page:
        for seg in wrap_line(line) if line else [""]:
            c.drawString(15 * mm, y, seg)
            y -= line_height
            if y < 12 * mm:
                break
        if y < 12 * mm:
            break
    c.showPage()


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    files = collect_files()
    lines, total = build_listing(files)
    pages = paginate(lines)
    total_pages = len(pages)

    font = register_fonts()
    safe_name = SOFTWARE_NAME.replace("——", "-")
    out_pdf = OUT_DIR / f"源程序_{safe_name}{VERSION}.pdf"
    c = canvas.Canvas(str(out_pdf), pagesize=A4)
    for i, page in enumerate(pages, 1):
        draw(c, page, i, total_pages, font)
    c.save()

    print(f"文件数: {len(files)}")
    print(f"程序总行数(申请表“源程序量”): {total}")
    print(f"总页数: {len(lines) / LINES_PER_PAGE:.0f} -> 提交页数: {total_pages} (前{min(FIRST_PAGES, total_pages)}+后{min(LAST_PAGES, max(0, total_pages - FIRST_PAGES))})")
    print(f"产物: {out_pdf}")

    manifest = OUT_DIR / "源程序_文件清单.txt"
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f"软件全称: {SOFTWARE_NAME}软件\n版本号: {VERSION}\n开发完成日期: {COMPLETION_DATE}\n")
        f.write(f"源程序总量: {total} 行\n\n")
        for p in files:
            n = len(read_lines(p))
            f.write(f"{p.relative_to(REPO).as_posix()}  ({n} 行)\n")
    print(f"清单: {manifest}")


if __name__ == "__main__":
    main()
