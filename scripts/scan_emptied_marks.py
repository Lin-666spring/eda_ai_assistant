"""查「批量删 emoji 之后留下空标记」的残迹（2026-10-03）。

背景：把 emoji 从状态图标里删掉时，如果只是删字符，会留下
`icon = "" if ok else ""`（两边变一样）或 `{"error": ""}` 这种
"标记位被掏空"的代码——语法没错、图标没了，很难靠读代码发现。
本脚本专门把这类形态挑出来。

用法：python scripts/scan_emptied_marks.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 只看与"标记/图标/严重度"有关的行，避免把正常的空默认值当误报
MARKISH = re.compile(r"icon|emoji|mark|sev|status|badge|label", re.I)

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"""['"]\s*['"]\s*if\s"""), "三元两边都是空串"),
    (re.compile(r""":\s*['"]\s*['"]\s*[,}]"""), "字典值为空串"),
    (re.compile(r"""\?\s*['"]\s*['"]\s*:"""), "三元分支返回空串"),
    (re.compile(r"""=\s*['"]\s*['"]\s*$"""), "赋值成空串"),
]

EXTS = {".py", ".js", ".html"}
# 只扫产品代码；.dsh/.zcode/node_modules 等第三方或工具目录不参与
SCAN_DIRS = ("web", "src", "scripts", "tests")


def main() -> int:
    hits = 0
    for top in SCAN_DIRS:
        for path in sorted((ROOT / top).rglob("*")):
            if path.suffix not in EXTS or "node_modules" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(lines, 1):
                if not MARKISH.search(line):
                    continue
                for pat, desc in PATTERNS:
                    if pat.search(line):
                        hits += 1
                        print(f"{path.relative_to(ROOT)}:{i}  [{desc}]")
                        print("    " + line.strip()[:110].encode("ascii", "backslashreplace").decode())
                        break
    print(f"\n-- {hits} suspicious emptied mark(s) --")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
