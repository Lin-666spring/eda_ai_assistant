#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""前端交互冒烟测试（Playwright 真机驱动 Eel UI）。

用法:
    python tests/ui_smoke.py                  # 跑检查 + 截图到 output/ui_smoke/
    python tests/ui_smoke.py --headed         # 显示浏览器窗口（调试用）
    python tests/ui_smoke.py --serve --port N # 内部用：只起 Eel 服务（stub LLM）

依赖（可选，不在 requirements.txt 里）:
    pip install playwright && playwright install chromium

两点设计约定:
  1. **不花 API 额度**：服务端把 controller.agent 换成 stub，全程不发网络请求；
  2. **不干扰 pytest**：文件名不以 test_ 开头，不会被 tests/ 的默认收集规则捡走。

覆盖的回归点:
  P1 设置弹窗 ✕ / 「取消」按钮点了不关（closeSettings 的 e.target 判断写错）
  P2 服务商卡片网格 `1fr` 被 min-content 撑爆，第三列被弹窗裁掉
  P3 伴生模式 380px 下顶栏溢出，出现横向滚动条、按钮跑到屏外
  P4 悬浮折叠圆钮压住入口卡片（已移除，改为顶栏按钮）
  P7 body[data-theme=dark] 但没有任何深色规则（现已实现深色主题）
  P9 流式 AI 气泡是 #chatMessages 裸子节点 → clearChatMessages() 清不掉，
     切换会话后同一个回答显示两遍
  P10 一键演示的结果在首次发送时被 clearChatMessages() 清空
  P11 伴生模式 4 张 KPI 卡片竖排占满整屏
  P12 主页面必须默认是对话界面；模式入口点开的是「功能子页面」
  P13 左侧栏承载会话列表 + 工作区选择，会话按工作区隔离
  P14 生成/加载过程必须有动效：思考气泡（三点脉冲+计时）、顶栏状态胶囊 +
      顶部进度条、多智能体审查骨架屏、按钮内联 loading
另外附带若干"只报告不失败"的巡检（死 id 引用、视图溢出）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_PORT = 8137
SHOT_DIR = ROOT / "output" / "ui_smoke"
# 第三方 CDN 资源（index.html 里的 Inter 字体 + ECharts）；离线时降级不算本地回归
CDN_HOSTS = ("cdn.jsdelivr.net",)


# ═══════════════════════════════════════════════════════════════
#  Server side (--serve)
# ═══════════════════════════════════════════════════════════════

class _StubAgent:
    """LLMClient 替身：形状对齐真实接口，但只在本地拼字符串。"""

    model = "ui-smoke-stub"

    def __init__(self):
        self.history = []
        self.tool_executor = None

    def clear_history(self):
        self.history = []

    def chat(self, prompt, system_prompt=None, **kw):
        return "【ui-smoke】" + str(prompt)[:60]

    def chat_stream(self, text, system_prompt=None, on_token=None,
                    use_history=False, **kw):
        msg = ("【ui-smoke】\n\n## 结果\n\n- 项目一\n- 项目二\n\n"
               "| 位号 | 值 |\n|------|----|\n| C1 | 100nF |\n")
        if on_token:
            for ch in msg:
                on_token(ch)
        return msg

    def chat_with_tools(self, *a, **k):
        return "【ui-smoke】agent loop 完成。"

    def chat_multimodal(self, text, image=None, **kw):
        return "【ui-smoke】已收到图片。"


def serve(port: int) -> None:
    import eel
    import main as app
    app.controller.agent = _StubAgent()
    print(f"[ui_smoke] serving on {port}", flush=True)
    eel.start("index.html", mode=None, port=port, block=True)


# ═══════════════════════════════════════════════════════════════
#  Checks
# ═══════════════════════════════════════════════════════════════

class Result:
    def __init__(self):
        self.checks: list[dict] = []
        self.warnings: list[str] = []
        self.data: dict = {}

    def check(self, name: str, ok: bool, detail: str = ""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": detail})

    def warn(self, msg: str):
        self.warnings.append(msg)

    @property
    def failed(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]


def _open_settings(page):
    page.click("#settingsBtn")
    page.wait_for_timeout(450)


def _settings_open(page) -> bool:
    return page.evaluate(
        "() => document.getElementById('settingsOverlay').classList.contains('show')")


def check_mode_subpage(page, res: Result):
    """P12: 点击顶栏模式入口 → 打开功能子页面；「返回对话」回到聊天主页面。"""
    page.click('.nav-item[data-view="bom"]')
    page.wait_for_timeout(500)
    m = page.evaluate("""() => ({
        subShown: !document.getElementById('subPage').classList.contains('hidden'),
        chatHidden: document.getElementById('chatMessages').classList.contains('hidden'),
        crumb: (document.getElementById('subpageCrumb') || {}).textContent || '',
        navActive: document.querySelectorAll('.nav-item.active').length,
        cards: document.querySelectorAll('#viewContainer .tool-card').length})""")
    res.check("P12 模式入口打开功能子页面",
              m["subShown"] and m["chatHidden"] and m["crumb"] == "BOM 分析"
              and m["navActive"] == 1 and m["cards"] >= 4,
              f"crumb「{m['crumb']}」, 卡片 {m['cards']} 张")
    page.screenshot(path=str(SHOT_DIR / "mode_subpage.png"))

    page.click(".subpage-back")
    page.wait_for_timeout(400)
    back = page.evaluate("""() => ({
        subHidden: document.getElementById('subPage').classList.contains('hidden'),
        chatVisible: !document.getElementById('chatMessages').classList.contains('hidden'),
        navActive: document.querySelectorAll('.nav-item.active').length})""")
    res.check("P12「返回对话」回到主对话页",
              back["subHidden"] and back["chatVisible"] and back["navActive"] == 0,
              f"subPage.hidden={back['subHidden']}, navActive={back['navActive']}")


def check_settings_close(page, res: Result):
    """P1: ✕ / 取消 / Esc / 遮罩 四种关法都要能关。"""
    _open_settings(page)
    page.click(".settings-close-btn")
    page.wait_for_timeout(400)
    res.check("P1 设置弹窗 ✕ 按钮可关闭", not _settings_open(page))

    _open_settings(page)
    page.click(".settings-bottom-actions .btn-secondary")
    page.wait_for_timeout(400)
    res.check("P1 设置弹窗「取消」可关闭", not _settings_open(page))

    _open_settings(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(350)
    res.check("P1 设置弹窗 Esc 可关闭", not _settings_open(page))

    _open_settings(page)
    page.mouse.click(20, 420)          # 遮罩空白处
    page.wait_for_timeout(350)
    res.check("P1 设置弹窗点遮罩可关闭", not _settings_open(page))

    # 误伤检查：点弹窗内部不应关闭
    _open_settings(page)
    page.click(".settings-tab-title")
    page.wait_for_timeout(300)
    res.check("P1 点弹窗内部不关闭", _settings_open(page))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def check_provider_cards(page, res: Result):
    """P2: 服务商卡片不得超出网格容器（否则会被弹窗裁掉）。"""
    _open_settings(page)
    page.wait_for_timeout(300)
    page.screenshot(path=str(SHOT_DIR / "settings_providers.png"))
    m = page.evaluate("""() => {
      const wrap = document.querySelector('.provider-cards');
      if (!wrap) return null;
      const wr = wrap.getBoundingClientRect();
      const cards = [...document.querySelectorAll('.provider-card')];
      const beyond = cards.filter(c => c.getBoundingClientRect().right > wr.right + 1);
      const dlg = document.querySelector('.settings-dialog').getBoundingClientRect();
      return {containerW: Math.round(wr.width), cols: getComputedStyle(wrap).gridTemplateColumns,
              count: cards.length, beyond: beyond.length,
              beyondDialog: cards.filter(c => c.getBoundingClientRect().right > dlg.right + 1).length};
    }""")
    if not m:
        res.check("P2 服务商卡片不溢出", False, "未找到 .provider-cards")
    else:
        res.check("P2 服务商卡片不溢出弹窗", m["beyond"] == 0 and m["beyondDialog"] == 0,
                  f"容器 {m['containerW']}px, 列宽 [{m['cols']}], "
                  f"越界 {m['beyond']}/{m['count']} 张, 超出弹窗 {m['beyondDialog']} 张")

    # 厂商/模型由后端下发（SSOT）+ 实时拉取入口
    src = page.evaluate("""async () => {
      const cat = await eel.get_providers()();
      const sel = document.getElementById('setModelSelect');
      const badge = document.getElementById('modelSourceBadge');
      const link = document.getElementById('providerKeyLink');
      return {server: cat.count,
              cards: document.querySelectorAll('.provider-card').length,
              models: sel ? sel.options.length : 0,
              badge: badge ? badge.textContent.trim() : '',
              fetchBtn: !!document.getElementById('fetchModelsBtn'),
              keyLink: link ? link.getAttribute('href') : '',
              jsProviders: Object.keys(PROVIDERS).length};
    }""")
    res.check("服务商卡片数与后端厂商表一致",
              src["cards"] == src["server"] == src["jsProviders"] and src["server"] >= 8,
              f"前端 {src['cards']} / JS 缓存 {src['jsProviders']} / 后端 {src['server']}")
    res.check("模型下拉已由后端填充", src["models"] >= 2, f"{src['models']} 个选项")
    res.check("有来源徽标与「拉取最新模型」入口",
              src["fetchBtn"] and bool(src["badge"]), f"徽标「{src['badge']}」")
    res.check("提供申请 API Key 的直达链接",
              src["keyLink"].startswith("https://"), src["keyLink"][:40])
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def check_companion(page, res: Result):
    """P3: 伴生模式 380px 宽不得出现横向滚动条，顶栏按钮不能被推出屏幕。
    P11: 伴生模式 KPI 卡片必须两列（单列会占满整屏，看不到入口卡片）。"""
    # 主页面默认是对话（没有 KPI）；先打开一个模式子页面，P11 才有得测
    page.evaluate("() => switchView('bom')")
    page.wait_for_timeout(700)
    page.click("#modeToggleBtn")
    page.wait_for_timeout(1200)
    body_cls = page.evaluate("() => document.body.className")
    page.set_viewport_size({"width": 380, "height": 540})
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOT_DIR / "companion_380.png"))
    m = page.evaluate("""() => {
      const de = document.documentElement;
      const right = document.querySelector('.topbar-right');
      const kpi = document.querySelector('.kpi-row');
      const cols = kpi ? getComputedStyle(kpi).gridTemplateColumns : '';
      return {hScroll: de.scrollWidth > de.clientWidth,
              scrollW: de.scrollWidth, clientW: de.clientWidth,
              topbarRight: right ? Math.round(right.getBoundingClientRect().right) : null,
              kpiCols: cols.trim().split(/\\s+/).filter(Boolean).length,
              kpiRows: kpi ? Math.round(kpi.getBoundingClientRect().height) : 0,
              navShown: (() => { const n = document.querySelector('.topbar-nav');
                 return n ? getComputedStyle(n).display !== 'none' : null; })()};
    }""")
    res.check("P3 伴生模式进入 body.companion-mode", "companion-mode" in body_cls, body_cls)
    res.check("P3 伴生 380px 无横向滚动条", not m["hScroll"],
              f"scrollWidth {m['scrollW']} / clientWidth {m['clientW']}")
    res.check("P3 伴生顶栏按钮在屏内",
              m["topbarRight"] is not None and m["topbarRight"] <= m["clientW"] + 1,
              f"topbar-right 右边界 {m['topbarRight']} / 视口 {m['clientW']}")
    res.check("P11 伴生 KPI 两列布局", m["kpiCols"] == 2,
              f"实际 {m['kpiCols']} 列（{m['kpiCols']} 行高 {m['kpiRows']}px）")

    page.set_viewport_size({"width": 1300, "height": 840})
    page.wait_for_timeout(500)
    page.click("#modeToggleBtn")
    page.wait_for_timeout(1000)
    res.check("P3 退出伴生模式还原", "companion-mode" not in page.evaluate(
        "() => document.body.className"))


def check_tool_hub(page, res: Result):
    """统一工具目录：卡片数量与服务端一致、搜索/分类/状态筛选、可直跑。"""
    page.click('.nav-item[data-view="tools"]')
    page.wait_for_timeout(700)
    page.screenshot(path=str(SHOT_DIR / "tool_hub.png"))

    m = page.evaluate("""async () => {
      const cat = await eel.get_tools_catalog()();
      return {server: cat.count, cards: document.querySelectorAll('#toolGrid .tool-card').length,
              chips: document.querySelectorAll('.hub-chip').length,
              search: !!document.getElementById('toolSearchInput')};
    }""")
    res.check("工具目录卡片数与后端工具表一致",
              m["cards"] == m["server"] and m["server"] >= 20,
              f"前端 {m['cards']} / 后端 {m['server']}")
    res.check("工具箱有分类筛选与搜索框",
              m["chips"] >= 6 and m["search"], f"{m['chips']} 个分类筛选项")

    clip = page.evaluate("""() => [...document.querySelectorAll('#toolGrid .tool-card')]
        .filter(c => { const cb = c.getBoundingClientRect();
          return [...c.children].some(ch => ch.getBoundingClientRect().bottom > cb.bottom + 1); })
        .length""")
    res.check("工具卡片内容不溢出卡片", clip == 0, f"{clip} 张卡片有内容溢出")

    # 记下「还没导入 BOM」时的徽标分布，稍后验证导入后会自动刷新
    ready = page.evaluate("""() => {
        const byState = {};
        [...document.querySelectorAll('#toolGrid .tool-card')].forEach(c => {
          byState[c.dataset.state] = (byState[c.dataset.state] || 0) + 1; });
        return {byState, total: document.querySelectorAll('#toolGrid .tool-card').length,
                catalogBlocked: TOOL_CATALOG.filter(t => !t.ready).length,
                catalogReady: TOOL_CATALOG.filter(t => t.ready).length};
    }""")
    res.data["ready_before_bom"] = ready["catalogReady"]
    res.check("未导入数据时徽标标出「需先导入 BOM」",
              ready["byState"].get("blocked", 0) > 0
              and sum(ready["byState"].values()) == ready["total"],
              f"分布 {ready['byState']}（目录 blocked={ready['catalogBlocked']}）")

    # 搜索过滤
    page.fill("#toolSearchInput", "合并")
    page.wait_for_timeout(350)
    n_merge = page.evaluate("() => document.querySelectorAll('#toolGrid .tool-card').length")
    res.check("搜索「合并」命中 2 个能力", n_merge == 2, f"{n_merge} 张卡片")
    page.fill("#toolSearchInput", "zzz-不存在")
    page.wait_for_timeout(350)
    empty = page.evaluate("""() => ({
      cards: document.querySelectorAll('#toolGrid .tool-card').length,
      emptyShown: getComputedStyle(document.getElementById('toolEmpty')).display !== 'none'})""")
    res.check("无结果时显示空态", empty["cards"] == 0 and empty["emptyShown"],
              f"卡片 {empty['cards']}, 空态 {empty['emptyShown']}")
    page.click(".tool-search-clear")
    page.wait_for_timeout(300)

    # 分类筛选
    page.click('.hub-chip[data-cat="bom"]')
    page.wait_for_timeout(350)
    cats = page.evaluate("""() => [...document.querySelectorAll('#toolGrid .tool-card')]
        .map(c => c.dataset.cat)""")
    res.check("分类筛选只留 BOM 类", cats and all(c == "bom" for c in cats),
              f"{len(cats)} 张: {set(cats)}")
    page.click('.hub-chip[data-cat="all"]')
    page.wait_for_timeout(300)

    # 直接运行一个不依赖 BOM 的能力（pcb_status 是纯本地查询，不发网络请求）
    page.click('#toolGrid .tool-card[data-tool="pcb_status"]')
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('#chatMessages .bubble-ai').length > 0",
            timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(500)
    runres = page.evaluate("""() => ({
        bubbles: document.querySelectorAll('#chatMessages .bubble-ai').length,
        text: (document.querySelector('#chatMessages .bubble-ai') || {}).textContent || '',
        bare: document.querySelectorAll('#chatMessages > .bubble').length})""")
    res.check("工具箱可一键直跑能力",
              runres["bubbles"] >= 1 and len(runres["text"]) > 5,
              runres["text"][:48].replace("\n", " "))
    res.check("直跑结果的 AI 气泡包在 .msg-row 内", runres["bare"] == 0,
              f"裸气泡 {runres['bare']} 个")
    page.screenshot(path=str(SHOT_DIR / "tool_run.png"))


def check_sidebar_conversations(page, res: Result):
    """左侧会话栏：结构可见、新建会话清空消息区、当前会话高亮、无残留气泡（P9）。"""
    m = page.evaluate("""() => {
      const sb = document.getElementById('sidebar');
      const btn = document.getElementById('newChatBtn');
      return {sidebar: !!sb, newBtn: !!btn,
              width: sb ? Math.round(sb.getBoundingClientRect().width) : 0,
              list: !!document.getElementById('conversationList'),
              wsChip: !!document.getElementById('workspaceChip')};
    }""")
    res.check("左侧栏存在（会话列表 + 工作区选择器）",
              m["sidebar"] and m["list"] and m["wsChip"] and m["newBtn"] and m["width"] >= 200,
              f"宽 {m['width']}px")

    page.click("#newChatBtn")
    page.wait_for_timeout(600)
    st = page.evaluate("""() => ({
        items: document.querySelectorAll('#conversationList .session-item').length,
        active: document.querySelectorAll('#conversationList .session-item.active').length,
        rows: document.querySelectorAll('#chatMessages .msg-row').length,
        bare: document.querySelectorAll('#chatMessages > .bubble').length,
        toolsLeft: document.querySelectorAll('#chatMessages > .tool-call-card').length})""")
    res.check("新建会话后消息区清空且无残留",
              st["rows"] == 0 and st["bare"] == 0 and st["toolsLeft"] == 0,
              f"msg-row {st['rows']} / 裸气泡 {st['bare']} / 工具卡 {st['toolsLeft']}")
    res.check("会话列表有记录且当前会话高亮",
              st["items"] >= 1 and st["active"] == 1,
              f"{st['items']} 条, 高亮 {st['active']}")
    page.screenshot(path=str(SHOT_DIR / "sidebar_conversations.png"))


def check_workspace(page, res: Result):
    """工作区选择：默认工作区存在、可新建、会话列表按工作区隔离、可切回。"""
    page.click("#workspaceChip")
    page.wait_for_timeout(400)
    m = page.evaluate("""() => {
      const menu = document.getElementById('workspaceMenu');
      const chip = document.getElementById('workspaceChipName');
      return {shown: !!menu && getComputedStyle(menu).display !== 'none',
              items: document.querySelectorAll('#workspaceList .sb-ws-item').length,
              chip: chip ? chip.textContent.trim() : '',
              defaultConvs: document.querySelectorAll('#conversationList .session-item').length};
    }""")
    res.check("工作区下拉可展开且含默认工作区",
              m["shown"] and m["items"] >= 1 and m["chip"] == "默认工作区",
              f"{m['items']} 个工作区, 当前「{m['chip']}」")
    page.screenshot(path=str(SHOT_DIR / "workspace_menu.png"))

    # 新建工作区（带一个真实存在的目录，验证后端会创建/校验它）
    page.click("#workspaceMenu .sb-menu-new")
    page.wait_for_timeout(400)
    res.check("新建工作区弹窗可打开",
              page.evaluate(
                  "() => document.getElementById('workspaceOverlay').classList.contains('show')"))
    page.fill("#wsNameInput", "UI 冒烟工作区")
    page.fill("#wsPathInput", str(SHOT_DIR / "ws_home"))
    page.click("#workspaceOverlay .modal-actions .btn-primary")
    page.wait_for_timeout(800)
    ws = page.evaluate("""() => ({
        chip: document.getElementById('workspaceChipName').textContent.trim(),
        items: document.querySelectorAll('#workspaceList .sb-ws-item').length,
        convs: document.querySelectorAll('#conversationList .session-item').length,
        active: (() => { const ws = workspaces.find(w => w.id === currentWorkspaceId) || {};
                 return ws.path || ''; })()})""")
    res.check("新建后自动切到新工作区且会话列表为空",
              ws["chip"] == "UI 冒烟工作区" and ws["items"] >= 2 and ws["convs"] == 0,
              f"当前「{ws['chip']}」, {ws['items']} 个工作区, {ws['convs']} 条会话")
    res.check("工作区绑定的目录被后端确认",
              ws["active"].replace("\\", "/").endswith("output/ui_smoke/ws_home"),
              ws["active"])

    page.click("#newChatBtn")
    page.wait_for_timeout(500)
    n = page.evaluate("() => document.querySelectorAll('#conversationList .session-item').length")
    res.check("新工作区里可以创建会话", n == 1, f"{n} 条")
    page.screenshot(path=str(SHOT_DIR / "workspace_new.png"))

    # 切回默认工作区：应看到默认工作区自己的会话，而不是新工作区的
    page.click("#workspaceChip")
    page.wait_for_timeout(350)
    page.evaluate("""() => {
      const rows = [...document.querySelectorAll('#workspaceList .sb-ws-item')];
      const def = rows.find(r => r.getAttribute('title') === '默认工作区'
                                 || r.textContent.includes('默认工作区'));
      if (def) def.click();
    }""")
    page.wait_for_timeout(800)
    back = page.evaluate("""() => ({
        chip: document.getElementById('workspaceChipName').textContent.trim(),
        items: document.querySelectorAll('#conversationList .session-item').length})""")
    res.check("切回默认工作区后看到它自己的会话",
              back["chip"] == "默认工作区" and back["items"] == m["defaultConvs"],
              f"当前「{back['chip']}」, {back['items']} 条（默认工作区原有 {m['defaultConvs']} 条）")
    page.screenshot(path=str(SHOT_DIR / "workspace_back.png"))


def check_dark_theme(page, res: Result):
    """P7: 深色主题必须真的生效（不能只有 data-theme 属性没有 CSS）。"""
    # 外观设置里必须同时提供浅色 / 深色两张可选卡片
    _open_settings(page)
    page.click('.settings-nav-item[data-tab="s-appearance"]')
    page.wait_for_timeout(400)
    cards = page.evaluate("""() => [...document.querySelectorAll('.theme-card input')]
        .map(r => r.value)""")
    res.check("P7 外观设置提供浅/深两套主题", cards == ["light", "dark"], str(cards))
    page.screenshot(path=str(SHOT_DIR / "settings_appearance.png"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    m = page.evaluate("""() => {
      applyTheme('dark');
      const cs = getComputedStyle(document.body);
      const bg = cs.backgroundColor;
      return {attr: document.body.getAttribute('data-theme'), bg,
              root: cs.getPropertyValue('--bg-root').trim(),
              text: cs.getPropertyValue('--text-primary').trim(),
              checked: [...document.querySelectorAll('.theme-card input')]
                        .filter(r => r.checked).map(r => r.value)};
    }""")
    # #0e1015 → rgb(14, 16, 21)；浅色 #f5f7f9 会是 245 级别
    dark_bg = m["bg"].startswith("rgb(1") and "245" not in m["bg"]
    res.check("P7 深色主题 token 生效", m["attr"] == "dark" and dark_bg,
              f"data-theme={m['attr']}, --bg-root={m['root']}, body bg={m['bg']}")
    res.check("P7 主题卡片单选状态同步", m["checked"] == ["dark"], str(m["checked"]))
    page.screenshot(path=str(SHOT_DIR / "dark_tools.png"))

    page.click('.nav-item[data-view="bom"]')
    page.wait_for_timeout(500)
    page.screenshot(path=str(SHOT_DIR / "dark_bom.png"))
    back = page.evaluate("""() => { applyTheme('light');
        return document.body.getAttribute('data-theme'); }""")
    res.check("P7 可切回浅色", back == "light", back)


def check_chat_and_views(page, res: Result):
    """基础交互巡检：演示数据、发消息、Markdown、视图切换、空输入不发送。"""
    page.click('.nav-item[data-view="bom"]')
    page.wait_for_timeout(300)
    page.click(".view-actions .btn-primary")     # 一键演示
    page.wait_for_timeout(2500)
    page.screenshot(path=str(SHOT_DIR / "bom_demo.png"))
    rows = page.evaluate("() => document.querySelectorAll('#bomTable tbody tr').length")
    res.check("演示数据加载出 BOM 行", rows > 0, f"{rows} 行")

    # 数据到位后，工具箱的可用性徽标必须自动刷新（无需重进视图）
    page.click('.nav-item[data-view="tools"]')
    page.wait_for_timeout(700)
    after = page.evaluate("""() => {
        const byState = {};
        [...document.querySelectorAll('#toolGrid .tool-card')].forEach(c => {
          byState[c.dataset.state] = (byState[c.dataset.state] || 0) + 1; });
        return {byState, total: document.querySelectorAll('#toolGrid .tool-card').length,
                catalogReady: TOOL_CATALOG.filter(t => t.ready).length};
    }""")
    before = res.data.get("ready_before_bom", 0)
    res.check("导入数据后工具箱徽标自动刷新",
              after["byState"].get("blocked", 0) == 0
              and after["catalogReady"] > before
              and sum(after["byState"].values()) == after["total"],
              f"可用 {before} → {after['catalogReady']}，徽标 {after['byState']}")
    page.screenshot(path=str(SHOT_DIR / "tool_hub_after_bom.png"))
    page.evaluate("() => _enterChatStream()")    # 回到聊天流（不重跑演示）
    page.wait_for_timeout(400)

    # P10: 演示结论必须归属到会话，首条消息发送后不能被清掉
    demo_ai = page.evaluate("""() => [...document.querySelectorAll('#chatMessages .bubble-ai')]
        .map(b => b.textContent).join(' ')""")
    res.check("P10 演示结论已渲染", "已加载示例 BOM" in demo_ai,
              f"AI 气泡文本长度 {len(demo_ai)}")

    page.fill("#chatInput", "检查去耦电容")
    page.press("#chatInput", "Enter")
    try:
        # 等 AI 气泡出现，避免只数到用户那条就断言（流式回复是异步的）
        page.wait_for_function(
            "() => document.querySelectorAll('#chatMessages .bubble-ai').length > 1",
            timeout=10000)
    except Exception:
        pass
    page.wait_for_timeout(600)
    chat = page.evaluate("""() => ({
      userBubbles: document.querySelectorAll('#chatMessages .bubble-user').length,
      aiBubbles: document.querySelectorAll('#chatMessages .bubble-ai').length,
      md: document.querySelectorAll('#chatMessages h2, #chatMessages table').length,
      inputVal: document.getElementById('chatInput').value,
      bareBubbles: document.querySelectorAll('#chatMessages > .bubble').length,
      demoKept: [...document.querySelectorAll('#chatMessages .bubble-ai')]
                  .some(b => b.textContent.includes('已加载示例 BOM')),
      rows: document.querySelectorAll('#chatMessages .msg-row').length})""")
    res.check("Enter 发送并收到 AI 回复",
              chat["userBubbles"] >= 1 and chat["aiBubbles"] >= 2,
              f"用户 {chat['userBubbles']} / AI {chat['aiBubbles']}")
    res.check("Markdown 渲染（标题/表格）", chat["md"] > 0, f"{chat['md']} 个元素")
    res.check("发送后输入框清空", chat["inputVal"] == "")
    res.check("P10 发送消息后演示结论仍在", chat["demoKept"])
    res.check("P9 AI 气泡全部包在 .msg-row 内", chat["bareBubbles"] == 0,
              f"裸气泡 {chat['bareBubbles']} 个")

    total = chat["userBubbles"] + chat["aiBubbles"]
    page.press("#chatInput", "Control+Enter")   # 空输入
    page.wait_for_timeout(1500)
    after = page.evaluate("""() => document.querySelectorAll(
        '#chatMessages .bubble-user, #chatMessages .bubble-ai').length""")
    res.check("空输入 Ctrl+Enter 不发送", after == total, f"{total} → {after}")

    # P9 端到端：切换助手实例后回答不能翻倍显示
    before_ai = page.evaluate(
        "() => document.querySelectorAll('#chatMessages .bubble-ai').length")
    page.click('.nav-item[data-view="config"]')
    page.wait_for_timeout(600)
    page.evaluate("""() => {
      const rows = [...document.querySelectorAll('#configAssistantList .assistant-row')];
      if (rows.length < 2) {   // 至少要有两个助手才能测切换
        createAssistantInstance('bom-expert');
        renderAssistants();
      }
      const target = [...document.querySelectorAll('#configAssistantList .assistant-row')]
        .find(r => !r.classList.contains('active'));
      if (target) target.click();
    }""")
    page.wait_for_timeout(900)
    after_ai = page.evaluate(
        "() => document.querySelectorAll('#chatMessages .bubble-ai').length")
    res.check("P9 切换助手后回答不重复显示", after_ai <= before_ai,
              f"切换前 {before_ai} → 切换后 {after_ai}")

    # 发过消息后切视图，视图不能白屏（历史回归点）
    page.click('.nav-item[data-view="review"]')
    page.wait_for_timeout(600)
    vc = page.evaluate("""() => {
      const vc = document.getElementById('viewContainer');
      return {hidden: vc.classList.contains('hidden'),
              h: Math.round(vc.getBoundingClientRect().height)};}""")
    res.check("切换视图后不白屏", (not vc["hidden"]) and vc["h"] > 50,
              f"hidden={vc['hidden']} h={vc['h']}")


def check_loading_states(page, res: Result):
    """P14 加载动效：思考气泡 / 顶栏胶囊+进度条 / 审查骨架屏 / 按钮 loading。

    关键回归点：流式气泡在首个 token 到达前必须是「思考中」动效，
    而不是一个空白气泡（用户视角 = 点了发送没反应）。
    """
    page.evaluate("() => { _enterChatStream(); }")
    page.wait_for_timeout(200)

    think = page.evaluate("""() => {
        const b = createStreamingBubble();
        document.getElementById('chatMessages').appendChild(b.element);
        window.__probeBubble = b;
        const el = b.element.querySelector('.bubble-ai');
        return {
          thinking: el.classList.contains('thinking'),
          dots: el.querySelectorAll('.think-dots i').length,
          text: (el.querySelector('.think-text') || {}).textContent || '',
          timer: (el.querySelector('.think-timer') || {}).textContent || '',
          blank: el.textContent.trim().length === 0,
        };
    }""")
    res.check("P14 生成中气泡是思考动效（非空白气泡）",
              think["thinking"] and think["dots"] == 3 and not think["blank"] and bool(think["text"]),
              f"dots={think['dots']} text={think['text']!r} timer={think['timer']!r}")

    page.wait_for_timeout(600)
    page.screenshot(path=str(SHOT_DIR / "loading_thinking.png"))
    t2 = page.evaluate(
        "() => (document.querySelector('#chatMessages .think-timer') || {}).textContent || ''")
    res.check("P14 思考计时器在走", t2 != think["timer"], f"{think['timer']} → {t2}")

    first = page.evaluate("""() => {
        window.__probeBubble.updateToken('第一段正文');
        const el = window.__probeBubble.element.querySelector('.bubble-ai');
        return {thinking: el.classList.contains('thinking'), text: el.textContent};
    }""")
    res.check("P14 首个 token 到达即让位给正文",
              (not first["thinking"]) and "第一段正文" in first["text"],
              first["text"][:40])
    page.evaluate("() => { window.__probeBubble.finalize('完成'); window.__probeBubble = null; }")

    st = page.evaluate("""() => {
        setStatus('运行 71 条设计规则…');
        const pill = document.getElementById('statusPill');
        return {hidden: pill.classList.contains('hidden'),
                text: pill.textContent.trim(),
                spinner: pill.querySelectorAll('.status-spinner').length,
                bar: document.getElementById('topProgress').classList.contains('on')};
    }""")
    res.check("P14 运行态点亮顶栏状态胶囊 + 顶部进度条",
              (not st["hidden"]) and st["spinner"] == 1 and st["bar"],
              f"pill={st['text']!r} bar={st['bar']}")

    done = page.evaluate("""() => {
        setStatus('就绪');
        const pill = document.getElementById('statusPill');
        return {done: pill.classList.contains('done'),
                bar: document.getElementById('topProgress').classList.contains('on')};
    }""")
    res.check("P14 完成后进度条熄灭、胶囊转完成态", done["done"] and not done["bar"], str(done))
    page.wait_for_timeout(1900)
    res.check("P14 完成态胶囊自动淡出",
              page.evaluate("() => document.getElementById('statusPill').classList.contains('hidden')"))

    # 骨架屏视觉存档：调的就是真实路径用的那个渲染函数，只为避开毫秒级 stub 的时序
    page.evaluate("""() => {
        openRightPanel(); switchTab('review');
        const b = document.querySelector('.review-start-btn');
        if (b) b.style.display = 'none';
        _showReviewLoading();
    }""")
    page.wait_for_timeout(450)
    page.screenshot(path=str(SHOT_DIR / "loading_review.png"))
    page.evaluate("""() => {
        _hideReviewLoading();
        const b = document.querySelector('.review-start-btn');
        if (b) b.style.display = '';
    }""")

    sk = page.evaluate("""() => {
        featureCmd('__review');      // 打开右面板 + 切到审查页 + 启动审查（同步段）
        const box = document.getElementById('reviewLoading');
        const b = document.querySelector('.review-start-btn');
        return {shown: box.style.display !== 'none',
                cards: box.querySelectorAll('.skeleton-card').length,
                lines: box.querySelectorAll('.skeleton-line').length,
                head: box.textContent.trim(),
                bar: document.getElementById('topProgress').classList.contains('on'),
                btn: b ? b.disabled : null};
    }""")
    res.check("P14 多智能体审查立刻铺 5 张骨架卡（不等后端）",
              sk["shown"] and sk["cards"] == 5 and sk["lines"] >= 10 and sk["bar"] and sk["btn"] is True,
              f"{sk['cards']} 卡 / {sk['lines']} 行 / {sk['head'][:24]!r}")

    page.wait_for_timeout(3000)
    after = page.evaluate("""() => {
        const box = document.getElementById('reviewLoading');
        const b = document.querySelector('.review-start-btn');
        return {shown: box.style.display !== 'none',
                result: document.getElementById('reviewResult').style.display !== 'none',
                btnBack: b ? !b.disabled : false,
                cards: document.querySelectorAll('#reviewResult .review-agent-card').length};
    }""")
    res.check("P14 审查结束撤掉骨架屏（出结果或恢复按钮）",
              (not after["shown"]) and (after["result"] or after["btnBack"]),
              f"result={after['result']} cards={after['cards']} btnBack={after['btnBack']}")

    btn = page.evaluate("""() => {
        const b = document.querySelector('.heatmap-load-btn');
        const orig = b.textContent.trim();
        _btnLoading(b, '统计中');
        const r = {orig: orig, loading: b.classList.contains('is-loading'), disabled: b.disabled,
                   text: b.textContent.trim(),
                   spin: getComputedStyle(b, '::after').content !== 'none'};
        _btnLoaded(b);
        r.restored = b.textContent.trim();
        r.cleared = !b.classList.contains('is-loading') && !b.disabled;
        return r;
    }""")
    res.check("P14 按钮 loading 态（内联 spinner + 文案替换 + 可还原）",
              btn["loading"] and btn["disabled"] and btn["text"] == "统计中" and btn["spin"]
              and btn["cleared"] and btn["restored"] == btn["orig"],
              f"{btn['orig']!r} → {btn['text']!r} → {btn['restored']!r}")

    # 热力图：占位动效必须真的挂上并被撤掉
    # 先把后端调用人为放慢（模拟真实大板子的统计耗时），这样截图抓到的才是加载态本身
    page.evaluate("""() => {
        window.__origHeat = eel.get_drc_heatmap;
        eel.get_drc_heatmap = (...a) => () => new Promise(res => {
            setTimeout(() => res(window.__origHeat(...a)()), 1400);
        });
        openRightPanel(); switchTab('review');
        const s = document.getElementById('drcHeatmapSection');
        s.style.display = 'block';
        s.scrollIntoView({block: 'center'});
    }""")
    page.wait_for_timeout(200)
    hm = page.evaluate("""() => {
        loadDrcHeatmap();            // 故意不 await：只看同步段
        const h = document.getElementById('drcHeatmapLoading');
        const b = document.querySelector('.heatmap-load-btn');
        return {shown: h.style.display !== 'none',
                spin: h.querySelectorAll('.status-spinner').length,
                btnLoading: b.classList.contains('is-loading'),
                text: b.textContent.trim()};
    }""")
    res.check("P14 热力图统计期间显示占位动效 + 按钮 loading",
              hm["shown"] and hm["spin"] == 1 and hm["btnLoading"] and hm["text"] == "统计中",
              str(hm))
    page.wait_for_timeout(700)
    page.screenshot(path=str(SHOT_DIR / "loading_heatmap.png"))
    page.wait_for_timeout(1600)
    res.check("P14 热力图结束后撤掉占位动效",
              page.evaluate("""() => {
                  const h = document.getElementById('drcHeatmapLoading');
                  const b = document.querySelector('.heatmap-load-btn');
                  return h.style.display === 'none' && !b.classList.contains('is-loading')
                         && b.textContent.trim() === '加载热力图';
              }"""))
    page.evaluate("() => { eel.get_drc_heatmap = window.__origHeat; }")

    # 白名单包装层：真实文件导入必须照常解析，且期间点亮忙碌态
    # （eel.* 被统一包了一层，这里验证包装没把异步返回值弄坏）
    page.evaluate("""() => {
        const csv = 'Reference,Value,Package,PartNumber,Quantity\\nR1,10k,0603,RC0603FR-0710KL,1\\n';
        window.__imp = {state: 'pending'};
        eel.import_bom_file('_smoke_bom.csv', btoa(csv))().then(r => {
            window.__imp = {state: 'done', ok: !!(r && r.ok)};
        }).catch(e => { window.__imp = {state: 'error', err: String(e)}; });
        // 同步段抓忙碌态（包装层在 await 之前就已经点亮）
        const p = document.getElementById('statusPill');
        window.__impPill = {text: p.classList.contains('hidden') ? '' : p.textContent.trim(),
                            bar: document.getElementById('topProgress').classList.contains('on')};
    }""")
    try:
        page.wait_for_function("() => window.__imp.state !== 'pending'", timeout=15000)
    except Exception:
        pass
    imp = page.evaluate("() => ({st: window.__imp, busy: window.__impPill})")
    res.check("P14 导入类调用被包装后仍正常返回，且期间有忙碌反馈",
              imp["st"].get("state") == "done" and imp["st"].get("ok") is True
              and bool(imp["busy"]["text"]) and imp["busy"]["bar"],
              f"{imp['st']} pill={imp['busy']['text']!r} bar={imp['busy']['bar']}")


def scan_warnings(page, res: Result, app_js: Path):
    """只报告、不判失败：死 id 引用 / 视图内容溢出。"""
    ids = sorted(set(re.findall(
        r"""getElementById\(['"]([A-Za-z0-9_-]+)['"]\)""", app_js.read_text(encoding="utf-8"))))
    view_ids = ("bom", "review", "tools", "report", "config")

    # 某些 id 只在特定视图渲染时才存在（工具箱的搜索框等）→ 取「所有视图都找不到」
    # 的交集才算真死代码。
    missing_everywhere = set(ids)
    for view in view_ids:
        page.click(f'.nav-item[data-view="{view}"]')
        page.wait_for_timeout(350)
        missing_everywhere &= set(page.evaluate(
            """(ids) => ids.filter(i => !document.getElementById(i))""", ids))
    if missing_everywhere:
        res.warn("app.js 里引用了任何视图下都不存在的 DOM id（死代码）: "
                 + ", ".join(sorted(missing_everywhere)))

    for view in view_ids:
        page.click(f'.nav-item[data-view="{view}"]')
        page.wait_for_timeout(400)
        info = page.evaluate("""() => {
          const vc = document.getElementById('viewContainer');
          const fb = document.getElementById('chatFooter').getBoundingClientRect();
          const kids = [...vc.children];
          // 滚到底之后，最后一块内容仍被命令栏挡住才算真溢出
          vc.scrollTop = vc.scrollHeight;
          const last = kids.length ? kids[kids.length-1].getBoundingClientRect() : null;
          return {lastBottom: last ? Math.round(last.bottom) : null,
                  footerTop: Math.round(fb.top),
                  clipped: last ? last.bottom > fb.top + 2 : false};
        }""")
        if info["clipped"]:
            res.warn(f"{view} 视图滚到底后最后一块仍被命令栏遮挡"
                     f"（bottom {info['lastBottom']} > footerTop {info['footerTop']}）")


# ═══════════════════════════════════════════════════════════════
#  Runner
# ═══════════════════════════════════════════════════════════════

def _wait_port(port: int, timeout: float = 25.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.3)
    return False


def run(port: int, headed: bool) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 playwright。安装：pip install playwright && playwright install chromium")
        return 2

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    # 隔离存储：把子进程的 USERPROFILE/HOME 指到 output/ui_smoke/home，
    # 这样 1) 不污染用户真实的 ~/.eda_ai_assistant/sessions.db，
    #      2) 每次清空 → 稳定复现「首跑空库」这条路径。
    fake_home = SHOT_DIR / "home"
    if fake_home.exists():
        shutil.rmtree(fake_home, ignore_errors=True)
    fake_home.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["USERPROFILE"] = str(fake_home)
    env["HOME"] = str(fake_home)
    env["PYTHONIOENCODING"] = "utf-8"
    log = open(SHOT_DIR / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--serve", "--port", str(port)],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, env=env)
    res = Result()
    try:
        if not _wait_port(port):
            print("❌ Eel 服务未能在 25s 内启动，见 output/ui_smoke/server.log")
            return 2

        console, pageerrors, failed = [], [], []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            page = browser.new_page(viewport={"width": 1300, "height": 840})
            page.on("console", lambda m: console.append((m.type, m.text[:200])))
            page.on("pageerror", lambda e: pageerrors.append(
                (str(e)[:200] + " || " + (getattr(e, "stack", "") or "")[:400])))
            page.on("requestfailed", lambda r: failed.append(r.url[:100]))

            page.goto(f"http://localhost:{port}/index.html", wait_until="networkidle")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(SHOT_DIR / "initial.png"))

            boot = page.evaluate("""() => ({
                assistants: assistantInstances.length,
                current: currentAssistantInstance || '',
                catalog: TOOL_CATALOG.length,
                defaultTypeOk: !!ASSISTANT_TYPES['eda-general'],
                subHidden: document.getElementById('subPage').classList.contains('hidden'),
                chatVisible: !document.getElementById('chatMessages').classList.contains('hidden'),
                workspaces: workspaces.length,
                wsChip: (document.getElementById('workspaceChipName') || {}).textContent || ''})""")
            res.check("首跑自动创建默认助手（空库不白屏）",
                      boot["assistants"] >= 1 and bool(boot["current"]) and boot["defaultTypeOk"],
                      f"{boot['assistants']} 个助手, current={boot['current'][:24]}")
            res.check("启动即加载统一工具目录", boot["catalog"] >= 20, f"{boot['catalog']} 个能力")
            res.check("P12 主页面默认是对话界面（子页面隐藏）",
                      boot["subHidden"] and boot["chatVisible"],
                      f"subPage.hidden={boot['subHidden']}, chatMessages 可见={boot['chatVisible']}")
            res.check("P13 启动即有默认工作区",
                      boot["workspaces"] >= 1 and boot["wsChip"] == "默认工作区",
                      f"{boot['workspaces']} 个工作区, chip「{boot['wsChip']}」")

            check_mode_subpage(page, res)
            check_settings_close(page, res)
            check_provider_cards(page, res)
            check_tool_hub(page, res)
            check_dark_theme(page, res)
            check_companion(page, res)
            check_chat_and_views(page, res)
            check_loading_states(page, res)
            check_sidebar_conversations(page, res)
            check_workspace(page, res)
            scan_warnings(page, res, ROOT / "web" / "js" / "app.js")

            # 第三方 CDN（字体 / ECharts）不通不算本地回归失败：离线跑时它们是
            # 预期内的降级（图表空、字体回落系统字体），但本地资源必须全绿。
            cdn_down = [u for u in failed if any(h in u for h in CDN_HOSTS)]
            failed = [u for u in failed if not any(h in u for h in CDN_HOSTS)]
            errs = [c for c in console
                    if c[0] == "error" and not any(h in c[1] for h in CDN_HOSTS)]
            if cdn_down:
                res.warn("第三方 CDN 不可达（离线运行预期降级：ECharts 图表不可用、"
                         "字体回落系统字体）: " + ", ".join(cdn_down[:2]))
            res.check("无 JS 控制台错误（本地资源）", not errs, json.dumps(errs[:3], ensure_ascii=False))
            res.check("无未捕获异常", not pageerrors, "; ".join(pageerrors[:3]))
            res.check("无失败请求（本地资源）", not failed, "; ".join(failed[:3]))
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()

    print("\n═══ UI 冒烟测试 ═══")
    for c in res.checks:
        print(f"  {'✅' if c['ok'] else '❌'} {c['name']}"
              + (f"  — {c['detail']}" if c["detail"] else ""))
    if res.warnings:
        print("\n  ⚠️ 巡检提醒（不影响通过）:")
        for w in res.warnings:
            print(f"     - {w}")
    n_fail = len(res.failed)
    print(f"\n{len(res.checks) - n_fail}/{len(res.checks)} 通过"
          f"{'' if n_fail == 0 else f' — {n_fail} 项失败'}")
    print(f"截图: {SHOT_DIR}")
    return 1 if n_fail else 0


def main():
    ap = argparse.ArgumentParser(description="前端交互冒烟测试")
    ap.add_argument("--serve", action="store_true", help="只启动 Eel 服务（内部用）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--headed", action="store_true", help="显示浏览器窗口")
    args = ap.parse_args()
    if args.serve:
        serve(args.port)
        return 0
    return run(args.port, args.headed)


if __name__ == "__main__":
    sys.exit(main())
