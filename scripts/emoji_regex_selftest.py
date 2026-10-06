"""自检：确认 emoji 正则真的能抓到星平面（astral）emoji。

背景：`"[\\U0001F300-\\U0001FAFF]"` 这种写法里，两个 \\U 转义会各自
展开成一个孤立代理字符，区间在两个代理之间——它对 BMP 字符永远匹配不上，
很容易让人以为"已经扫干净了"。这个脚本用真实样本验证。

用法：python scripts/emoji_regex_selftest.py
"""

from __future__ import annotations

import re
import sys

# 当前扫描脚本里用的写法
PATTERN = (
    "[\U0001F300-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE0F"
    "\u2705\u274C\u26A0\u2699\u2139]"
)
EMOJI = re.compile(PATTERN)

SAMPLES = {
    "U+1F4CA (chart)": "\U0001F4CA",
    "U+1F4D0 (ruler)": "\U0001F4D0",
    "U+1F527 (wrench)": "\U0001F527",
    "U+1F600 (grin)": "\U0001F600",
    "U+1FAE0 (melt)": "\U0001FAE0",
    "U+2705 (check btn)": "\u2705",
    "U+274C (cross btn)": "\u274C",
    "U+26A0 (warning)": "\u26A0",
    "U+2699 (gear)": "\u2699",
    "U+2139 (info)": "\u2139",
}


def main() -> int:
    bad = 0
    for label, ch in SAMPLES.items():
        hit = bool(EMOJI.match(ch))
        # 控制台是 GBK，不打印字符本身
        print(f"{'OK  ' if hit else 'MISS'} {label}  ->  {hit}")
        if not hit:
            bad += 1
    print(f"\n{len(SAMPLES) - bad}/{len(SAMPLES)} samples matched")
    if bad:
        print("正则漏了星平面 emoji —— 必须显式用 \\U0001F300-\\U0001FAFF 区间",
              file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
