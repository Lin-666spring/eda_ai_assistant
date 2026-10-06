"""检查一个文件里所有非 ASCII 字符能否在 GBK 控制台安全输出。

用途：Windows 上 `python tests/ui_smoke.py | tee` 这类管道会让 stdout 变成
GBK，遇到 ✓ ✕ 之外的字符直接 UnicodeEncodeError 把脚本打断。加输出前先用
这个脚本确认。

用法：python scripts/check_console_gbk.py tests/ui_smoke.py
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path


def main(argv: list[str]) -> int:
    path = Path(argv[1] if len(argv) > 1 else "tests/ui_smoke.py")
    src = path.read_text(encoding="utf-8")

    counts: dict[str, int] = {}
    for ch in src:
        if ord(ch) > 127:
            counts[ch] = counts.get(ch, 0) + 1

    unsafe = 0
    print(f"{path.as_posix()}: {len(counts)} distinct non-ASCII chars")
    for ch, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        try:
            ch.encode("gbk")
            status = "GBK-OK"
        except UnicodeEncodeError:
            status = "GBK-FAIL"
            unsafe += 1
        name = unicodedata.name(ch, "<unnamed>")[:46]
        print(f"  U+{ord(ch):04X}  x{n:<4} {status:<9} {name}")

    print(f"\n{unsafe} char(s) would break a GBK console")
    return 1 if unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
