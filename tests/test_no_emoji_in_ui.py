"""界面与用户可见文案里不得出现 emoji（2026-10-03）。

背景：项目规定图标统一用 `ICONS` 里的内联 SVG，不用 emoji 字体图标
（见 CLAUDE.md）。但 emoji 一直在各处回流——模板里的空状态、聊天文案、
验证报告的严重度标记都出现过。这个测试把规则钉死，避免下次又被加回来。

允许的符号是**排版符号**：✓ ✗ → ← ↑ ↓ · • — ═ ─ ● ■ 等。
它们不是 emoji，是正文的一部分（比如 `✓ 通过`、`✗ 未通过`），而且
不受字体图标缺失影响。

历史坑：批量删 emoji 时如果只删字符，会留下 `icon = "" if ok else ""`
这种「两边一样」的空标记——语法通过、图标消失。本文件同时钉住这一点。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Extended_Pictographic 覆盖绝大多数彩色 emoji；补上变体选择符（U+FE0F）、
# dingbat 区与常被当图标用的几个符号。
EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE0F"
    "\u2705\u274C\u26A0\u2699\u2139]"
)

# 排版符号：当文本用，允许
ALLOWED = set("✓✗✕✗→←↑↓•—═─●■□◆★☆")

# 用户可见的产品代码。tests/ 下的实验脚本往终端打 emoji 不在此列——
# 那些不是产品界面文案。
SCAN_FILES = [
    ROOT / "web" / "index.html",
    ROOT / "web" / "css" / "style.css",
    ROOT / "web" / "js" / "app.js",
    ROOT / "src" / "html_bom" / "templates" / "ibom.html",
    ROOT / "src" / "html_bom" / "templates" / "verification_map.html",
]

SCAN_GLOBS = [
    ("src/**/*.py", "src"),
]


def _emoji_in(text: str) -> list[tuple[int, int, str]]:
    """返回 (行号, 列号, 字符) 列表。"""
    out: list[tuple[int, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            if EMOJI.match(ch) and ch not in ALLOWED:
                out.append((lineno, col, ch))
    return out


def _targets() -> list[Path]:
    files = [p for p in SCAN_FILES if p.exists()]
    for pattern, _ in SCAN_GLOBS:
        files.extend(sorted(ROOT.glob(pattern)))
    # 去重且保持稳定顺序
    return sorted(set(files))


def test_no_emoji_in_user_facing_code():
    """web/ 与 src/ 的产品代码里不得出现 emoji。"""
    offenders: list[str] = []
    for path in _targets():
        if "node_modules" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, col, ch in _emoji_in(text):
            rel = path.relative_to(ROOT).as_posix()
            offenders.append(f"{rel}:{lineno}:{col} U+{ord(ch):04X}")
    assert not offenders, (
        "界面代码里出现了 emoji，请改用 ICONS 里的内联 SVG（或纯文字）：\n  "
        + "\n  ".join(offenders[:20])
    )


def test_app_js_icons_use_semantic_keys():
    """ICONS 的键必须是语义名，不许再退回 emoji 当键。"""
    app_js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"const ICONS = \{(.*?)\n\};", app_js, re.S)
    assert block, "没解析到 app.js 的 ICONS 表（结构变了？）"
    keys = re.findall(r"'([^']+)':\s*'<svg", block.group(1))
    assert keys, "ICONS 表里一个图标都没解析到"
    bad = [k for k in keys if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", k)]
    assert not bad, f"ICONS 的键必须是 kebab-case 语义名，这些不是: {bad}"


def test_tool_icons_point_at_existing_keys():
    """TOOL_ICONS 的每个值都要在 ICONS 里真实存在，否则卡片图标为空。"""
    app_js = (ROOT / "web" / "js" / "app.js").read_text(encoding="utf-8")
    icons_block = re.search(r"const ICONS = \{(.*?)\n\};", app_js, re.S).group(1)
    available = set(re.findall(r"'([^']+)':\s*'<svg", icons_block))
    tool_block = re.search(r"const TOOL_ICONS = \{(.*?)\n\};", app_js, re.S).group(1)
    mapping = dict(re.findall(r"(\w+):\s*'([^']+)'", tool_block))
    assert mapping, "没解析到 TOOL_ICONS"
    missing = {k: v for k, v in mapping.items() if v not in available}
    assert not missing, f"TOOL_ICONS 指向了 ICONS 里不存在的键: {missing}"


def test_no_emptied_icon_marks():
    """删 emoji 不许留下『两边都是空串』的标记位。

    `icon = "" if ok else ""` / `{"error": ""}` 这类代码语法正确，
    但把状态指示掏空了，只能靠这种检查发现。
    """
    suspicious = re.compile(
        r"""['"]\s*['"]\s*if\s|:\s*['"]\s*['"]\s*[,}]|\?\s*['"]\s*['"]\s*:"""
    )
    markish = re.compile(r"icon|emoji|mark|sev|status", re.I)
    offenders: list[str] = []
    for path in _targets():
        if "node_modules" in path.parts or path.name.startswith("scan_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if markish.search(line) and suspicious.search(line):
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}: {line.strip()[:80]}")
    assert not offenders, "疑似被掏空的图标/状态标记：\n  " + "\n  ".join(offenders[:10])
