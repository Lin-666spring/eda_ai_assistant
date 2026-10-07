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
  P15 热力图数据来源：坐标文件（无 PCB）也能出格、网格边长可切换并传给后端、
      空状态按 reason 给不同文案（而不是笼统的"无数据"）
  P16 两段式启动：480×340 小窗启动界面（不溢出、可停住预览）→ 展开正式界面
      1300×840 → 遮罩移除；resizeTo 被拒时走「另开正式窗口」兜底。
      另含：启动遮罩必须收尾、默认外观是浅色、界面文字不含 emoji 图标
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

# 控制台安全：检查项名字里带 ✕ / ✓ 这类符号，GBK 终端或 `| tee` 管道下
# print 会直接 UnicodeEncodeError 把整个巡检打断（Python 3.13 起更严）。
# 改成 UTF-8 + 不可编码字符替换，宁可显示成 ? 也不要中断测试。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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


def check_heatmap_data_path(page, res: Result):
    """P15 热力图（违规计数网格）数据来源与空状态。

    热力图 = 位号 → 坐标 → 分桶计数，与原理图/位图无关。这里验证
    「一键演示（BOM + 坐标文件，没有 PCB）」这条路径真能画出格子 —— 修复前
    get_heatmap_data() 只认 PCB 的 component_positions，这条路径恒为空表。
    P14 里那次真实 import_bom_file 会把上下文换成单行 BOM，所以这里先重新
    加载一遍演示数据，跑的是**真实后端**（无 stub）。
    """
    page.evaluate("() => { openRightPanel(); switchTab('review'); }")
    page.wait_for_timeout(200)

    real = page.evaluate("""async () => {
        await eel.load_demo_data()();     // BOM + 坐标文件（无 PCB）
        const sel = document.getElementById('drcHeatmapGrid');
        sel.value = '5';
        await loadDrcHeatmap();
        const empty = document.getElementById('drcHeatmapEmpty');
        const chart = document.getElementById('drcHeatmapChart');
        return {desc: document.getElementById('drcHeatmapDesc').textContent,
                emptyShown: empty.style.display !== 'none',
                emptyText: empty.textContent,
                chartShown: chart.style.display !== 'none',
                canvases: document.querySelectorAll('#drcHeatmapChart canvas').length,
                hasEcharts: !!window.echarts,
                chartInited: !!drcHeatmapChart,
                options: [...sel.options].map(o => o.value)};
    }""")
    res.check("P15 只有坐标文件（无 PCB）也能出热力图",
              real["chartShown"] and not real["emptyShown"]
              and "位置来源：坐标文件" in real["desc"],
              f"描述「{real['desc']}」/ 空提示={real['emptyShown']}")
    res.check("P15 热力图描述写清来源与计数",
              "条违规" in real["desc"] and "处计数" in real["desc"],
              f"描述「{real['desc']}」")
    if real["hasEcharts"]:
        res.check("P15 真实渲染出热力图 canvas",
                  real["chartInited"] and real["canvases"] >= 1,
                  f"canvas={real['canvases']}")
    else:
        res.warn("ECharts 未加载（离线 CDN）→ 只验证了数据与文案，未渲染图表")
    res.check("P15 网格边长可选（2/5/10/20mm）",
              real["options"] == ["2", "5", "10", "20"], str(real["options"]))

    # 切换网格边长必须真的把新值传给后端（而不是只改前端标签）
    grid = page.evaluate("""async () => {
        const sel = document.getElementById('drcHeatmapGrid');
        const calls = [];
        const orig = eel.get_drc_heatmap;
        eel.get_drc_heatmap = (...a) => { calls.push(a[0]); return orig(...a); };
        sel.value = '20';
        sel.dispatchEvent(new Event('change'));
        await new Promise(r => setTimeout(r, 1200));
        eel.get_drc_heatmap = orig;
        return {calls: calls,
                desc: document.getElementById('drcHeatmapDesc').textContent};
    }""")
    res.check("P15 切换网格边长会带上新值重新统计",
              grid["calls"] and grid["calls"][0] == 20 and "网格 20mm" in grid["desc"],
              f"后端收到 {grid['calls']} / 描述「{grid['desc']}」")

    # 空状态：按后端 reason 给不同文案，别一律「无数据」
    empty = page.evaluate("""async () => {
        const orig = eel.get_drc_heatmap;
        const out = {};
        const run = async (reason) => {
            eel.get_drc_heatmap = () => () => Promise.resolve(JSON.stringify(
                {ok: true, data: [], grid_size_mm: 5, source: '', violation_count: 0,
                 mapped: 0, reason: reason}));
            await loadDrcHeatmap();
            const e = document.getElementById('drcHeatmapEmpty');
            out[reason] = {shown: e.style.display !== 'none', text: e.textContent};
        };
        await run('no_positions');
        await run('no_violations');
        await run('unmapped');
        eel.get_drc_heatmap = orig;
        return out;
    }""")
    texts = {k: v["text"] for k, v in empty.items()}
    res.check("P15 空状态按原因给文案（无坐标 / 无违规 / 未关联位号）",
              all(v["shown"] for v in empty.values())
              and len(set(texts.values())) == 3
              and "Pick & Place" in texts.get("no_positions", "")
              and "通过" in texts.get("no_violations", "")
              and "位号" in texts.get("unmapped", ""),
              json.dumps(texts, ensure_ascii=False))

    page.evaluate("() => { document.getElementById('drcHeatmapGrid').value = '5'; loadDrcHeatmap(); }")
    page.wait_for_timeout(800)
    page.screenshot(path=str(SHOT_DIR / "heatmap_from_positions.png"))


def check_startup_splash_theme_and_emoji(page, res: Result):
    """P16 启动加载动画 / 默认浅色 / 界面无 emoji 字体图标。

    三个回归点：
      * 启动遮罩必须**已经消失且从 DOM 移除** —— 它盖住整个窗口，
        若因初始化抛错留在页面上，等于整个应用点不动（比没动画严重得多）。
      * 默认外观是浅色，且启动流程不得把主题写回后端（以前 applyTheme
        自带 save_theme，开机即把当前值回写，导致"改默认值"永远不生效）。
      * 界面文字里不得出现 emoji —— 图标统一走 ICONS 的内联 SVG。
    """
    splash = page.evaluate("""() => {
        const el = document.getElementById('appSplash');
        return {exists: !!el,
                hiding: !!(el && el.classList.contains('is-hiding')),
                status: (document.getElementById('appSplashStatus') || {}).textContent || '',
                booting: document.body.classList.contains('is-booting')};
    }""")
    res.check("P16 启动动画已完成并移除（未永久遮挡界面）",
              not splash["exists"] and not splash["booting"],
              f"exists={splash['exists']} hiding={splash['hiding']} booting={splash['booting']}")

    theme = page.evaluate("""() => ({
        attr: document.body.getAttribute('data-theme'),
        htmlAttr: document.documentElement.getAttribute('data-theme'),
        checked: [...document.querySelectorAll('.theme-card input')]
                   .filter(r => r.checked).map(r => r.value),
        bg: getComputedStyle(document.body).backgroundColor})""")
    res.check("P16 默认主题是浅色（含主题卡片单选态同步）",
              theme["attr"] == "light" and theme["checked"] == ["light"],
              f"data-theme={theme['attr']} checked={theme['checked']} bg={theme['bg']}")

    icons = page.evaluate("""() => {
        const txt = document.body.innerText || '';
        return {wrench: txt.includes('\\u{1F527}'),
                chart: txt.includes('\\u{1F4CA}'),
                ok: txt.includes('\\u{2705}'),
                cross: txt.includes('\\u{274C}'),
                headIcon: !!document.querySelector('#heatmapTitleIcon svg')};
    }""")
    res.check("P16 界面文字不含 emoji 图标（含 ）",
              not any(icons[k] for k in ("wrench", "chart", "ok", "cross")),
              json.dumps(icons, ensure_ascii=True))
    res.check("P16 热力图标题图标走内联 SVG（ICONS 注入）",
              icons["headIcon"] is True, f"svg={icons['headIcon']}")

    # 主题持久化：只有用户点选才回写后端，启动流程不许写（放最后做，避免影响后续检查）
    persist = page.evaluate("""async () => {
        const orig = eel.save_theme;
        const calls = [];
        eel.save_theme = (t) => { calls.push(t); return orig(t); };
        applyTheme('dark');
        const afterApply = calls.slice();
        saveThemePreference('dark');
        const afterSave = calls.slice();
        applyTheme('light');
        saveThemePreference('light');
        eel.save_theme = orig;
        return {afterApply: afterApply, afterSave: afterSave};
    }""")
    res.check("P16 applyTheme 不再隐式写回主题（仅用户点选才落盘）",
              persist["afterApply"] == [] and persist["afterSave"] == ["dark"],
              f"applyTheme→{persist['afterApply']} saveThemePreference→{persist['afterSave']}")


def check_boot_splash(browser, port: int, res: Result, console: list,
                     pageerrors: list, failed: list):
    """P16 两段式启动：小窗启动界面 → 展开正式界面。

    单独开一个 **480×340** 的小页面跑（正式页是 1300×840，尺寸不同）：
      * URL 带 #boot-hold → 启动界面停住，正好用来核对它与截图；
      * 解除后必须能收尾：遮罩移除、is-booting 摘掉；
      * resizeTo 在无头 Playwright 里必然不生效（viewport 是模拟的），
        正好把「被拒绝 → 走另开正式窗口兜底」这条路径真跑一遍。
    """
    page = browser.new_page(viewport={"width": 480, "height": 340})
    page.on("console", lambda m: console.append(
        (m.type, m.text[:200], getattr(m, "location", None) or {})))
    page.on("pageerror", lambda e: pageerrors.append(
        (str(e)[:200] + " || " + (getattr(e, "stack", "") or "")[:400])))
    page.on("requestfailed", lambda r: failed.append(r.url[:100]))
    try:
        page.goto(f"http://localhost:{port}/index.html#boot-hold", wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(SHOT_DIR / "boot_splash_small.png"))

        st = page.evaluate("""() => {
            const el = document.getElementById('appSplash');
            const fill = document.getElementById('appSplashFill');
            return {
                exists: !!el,
                title: (document.querySelector('.splash-title') || {}).textContent || '',
                sub: (document.querySelector('.splash-sub') || {}).textContent || '',
                status: (document.getElementById('appSplashStatus') || {}).textContent || '',
                version: (document.getElementById('appSplashVersion') || {}).textContent || '',
                hasMark: !!document.querySelector('.splash-logo svg'),
                fillWidth: fill ? Math.round(fill.getBoundingClientRect().width) : 0,
                hold: !!(window.boot && window.boot.hold),
                finished: !!(window.boot && window.boot.state.finished),
                booting: document.body.classList.contains('is-booting'),
                overflowX: document.documentElement.scrollWidth
                           - document.documentElement.clientWidth,
                overflowY: document.documentElement.scrollHeight
                           - document.documentElement.clientHeight,
            };
        }""")
        res.check("P16 小窗启动界面完整渲染（标记/标题/副标题/进度/状态/版本号）",
                  st["exists"] and st["hasMark"] and bool(st["title"]) and bool(st["sub"])
                  and st["fillWidth"] > 4 and bool(st["status"]) and st["version"].startswith("v"),
                  json.dumps(st, ensure_ascii=False)[:220])
        res.check("P16 启动界面在 480×340 小窗内不溢出（横向/纵向）",
                  st["overflowX"] <= 1 and st["overflowY"] <= 1 and st["booting"],
                  f"溢出 x={st['overflowX']} y={st['overflowY']} booting={st['booting']}")
        res.check("P16 #boot-hold 停在启动界面（首屏已就绪也不收尾）",
                  st["hold"] and not st["finished"] and st["exists"],
                  f"hold={st['hold']} finished={st['finished']} exists={st['exists']}")

        # 深色下的同一块界面（截图存档，顺带确认深色 token 覆盖到启动界面）
        page.evaluate("""() => {
            document.documentElement.setAttribute('data-theme', 'dark');
            document.body.setAttribute('data-theme', 'dark');
        }""")
        page.wait_for_timeout(250)
        page.screenshot(path=str(SHOT_DIR / "boot_splash_small_dark.png"))
        page.evaluate("""() => {
            document.documentElement.removeAttribute('data-theme');
            document.body.setAttribute('data-theme', 'light');
        }""")

        page.evaluate("() => window.boot.finish()")
        page.wait_for_timeout(1600)
        after = page.evaluate("""() => {
            const el = document.getElementById('appSplash');
            const s = (window.boot && window.boot.state) || {};
            return {exists: !!el,
                    hiding: !!(el && el.classList.contains('is-hiding')),
                    booting: document.body.classList.contains('is-booting'),
                    resize: s.resize, fallback: !!s.fallback, expanded: !!s.expanded};
        }""")
        res.check("P16 收尾：启动界面移除、首屏可见、窗口尺寸被拒也不卡住",
                  not after["exists"] and not after["booting"]
                  and after["resize"] in ("ok", "refused"),
                  json.dumps(after, ensure_ascii=False))
        res.check("P16 resizeTo 被拒绝时走「另开正式窗口」兜底",
                  after["resize"] != "refused" or after["fallback"],
                  json.dumps(after, ensure_ascii=False))
    finally:
        page.close()


def scan_warnings(page, res: Result, app_js: Path):
    """只报告、不判失败：死 id 引用 / 视图内容溢出。"""
    ids = sorted(set(re.findall(
        r"""getElementById\(['"]([A-Za-z0-9_-]+)['"]\)""", app_js.read_text(encoding="utf-8"))))
    view_ids = ("bom", "review", "tools", "report", "config")

    # index.html 里静态写死的 id 也算「真实存在」：启动遮罩这类元素在首屏之后就被
    # 移除了，但 app.js 在启动阶段确实要用它们，不是死代码。
    html_ids = set(re.findall(
        r'id="([A-Za-z0-9_-]+)"', (app_js.parent.parent / "index.html").read_text(encoding="utf-8")))

    # 某些 id 只在特定视图渲染时才存在（工具箱的搜索框等）→ 取「所有视图都找不到」
    # 的交集才算真死代码。
    missing_everywhere = set(ids) - html_ids
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
            print("Eel 服务未能在 25s 内启动，见 output/ui_smoke/server.log")
            return 2

        console, pageerrors, failed = [], [], []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not headed)
            page = browser.new_page(viewport={"width": 1300, "height": 840})
            page.on("console", lambda m: console.append(
                (m.type, m.text[:200], getattr(m, "location", None) or {})))
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
            check_heatmap_data_path(page, res)
            check_startup_splash_theme_and_emoji(page, res)
            check_boot_splash(browser, port, res, console, pageerrors, failed)
            check_sidebar_conversations(page, res)
            check_workspace(page, res)
            scan_warnings(page, res, ROOT / "web" / "js" / "app.js")

            # 第三方 CDN（字体 / ECharts）不通不算本地回归失败：离线跑时它们是
            # 预期内的降级（图表空、字体回落系统字体），但本地资源必须全绿。
            # 注意 r"Failed to load resource" 这类控制台错误的 m.text 里**没有 URL**，
            # 必须靠 m.location 里的 url 才能判定是 CDN —— 否则会被误判成本地回归。
            cdn_down = [u for u in failed if any(h in u for h in CDN_HOSTS)]
            failed = [u for u in failed if not any(h in u for h in CDN_HOSTS)]

            def _is_cdn(entry) -> bool:
                _, text, loc = entry
                url = loc.get("url", "") if isinstance(loc, dict) else ""
                return any(h in text or h in url for h in CDN_HOSTS)

            errs = [c for c in console if c[0] == "error" and not _is_cdn(c)]
            cdn_errs = [c for c in console if c[0] == "error" and _is_cdn(c)]
            if cdn_errs:
                cdn_down.extend(c[2].get("url", "") for c in cdn_errs if isinstance(c[2], dict))
            if cdn_down:
                res.warn("第三方 CDN 不可达（离线运行预期降级：ECharts 图表不可用、"
                         "字体回落系统字体）: " + ", ".join(sorted(set(cdn_down))[:2]))
            res.check("无 JS 控制台错误（本地资源）", not errs,
                      json.dumps([[c[1], c[2]] for c in errs[:3]], ensure_ascii=False))
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
        # 失败项必须可见：此前 ok/失败都打空串，巡检输出里看不出哪项挂了
        print(f"  {'[FAIL]' if not c['ok'] else '[ok]  '} {c['name']}"
              + (f"  — {c['detail']}" if c["detail"] else ""))
    if res.warnings:
        print("\n  巡检提醒（不影响通过）:")
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
