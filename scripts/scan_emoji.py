"""列出一个文件里所有 emoji 及其行号/列号/上下文。

用途：把「删掉界面里的 emoji」这件事做成可核对的清单，
而不是靠 grep 出来的片段猜。改完再跑一次，输出应为空。

用法：
    python scripts/scan_emoji.py web/js
    python scripts/scan_emoji.py web src        # 目录递归
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Extended_Pictographic 覆盖绝大多数彩色 emoji；再补上
# 变体选择符（U+FE0F）与 dingbat/箭头区里常被当图标用的符号。
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF"      # 各类 pictograph（含 📊📐🔍 等）
    "\u2600-\u27BF"               # dingbats / misc symbols（✅❌⚠️✕ 等）
    "\u2B00-\u2BFF"               # 更多箭头/星形符号
    "\uFE0F"                      # variation selector-16
    "\u2705\u274C\u26A0]"         # 明确点名的几个
)

# 这些是排版符号而非 emoji，项目里当文本用（✓ ✕ → ← 等），不报。
ALLOWED = set("\u2713\u2715\u2717\u2192\u2190\u2191\u2193")


def scan(path: Path) -> int:
    hits = 0
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        found = [c for c in line if EMOJI.match(c) and c not in ALLOWED]
        if not found:
            continue
        for col, ch in enumerate(line, 1):
            if EMOJI.match(ch) and ch not in ALLOWED:
                hits += 1
                # 只打印码位与已剔除 emoji 的上下文：Windows 控制台是 GBK，
                # 直接 print emoji 会 UnicodeEncodeError。
                clean = "".join(c if not EMOJI.match(c) or c in ALLOWED else "?" for c in line.strip())
                # 控制台是 GBK：统一转义，否则行内其它非 ASCII 也会炸。
                print(
                    f"{path.as_posix()}:{lineno}:{col}  U+{ord(ch):04X}  | "
                    + clean[:100].encode("ascii", "backslashreplace").decode("ascii")
                )
    return hits


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]] or [Path("web"), Path("src")]
    exts = {".js", ".html", ".css", ".py"}
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(sorted(p for p in t.rglob("*") if p.suffix in exts))
        elif t.is_file():
            files.append(t)
        else:
            print(f"skip missing: {t}", file=sys.stderr)

    total = sum(scan(f) for f in files)
    print(f"\n-- {total} emoji occurrence(s) in {len(files)} file(s) --")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
