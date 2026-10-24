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
    const conv = getActiveConversation();
    conv.messages.push({ role: 'ai', content: _activeStreamBubble.getText() });
    _persistMessage(activeConvId, 'ai', _activeStreamBubble.getText());
    showReport(fullText);
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
  _activeToolCards.forEach(c => c.remove());
  _activeToolCards = [];
  if (_activeStreamBubble) {
    _activeStreamBubble.finalize(' 流式输出中断: ' + errorMsg);
    const conv = getActiveConversation();
    const text = _activeStreamBubble.getText();
    conv.messages.push({ role: 'ai', content: text });
    // 与 onStreamDone 同口径落库：否则重启后这条 AI 回复会凭空消失
    _persistMessage(activeConvId, 'ai', text);
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }
  disableInput(false);
  setStatus('错误');
  renderConversations();
}

