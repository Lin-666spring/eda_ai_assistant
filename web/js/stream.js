// ═══════════════════════════════════════════
//  Stream Callbacks —— P1-6 阶段C 自 app.js 拆出（原 2788-2906 行）
//  eel 回调：onPCBChanged / 工具卡 / 流式 token 与收尾
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// Called by Python file watcher
eel.expose(onPCBChanged, 'on_pcb_changed');
function onPCBChanged(filepath) {
  appendSystem(`[PCB]  检测到 PCB 文件变化: ${filepath}`);
  // 文件监听开启时 PCB 到位 → 刷新工具可用性（与 onStreamDone 同口径）
  refreshToolCatalog();
}

// ── Streaming callbacks (called by Python) ──

// 工具卡片标签 — 一律取 get_tools_catalog()（= ToolRegistry）下发的 label。
// 过去这里手抄过一份 name→中文 映射，9/14 个键和 ToolRegistry 对不上
// （validate_packages/check_rules/analyze_pcb…，rag_query 写成
// query_knowledge_base），Agent 模式的工具卡片一直显示英文原始名。
// 目录是启动时必载的（loadToolCatalog），只在目录加载失败的极端情况下退回原始名。
function toolCallLabel(toolName) {
  const t = getTool(toolName);
  return (t && t.label) || toolName;
}

let _activeToolCards = [];

eel.expose(onToolCall, 'on_tool_call');
function onToolCall(toolName) {
  // P1-26（验收 2026-10-24）：本轮回答确实动用了工具 → 完成时才允许进报告栈
  _streamHadToolCall = true;
  if (!_activeStreamBubble) return;
  const label = toolCallLabel(toolName);
  // Create a card with spinner, inserted before the streaming bubble
  const card = document.createElement('div');
  card.className = 'tool-call-card';
  card.innerHTML = `<span class="tool-call-spinner"></span>
    <span class="tool-call-icon">${ICONS['wrench']}</span>
    <span class="tool-call-name">${label}</span>
    <span class="tool-call-status">执行中…</span>
    <span class="tool-call-timer">0.0s</span>`;
  _activeStreamBubble.element.parentNode.insertBefore(card, _activeStreamBubble.element);
  _activeToolCards.push(card);
  // 卡片自带计时器：让「慢工具」看起来是在跑，而不是卡住
  const t0 = Date.now();
  const timerEl = card.querySelector('.tool-call-timer');
  card._stopTimer = () => {
    if (card._timerId) { clearInterval(card._timerId); card._timerId = null; }
    if (timerEl) timerEl.textContent = ((Date.now() - t0) / 1000).toFixed(1) + 's';
  };
  card._timerId = setInterval(() => {
    if (timerEl) timerEl.textContent = ((Date.now() - t0) / 1000).toFixed(1) + 's';
  }, 100);
  // 气泡里的思考文案跟着工具走
  if (_activeStreamBubble.think) _activeStreamBubble.think(`正在调用「${label}」`);
  // Mark previous card as done
  if (_activeToolCards.length > 1) {
    const prev = _activeToolCards[_activeToolCards.length - 2];
    prev.classList.add('done');
    if (prev._stopTimer) prev._stopTimer();
    prev.querySelector('.tool-call-spinner').replaceWith(makeDoneIcon());
    prev.querySelector('.tool-call-status').textContent = '已完成';
  }
  scrollChat();
}
function _finishToolCard(c) {
  if (!c || c.classList.contains('done')) return;
  c.classList.add('done');
  if (c._stopTimer) c._stopTimer();
  const sp = c.querySelector('.tool-call-spinner');
  if (sp) sp.replaceWith(makeDoneIcon());
  const st = c.querySelector('.tool-call-status');
  if (st) st.textContent = '已完成';
}

/** P1-22(c)（验收 2026-10-24）：丢弃工具卡必须先 clearInterval —— 只 remove
 *  节点的话，卡片自带的 100ms 计时器仍在往已脱离 DOM 的元素写文本，
 *  长会话下定时器与节点双双泄漏（clearChatMessages / 新一轮流 / 错误收尾
 *  共用本入口；需要保留卡片可见的收尾走 _finishToolCard）。 */
function _discardToolCards() {
  _activeToolCards.forEach(c => {
    if (c._stopTimer) c._stopTimer();
    c.remove();
  });
  _activeToolCards = [];
}
function makeDoneIcon() {
  const s = document.createElement('span');
  s.className = 'tool-call-icon';
  s.textContent = '✓';
  s.style.color = 'var(--success)';
  return s;
}

eel.expose(onStreamToken, 'on_stream_token');
function onStreamToken(token) {
  if (_activeStreamBubble) {
    _streamTokenCount++;
    _activeStreamBubble.updateToken(token);
  }
}

eel.expose(onStreamDone, 'on_stream_done');
function onStreamDone(fullText) {
  // Finalize any pending tool-call cards
  _activeToolCards.forEach(c => _finishToolCard(c));
  _activeToolCards = [];
  if (_activeStreamBubble) {
    _activeStreamBubble.finalize(fullText);
    // P1-22(a)（验收 2026-10-24）：落库绑定「发起流时」的会话 —— 回调到达时
    // activeConvId 可能已被切走，用完成时的活动会话会把回复写错地方。
    const convId = _activeStreamConvId || activeConvId;
    const conv = findConversation(convId);
    if (conv) {
      const text = _activeStreamBubble.getText();
      conv.messages.push({ role: 'ai', content: text });
      _persistMessage(convId, 'ai', text);
    }
    // P1-26（验收 2026-10-24）：仅当本轮流式回答确实调用过工具（产出了
    // 报告/工具成果）才入报告栈并切右面板 —— 纯闲聊不再抢走用户正在看的
    // BOM 表（是否强切由 showReport 按用户当前视面决定）。
    if (_streamHadToolCall) showReport(fullText);
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }
  disableInput(false);
  setStatus('就绪');
  renderConversations();
  // Agent 循环里可能调用了导入类工具（BOM/PCB 到位）→ 后台刷新可用性
  refreshToolCatalog();
}

eel.expose(onStreamError, 'on_stream_error');
function onStreamError(errorMsg) {
  // P1-22(c)（验收 2026-10-24）：丢弃工具卡先停计时器（只 remove 泄漏 setInterval）
  _discardToolCards();
  if (_activeStreamBubble) {
    _activeStreamBubble.finalize(' 流式输出中断: ' + errorMsg);
    // P1-22(a)（验收 2026-10-24）：错误收尾同 onStreamDone 口径 —— 按
    // 发起会话落库，否则切走会话后中断回复会写错地方或整条丢失。
    const convId = _activeStreamConvId || activeConvId;
    const conv = findConversation(convId);
    if (conv) {
      const text = _activeStreamBubble.getText();
      conv.messages.push({ role: 'ai', content: text });
      _persistMessage(convId, 'ai', text);
    }
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }
  disableInput(false);
  setStatus('错误');
  renderConversations();
}

