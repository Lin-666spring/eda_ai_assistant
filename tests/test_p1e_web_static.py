"""P1-27 回归（2026-10-24）：HTML 报告 iframe 必须带 sandbox 最小权限。

验收报告缺陷：web/index.html 的 #htmlFrame 无 sandbox —— file:// 上下文下，
站内生成的 HTML BOM 报告（含模板内联 JS）与父页面同源/同权执行。
修法取 sandbox="allow-scripts"（报告自带搜索/高亮/封装预览 JS 需要执行），
不给 allow-same-origin（文档落到不透明源：无法触碰父页面 DOM、无
storage/cookie、不能弹窗/表单/导航父页；模板已核实无外部资源引用）。

附带钉住 P1-22(c)：工具卡的「只 remove 不 clearInterval」泄漏模式
（`_activeToolCards.forEach(c => c.remove())`）不得回潮 —— 丢弃一律走
先停定时器的 _discardToolCards 入口。
"""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
INDEX_HTML = (WEB / "index.html").read_text(encoding="utf-8")


def _iframe_tag() -> str:
    m = re.search(r'<iframe\b[^>]*id="htmlFrame"[^>]*>', INDEX_HTML)
    assert m, "index.html 中找不到 #htmlFrame iframe 标签"
    return m.group(0)


def test_html_frame_has_sandbox():
    assert re.search(r'\bsandbox=', _iframe_tag()), "报告 iframe 缺少 sandbox 属性"


def test_html_frame_sandbox_no_same_origin():
    tag = _iframe_tag()
    m = re.search(r'sandbox="([^"]*)"', tag)
    assert m, "sandbox 属性必须带显式取值（裸 sandbox 也会禁脚本，报告功能不可用）"
    tokens = m.group(1).split()
    # 报告是站内生成内容，但脚本执行面必须隔离：允许脚本、不给同源
    assert "allow-scripts" in tokens
    assert "allow-same-origin" not in tokens, (
        "allow-same-origin 会让沙箱内脚本获得父页面同源权限（可与 "
        "allow-scripts 组合自移除沙箱），报告功能无需该权限"
    )


def test_toolcard_leaky_removal_pattern_gone():
    # P1-22(c)：4 处「只 remove 不 clearInterval」的丢弃点已统一收敛到
    # _discardToolCards（先停定时器）；该泄漏模式不得重新出现。
    for name in ("chat.js", "tools.js", "stream.js"):
        src = (WEB / "js" / name).read_text(encoding="utf-8")
        assert "_activeToolCards.forEach(c => c.remove())" not in src, (
            f"{name} 重新引入了不停定时器直接 remove 工具卡的泄漏模式"
        )
