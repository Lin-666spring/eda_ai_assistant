"""P1-22(a/b/c) + P1-26 回归（2026-10-24）：前端流式竞态与报告栈策略。

验收报告缺陷：
- P1-22(a) 流式进行中切换会话不调 cancel_stream → AI 回复永久丢失或落错
  会话；stream.js 用「完成时」的会话落库。
- P1-22(b) 新消息打断旧流 → 旧气泡光标残留 + thinking 定时器永不清。
- P1-22(c) 工具卡定时器 4 处只 remove 不 clearInterval。
- P1-26 每条流式回答无条件入报告栈并强切右面板 Tab。

本测试沿用 tests/test_web_render_safety.py 的模式：node 加载从前端 js 模块
全集抽取的真实函数源码，注入桩件做行为级断言（落库绑定的会话 id、定时器
清理顺序、报告栈触发条件等纯逻辑可判定部分）。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

JS_DIR = Path(__file__).resolve().parent.parent / "web" / "js"
FRONTEND_JS = sorted(p for p in JS_DIR.glob("*.js") if p.name != "marked.min.js")

# 从拼接源抽取函数源码（与 test_web_render_safety 相同的抽取约定：
# 函数体结束的 `}` 必须顶格）。
EXTRACT_HELPER = r"""
function extract(name) {
  const src = fs.readFileSync(process.argv[2], 'utf8');
  const re = new RegExp('^(?:async )?function ' + name + '\\([^)]*\\) \\{[\\s\\S]*?^\\}', 'm');
  const m = src.match(re);
  if (!m) { console.error('extract failed: ' + name); process.exit(3); }
  return m[0];
}
"""


def _run_node(probe: str) -> subprocess.CompletedProcess:
    combined = "\n".join(p.read_text(encoding="utf-8") for p in FRONTEND_JS)
    import tempfile
    with tempfile.NamedTemporaryFile(
        "w", suffix="_frontend_combined.js", delete=False, encoding="utf-8"
    ) as f:
        f.write(combined)
        src_path = f.name
    try:
        return subprocess.run(
            ["node", "-e", probe, "unused", src_path],
            capture_output=True, text=True, timeout=60,
        )
    finally:
        Path(src_path).unlink(missing_ok=True)


PROBE_ABORT_STREAM = r"""
const fs = require('fs');
""" + EXTRACT_HELPER + r"""
const fails = [];
function check(name, cond, detail) { if (!cond) fails.push(name + ': ' + detail); }

// ── P1-22(a)：_abortActiveStream 必须按「发起会话」落库，而非当前会话 ──
const bubbleCalls = [];
const bubble = {
  getText: () => '半截回复',
  finalize: (t) => bubbleCalls.push(t),
};
let persisted = null;
const convA = { id: 'conv_A', messages: [] };
const abort = new Function(
  '_activeStreamBubble', '_streamTokenCount', '_activeStreamConvId', 'activeConvId',
  'findConversation', '_persistMessage', 'disableInput', 'renderConversations',
  extract('_abortActiveStream') + '\nreturn _abortActiveStream;'
)(bubble, 7, 'conv_A', 'conv_B',
  (id) => (id === 'conv_A' ? convA : null),
  (cid, role, content) => { persisted = [cid, role, content]; },
  () => {}, () => {});
abort('\n\n*(已停止生成)*');
check('abort_finalizes_bubble', bubbleCalls.length === 1 &&
  bubbleCalls[0] === '半截回复\n\n*(已停止生成)*', JSON.stringify(bubbleCalls));
check('abort_persists_to_initiating_conv',
  !!persisted && persisted[0] === 'conv_A' && persisted[1] === 'ai' &&
  persisted[2] === '半截回复\n\n*(已停止生成)*', JSON.stringify(persisted));
check('abort_pushes_into_conv_messages', convA.messages.length === 1, JSON.stringify(convA.messages));

// 半截内容为空（非流式路径占位气泡）→ 不落库，避免留下纯「已停止」噪声
let persisted2 = null;
const emptyBubble = { getText: () => '', finalize: () => {} };
const abort2 = new Function(
  '_activeStreamBubble', '_streamTokenCount', '_activeStreamConvId', 'activeConvId',
  'findConversation', '_persistMessage', 'disableInput', 'renderConversations',
  extract('_abortActiveStream') + '\nreturn _abortActiveStream;'
)(emptyBubble, 0, 'conv_A', 'conv_B',
  () => ({ messages: [] }),
  (cid) => { persisted2 = cid; }, () => {}, () => {});
abort2('\n\n*(已停止生成)*');
check('abort_empty_partial_skips_persist', persisted2 === null, String(persisted2));

// ── P1-22(a)：onStreamDone / onStreamError 落库绑定发起会话 ──
function runDone(hadTool, withBubble, convFound) {
  let persisted = null;
  const reports = [];
  const conv = { messages: [] };
  const done = new Function(
    '_activeToolCards', '_finishToolCard', '_activeStreamBubble', '_activeStreamConvId',
    'activeConvId', 'findConversation', '_persistMessage', '_streamHadToolCall',
    'showReport', '_streamTokenCount', 'disableInput', 'setStatus',
    'renderConversations', 'refreshToolCatalog',
    extract('onStreamDone') + '\nreturn onStreamDone;'
  )([], () => {}, withBubble ? { finalize() {}, getText: () => '完整回复' } : null,
    'conv_A', 'conv_B',
    (id) => (convFound ? conv : null),
    (cid, role, content) => { persisted = [cid, role, content]; },
    hadTool, (t) => reports.push(t), 3, () => {}, () => {}, () => {}, () => {});
  done('完整回复');
  return { persisted, reports };
}
const r1 = runDone(false, true, true);
check('done_persists_to_initiating_conv',
  !!r1.persisted && r1.persisted[0] === 'conv_A', JSON.stringify(r1.persisted));
check('done_no_report_stack_without_toolcall', r1.reports.length === 0, JSON.stringify(r1.reports));
const r2 = runDone(true, true, true);
check('done_report_stack_with_toolcall', r2.reports.length === 1, JSON.stringify(r2.reports));
const r3 = runDone(true, false, true);
check('done_without_bubble_no_persist_no_report', r3.persisted === null && r3.reports.length === 0, JSON.stringify(r3));
const r4 = runDone(true, true, false);
check('done_missing_conv_no_crash_no_persist', r4.persisted === null, JSON.stringify(r4));

let errPersisted = null;
const errConv = { messages: [] };
const errDone = new Function(
  '_activeToolCards', '_discardToolCards', '_activeStreamBubble', '_activeStreamConvId',
  'activeConvId', 'findConversation', '_persistMessage', '_streamTokenCount',
  'disableInput', 'setStatus', 'renderConversations',
  extract('onStreamError') + '\nreturn onStreamError;'
)([], () => {}, { finalize() {}, getText: () => ' 流式输出中断: x' }, 'conv_A', 'conv_B',
  (id) => (id === 'conv_A' ? errConv : null),
  (cid, role, content) => { errPersisted = [cid, role, content]; },
  0, () => {}, () => {}, () => {});
errDone('boom');
check('error_persists_to_initiating_conv',
  !!errPersisted && errPersisted[0] === 'conv_A', JSON.stringify(errPersisted));
check('error_pushes_into_conv_messages', errConv.messages.length === 1, JSON.stringify(errConv.messages));

// ── P1-22(a)：switchConversation 在流式进行中必须调 cancel_stream ──
async function runSwitch(withBubble) {
  let cancels = 0;
  const eelStub = { cancel_stream: () => () => { cancels++; } };
  const switchConv = new Function(
    '_activeStreamBubble', 'eel', 'activeConvId', '_persistState', 'renderConversations',
    'clearChatMessages', 'showEmptyState', 'closeSubPage', 'findConversation', 'document',
    extract('switchConversation') + '\nreturn switchConversation;'
  )(withBubble ? { getText: () => 'x' } : null, eelStub, 'conv_old',
    () => {}, () => {}, () => {}, () => {}, () => {},
    () => ({ id: 'conv_new', messages: [], _loaded: true }),
    { getElementById: () => ({ focus() {} }) });
  await switchConv('conv_new');
  return cancels;
}
(async () => {
  check('switch_cancels_stream_when_active', (await runSwitch(true)) === 1, 'cancels=');
  check('switch_no_cancel_when_idle', (await runSwitch(false)) === 0, 'cancels=');

  if (fails.length) { console.error(fails.join('\n')); process.exit(1); }
  console.log('ALL_OK');
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 执行前端流式收尾逻辑")
def test_stream_abort_and_completion_bind_initiating_conversation():
    r = _run_node(PROBE_ABORT_STREAM)
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "ALL_OK" in r.stdout


PROBE_TIMERS_AND_TAB = r"""
const fs = require('fs');
""" + EXTRACT_HELPER + r"""
const fails = [];
function check(name, cond, detail) { if (!cond) fails.push(name + ': ' + detail); }

// ── P1-22(c)：_discardToolCards 必须先 clearInterval 再 remove ──
const events = [];
const cards = [
  { _stopTimer: () => events.push('stop1'), remove: () => events.push('remove1') },
  { _stopTimer: () => events.push('stop2'), remove: () => events.push('remove2') },
  { _stopTimer: null, remove: () => events.push('remove3') },  // 无计时器的卡也要能丢
];
const discard = new Function('_activeToolCards',
  extract('_discardToolCards') + '\nreturn _discardToolCards;')(cards);
discard();
check('timers_cleared_before_removal',
  events.join(',') === 'stop1,remove1,stop2,remove2,remove3', events.join(','));

// ── P1-26：报告 Tab 强切策略（用户在看其他面板时只加角标不强切） ──
const policy = new Function(
  extract('_userReadingOtherTab') + '\nreturn _userReadingOtherTab;')();
check('badge_when_viewing_other_tab', policy(false, 'bom') === true, 'bom');
check('switch_when_panel_collapsed', policy(true, 'bom') === false, 'collapsed');
check('switch_when_already_on_report', policy(false, 'report') === false, 'report');
check('switch_when_no_active_tab', policy(false, null) === false, 'null');

if (fails.length) { console.error(fails.join('\n')); process.exit(1); }
console.log('ALL_OK');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 执行前端工具卡/面板逻辑")
def test_toolcard_timers_and_report_tab_policy():
    r = _run_node(PROBE_TIMERS_AND_TAB)
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "ALL_OK" in r.stdout
