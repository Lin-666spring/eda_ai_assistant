"""把界面/文案里的 emoji 换成等义文本（2026-10-03）。

分三类处理，规则写在代码里而不是靠人工逐行：
  1. 注释行里的 ⚠️ 标记 —— 这是给维护者看的，用项目既有的中文「注意：」，
     整段替换（而不是删字符），否则会留下 `#    text` 这种断头注释。
  2. 字符串/模板里的 emoji 前缀 —— 删掉 emoji 与其后紧跟的空白。
  3. 其余零散 emoji —— 删掉字符本身。

只碰带 emoji 的行，不做全局替换；不处理 tests/（测试脚本的终端输出
保留 emoji，那些不是产品界面文案）。

用法：
    python scripts/strip_ui_emoji.py --check   # 只报告，不改
    python scripts/strip_ui_emoji.py --fix
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TARGETS = [
    ROOT / "web" / "index.html",
    ROOT / "web" / "css" / "style.css",
    ROOT / "web" / "js" / "app.js",
    ROOT / "src" / "supply" / "bom_health.py",
    ROOT / "src" / "rules" / "checker.py",
    ROOT / "src" / "bom" / "checker.py",
    ROOT / "src" / "bom" / "merger.py",
    ROOT / "src" / "bom" / "validator.py",
    ROOT / "src" / "pcb" / "calculator.py",
    ROOT / "src" / "core" / "controller.py",
    ROOT / "src" / "core" / "verifier.py",
    ROOT / "src" / "gui" / "main_window.py",
    ROOT / "src" / "agent" / "llm_client.py",
    ROOT / "src" / "agent" / "nlu_engine.py",
    ROOT / "src" / "agent" / "model_catalog.py",
    # 生成的 HTML 报告模板也是用户可见界面
    ROOT / "src" / "html_bom" / "templates" / "ibom.html",
    ROOT / "src" / "html_bom" / "templates" / "verification_map.html",
    # 闭环验证的 prompt 构造器（生产依赖，模型看到的就是它）
    ROOT / "tests" / "bom_suggestion.py",
    ROOT / "tests" / "test_bom_suggestion.py",
    # 回归脚本的控制台输出：emoji 会在 GBK 控制台/管道下直接 UnicodeEncodeError
    ROOT / "tests" / "ui_smoke.py",
    ROOT / "tests" / "demo_all.py",
]

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE0F"
    "\u2705\u274C\u26A0\u2699]"
)

# 排版符号，当文本用，保留
KEEP = set("\u2713\u2715\u2717\u2192\u2190\u2191\u2193\u2022\u2014\u2500\u2502")

# ── 精确替换（先跑，避免删字符留下病句）──
EXACT: list[tuple[str, str]] = [
    ("// ⚠️ ", "// 注意："),
    ("# ⚠️ ", "# 注意："),
    ("// ⚠️", "// 注意："),
    ("# ⚠️", "# 注意："),
    ("'⚠️ '", "'[警告] '"),
    ("'⚠ '", "'[警告] '"),
    ("\"⚠️ \"", "\"[警告] \""),
    ('"⚠️  "', '"[警告] "'),
    ('"⚠️"', '"[警告]"'),
    ("    ⚠ ", "    [警告] "),
    ('"✅ 设计规则检查通过，未发现违规项。"',
     '"设计规则检查通过，未发现违规项。"'),
    ('"✅ BOM 位号检查通过，无重复位号。"',
     '"BOM 位号检查通过，无重复位号。"'),
    ('emoji = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ "}[sev.value]',
     'mark = {"error": "[错误]", "warning": "[警告]", "info": "[提示]"}[sev.value]'),
]

# 行内替换：删 emoji + 紧跟的空白（zh 文案里 emoji 后面通常带一个空格）
INLINE = re.compile("[ \t]*(" + EMOJI.pattern + ")+[ \t]*")


def fix_line(line: str) -> str:
    for old, new in EXACT:
        if old in line:
            line = line.replace(old, new)
    stripped = line.lstrip()
    if stripped.startswith(("#", "//", "/*", "*", "<!--", "-->")):
        # 注释行：整段删掉 emoji 及其尾随空白，不引入新标记
        return INLINE.sub(" ", line).rstrip() + ("\n" if line.endswith("\n") else "")
    # 代码行：把 emoji + 其后尾随空白整段删掉。
    # 注意别留前导空格：`"✅ 建议已通过"` 必须是 `"建议已通过"`，
    # 而不是 `" 建议已通过"`（emoji 后面那个空格属于 emoji 的排版）。
    return re.sub("(" + EMOJI.pattern + ")+\uFE0F?[ \t]*", "", line)


def _safe(s: str) -> str:
    """Windows 控制台是 GBK，非 ASCII 一律转义，否则 print 直接抛异常。"""
    return s.encode("ascii", "backslashreplace").decode("ascii")


def process(path: Path, apply: bool) -> int:
    if not path.exists():
        print(f"missing: {path.relative_to(ROOT)}", file=sys.stderr)
        return 0
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    changed = 0
    out: list[str] = []
    for i, line in enumerate(lines, 1):
        hits = [c for c in line if EMOJI.match(c) and c not in KEEP]
        if not hits:
            out.append(line)
            continue
        new = fix_line(line)
        if new != line:
            changed += 1
            clean_old = "".join(c if c not in hits else "?" for c in line.strip())[:88]
            clean_new = "".join(c if c not in hits else "?" for c in new.strip())[:88]
            print(f"{path.relative_to(ROOT)}:{i}")
            print(f"   -  {_safe(clean_old)}")
            print(f"   +  {_safe(clean_new)}")
        out.append(new)
    if apply and changed:
        path.write_text("".join(out), encoding="utf-8", newline="")
    return changed


def main(argv: list[str]) -> int:
    apply = "--fix" in argv
    total = 0
    for t in TARGETS:
        total += process(t, apply)
    print(f"\n{total} line(s) {'fixed' if apply else 'to fix'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
