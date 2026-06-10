/* ═══════════════════════════════════════════
   EDA AI 智能助手 — Cherry Studio Frontend
   ═══════════════════════════════════════════ */

// ═══════════ State ═══════════

const ASSISTANT_TYPES = {
  'eda-general': {
    typeId: 'eda-general', name: 'EDA 通用助手', icon: '(´｡• ᵕ •｡`)',
    systemPrompt: 'general',
    quickActions: ['合并 BOM', '校验封装', '设计规则', 'BOM健康'],
    description: 'BOM管理、设计规则检查、PCB分析的通用助手',
  },
  'bom-expert': {
    typeId: 'bom-expert', name: 'BOM 管理专家', icon: '( •̀ᴗ•́ )و',
    systemPrompt: 'bom',
    quickActions: ['合并 BOM', 'AI智能合并', '校验封装', '查重', 'BOM健康', '生成 HTML'],
    description: '专注于物料清单管理、合并、验证和供应链检查',
  },
  'pcb-reviewer': {
    typeId: 'pcb-reviewer', name: 'PCB 设计审查', icon: '(｡･ω･｡)',
    systemPrompt: 'pcb',
    quickActions: ['设计规则', '分析PCB', '检查走线', '查看PCB'],
    description: '专注于PCB布局分析、设计规则检查和信号完整性',
  },
  'vision-analyst': {
    typeId: 'vision-analyst', name: '视觉分析助手', icon: '(=^･^=)',
    systemPrompt: 'vision',
    quickActions: ['分析图片'],
    description: '上传PCB截图或原理图进行AI视觉分析',
  },
};

// ── Assistant instances (multi-instance model) ──
let assistantInstances = [];   // [{ instanceId, typeId, customName? }]
let currentAssistantInstance = null;  // instanceId
let instanceCounter = 0;

// ── Conversations per instance ──
let conversations = {};        // { instanceId: [{ id, title, messages: [] }] }
let activeConvId = null;
let convCounter = 0;

// ── UI state ──
let sidebarTab = 'assistants'; // 'assistants' | 'topics'
let currentImage = null;
let _activeStreamBubble = null;
let _streamTokenCount = 0;
let agentMode = false;

function createAssistantInstance(typeId, customName) {
  const type = ASSISTANT_TYPES[typeId];
  if (!type) return null;
  instanceCounter++;
  const inst = {
    instanceId: `asst_${Date.now()}_${instanceCounter}`,
    typeId: typeId,
    name: customName || type.name,
  };
  assistantInstances.push(inst);
  _persistAssistant(inst);
  return inst;
}

// ── Marked.js configuration ──
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true, gfm: true, headerIds: false, mangle: false,
  });
}

// ═══════════ Init ═══════════

document.addEventListener('DOMContentLoaded', async () => {
  await loadPersistedState();
  renderAssistants();
  renderConversations();

  // Theme
  try {
    const sett = await eel.get_settings()();
    if (sett && sett.theme) applyTheme(sett.theme);
  } catch(e) {}

  // LLM config
  try {
    const cfg = await eel.get_llm_config()();
    updateLLMStatus(cfg);
  } catch(e) {}

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Enter to send, Shift+Enter for newline
  const input = document.getElementById('chatInput');
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  // Paste image
  document.addEventListener('paste', e => {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (let item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault();
        const blob = item.getAsFile();
        const reader = new FileReader();
        reader.onload = ev => { currentImage = ev.target.result; showImagePreview(currentImage); };
        reader.readAsDataURL(blob);
        break;
      }
    }
  });
});

// ═══════════ Persistence ═══════════

async function loadPersistedState() {
  let resp;
  try { resp = await eel.db_load_all()(); } catch(e) { return; }
  if (!resp || !resp.ok || !resp.data) return;

  const { assistants: saved, conversations: savedConvs, active_assistant, active_conv } = resp.data;

  // 无持久化数据 → 保持空白状态
  if (!saved || saved.length === 0) return;

  // 恢复助手实例
  assistantInstances = saved.map(a => ({
    instanceId: a.instance_id,
    typeId: a.type_id,
    name: a.name,
  }));
  conversations = {};
  saved.forEach(a => {
    conversations[a.instance_id] = savedConvs[a.instance_id] || [];
  });

  // 恢复活跃状态
  if (active_assistant && assistantInstances.find(i => i.instanceId === active_assistant)) {
    currentAssistantInstance = active_assistant;
  } else {
    currentAssistantInstance = assistantInstances[0].instanceId;
  }

  updateChatHeader();
  renderQuickActions();

  // 恢复当前对话
  const convs = conversations[currentAssistantInstance] || [];
  if (active_conv && convs.find(c => c.id === active_conv)) {
    activeConvId = active_conv;
    await restoreConversationMessages(active_conv);
  } else if (convs.length > 0) {
    activeConvId = convs[0].id;
    await restoreConversationMessages(convs[0].id);
  }
}

async function restoreConversationMessages(convId) {
  showEmptyState(false);
  let resp;
  try { resp = await eel.db_load_messages(convId)(); } catch(e) { return; }
  if (!resp || !resp.ok) return;
  const msgs = resp.messages || [];
  msgs.forEach(m => {
    if (m.image) {
      appendBubbleWithImage(m.role, m.content, m.image);
    } else {
      appendBubble(m.role, m.content);
    }
  });
}

// ── Fire-and-forget persistence helpers ──

function _persistAssistant(inst) {
  try { eel.db_save_assistant(inst.instanceId, inst.typeId, inst.name)(); } catch(e) {}
}

function _persistDeleteAssistant(instanceId) {
  try { eel.db_delete_assistant(instanceId)(); } catch(e) {}
}

function _persistConversation(conv) {
  const inst = assistantInstances.find(i => i.instanceId === currentAssistantInstance);
  if (!inst) return;
  try { eel.db_save_conversation(conv.id, inst.instanceId, conv.title)(); } catch(e) {}
}

function _persistDeleteConversation(convId) {
  try { eel.db_delete_conversation(convId)(); } catch(e) {}
}

function _persistMessage(convId, role, content, image) {
  try { eel.db_save_message(convId, role, content, image || '')(); } catch(e) {}
}

function _persistState() {
  try { eel.db_save_active_state(
    currentAssistantInstance || '',
    activeConvId || ''
  )(); } catch(e) {}
}

// ═══════════ Sidebar Tabs ═══════════

function switchSidebarTab(tab) {
  sidebarTab = tab;
  document.querySelectorAll('.sidebar-tab').forEach(b => b.classList.remove('active'));
  document.querySelector(`.sidebar-tab[data-tab="${tab}"]`).classList.add('active');
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.getElementById(tab === 'assistants' ? 'sidebarAssistants' : 'sidebarTopics').classList.add('active');
}

// ═══════════ Assistant Management ═══════════

function getActiveAssistant() {
  const inst = assistantInstances.find(i => i.instanceId === currentAssistantInstance);
  if (!inst) return null;
  const type = ASSISTANT_TYPES[inst.typeId];
  return { ...type, instanceId: inst.instanceId, name: inst.name };
}

function renderAssistants() {
  const container = document.getElementById('assistantList');
  if (assistantInstances.length === 0) {
    container.innerHTML = '<div class="sidebar-empty">点击 + 新建助手</div>';
    return;
  }
  container.innerHTML = assistantInstances.map(inst => {
    const type = ASSISTANT_TYPES[inst.typeId];
    if (!type) return '';
    const active = inst.instanceId === currentAssistantInstance ? 'active' : '';
    return `
      <div class="sb-item ${active}"
           onclick="selectAssistant('${inst.instanceId}')" title="${type.description}">
        <span class="sb-item-icon">${type.icon}</span>
        <span class="sb-item-name">${inst.name}</span>
        <button class="sb-item-del" onclick="deleteAssistant('${inst.instanceId}', event)" title="删除助手">
          <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>
        </button>
      </div>
    `;
  }).join('');
}

function selectAssistant(instanceId) {
  currentAssistantInstance = instanceId;
  if (!conversations[instanceId]) conversations[instanceId] = [];
  const inst = assistantInstances.find(i => i.instanceId === instanceId);
  if (inst) {
    try { eel.set_active_assistant(inst.typeId)(); } catch(e) {}
  }
  _persistState();
  renderAssistants();
  renderConversations();
  updateChatHeader();
  const convs = conversations[instanceId] || [];
  if (convs.length > 0) {
    switchConversation(convs[0].id);
  } else {
    activeConvId = null;
    showEmptyState(true);
    document.getElementById('chatMessages').querySelectorAll('.msg-row').forEach(el => el.remove());
  }
  renderQuickActions();
}

function deleteAssistant(instanceId, event) {
  event.stopPropagation();
  const inst = assistantInstances.find(i => i.instanceId === instanceId);
  const name = inst ? inst.name : '此助手';
  showConfirmDialog({
    title: '删除助手',
    message: `确定要删除「${name}」吗？\n该助手的对话记录也会被清除。`,
    okText: '删除',
    onOk: () => {
      _persistDeleteAssistant(instanceId);
      assistantInstances = assistantInstances.filter(i => i.instanceId !== instanceId);
      delete conversations[instanceId];
      if (currentAssistantInstance === instanceId) {
        if (assistantInstances.length > 0) {
          currentAssistantInstance = assistantInstances[0].instanceId;
          selectAssistant(currentAssistantInstance);
        } else {
          currentAssistantInstance = null;
          activeConvId = null;
          clearChatMessages();
          showEmptyState(true);
          updateChatHeader();
          renderQuickActions();
        }
      }
      _persistState();
      renderAssistants();
    },
  });
}

function updateChatHeader() {
  const a = getActiveAssistant();
  if (!a) {
    document.getElementById('assistantIcon').textContent = '';
    document.getElementById('assistantName').textContent = '新建助手以开始';
    return;
  }
  document.getElementById('assistantIcon').textContent = a.icon;
  document.getElementById('assistantName').textContent = a.name;
}

function switchAssistant(instanceId) {
  if (instanceId) selectAssistant(instanceId);
}

function toggleAgentMode() {
  agentMode = !agentMode;
  const btn = document.getElementById('agentToggle');
  const input = document.getElementById('chatInput');
  if (agentMode) {
    btn.classList.add('active');
    input.placeholder = 'Agent 模式 — 描述你的目标，AI 自主规划执行...';
  } else {
    btn.classList.remove('active');
    input.placeholder = '输入指令... (Enter 发送, Shift+Enter 换行)';
  }
}

// ═══════════ Window Mode ═══════════

let companionMode = false;

async function toggleWindowMode() {
  companionMode = !companionMode;
  applyWindowMode();
  try { eel.request_window_toggle()(); } catch(e) {}
}

function applyWindowMode() {
  const btn = document.getElementById('modeToggleBtn');
  if (companionMode) {
    document.body.classList.add('companion-mode');
    btn.classList.add('active');
    window.resizeTo(380, 540);
    window.moveTo(screen.width - 400, 40);
  } else {
    document.body.classList.remove('companion-mode');
    btn.classList.remove('active');
    window.resizeTo(1300, 840);
    window.moveTo(40, 40);
  }
}

// Poll Python-side hotkey/tray toggle requests
setInterval(async () => {
  try {
    const resp = await eel.poll_toggle()();
    if (resp && resp.ok && resp.toggled) {
      companionMode = resp.companion;
      applyWindowMode();
    }
  } catch(e) {}
}, 500);

function renderQuickActions() {
  const a = getActiveAssistant();
  const container = document.getElementById('quickActions');
  if (!a) { container.innerHTML = ''; return; }
  container.innerHTML = (a.quickActions || []).map(cmd =>
    `<button class="qa-btn" onclick="quickCmd('${cmd}')">${cmd}</button>`
  ).join('');
}

// ═══════════ New Assistant Dialog ═══════════

function showNewAssistantDialog() {
  const grid = document.getElementById('assistantTypeList');
  grid.innerHTML = Object.values(ASSISTANT_TYPES).map(type => `
    <div class="assistant-type-card" onclick="createAssistantFromDialog('${type.typeId}')">
      <span class="assistant-type-icon">${type.icon}</span>
      <div class="assistant-type-name">${type.name}</div>
      <div class="assistant-type-desc">${type.description}</div>
    </div>
  `).join('');
  document.getElementById('newAssistantOverlay').classList.add('show');
}

function closeNewAssistantDialog() {
  document.getElementById('newAssistantOverlay').classList.remove('show');
}

function createAssistantFromDialog(typeId) {
  const inst = createAssistantInstance(typeId);
  if (!inst) return;
  conversations[inst.instanceId] = [];
  closeNewAssistantDialog();
  selectAssistant(inst.instanceId);
  // Switch to topics tab and auto-create first conversation
  switchSidebarTab('topics');
  newConversation();
}

// ═══════════ Conversation Management ═══════════

function newConversation() {
  if (!currentAssistantInstance) {
    // No assistant yet — prompt user to create one
    showNewAssistantDialog();
    return;
  }
  if (!conversations[currentAssistantInstance]) conversations[currentAssistantInstance] = [];
  const convs = conversations[currentAssistantInstance];
  convCounter++;
  const conv = {
    id: `conv_${Date.now()}_${convCounter}`,
    title: '新对话',
    messages: [],
  };
  convs.unshift(conv);
  activeConvId = conv.id;
  _persistConversation(conv);
  _persistState();
  renderConversations();
  clearChatMessages();
  showEmptyState(true);
  document.getElementById('chatInput').focus();
}

function switchConversation(convId) {
  activeConvId = convId;
  _persistState();
  renderConversations();
  clearChatMessages();
  showEmptyState(false);

  const conv = findConversation(convId);
  if (conv && conv.messages.length > 0) {
    conv.messages.forEach(m => appendBubble(m.role, m.content, m.image));
  } else if (!conv || conv.messages.length === 0) {
    showEmptyState(true);
  }
  document.getElementById('chatInput').focus();
}

function deleteConversation(convId, event) {
  event.stopPropagation();
  const conv = findConversation(convId);
  const title = conv ? conv.title : '此对话';
  showConfirmDialog({
    title: '删除对话',
    message: `确定要删除「${title}」吗？\n删除后无法恢复。`,
    okText: '删除',
    onOk: () => {
      _persistDeleteConversation(convId);
      const convs = conversations[currentAssistantInstance];
      const idx = convs.findIndex(c => c.id === convId);
      if (idx < 0) return;
      convs.splice(idx, 1);

      if (activeConvId === convId) {
        if (convs.length > 0) {
          switchConversation(convs[0].id);
        } else {
          activeConvId = null;
          clearChatMessages();
          showEmptyState(true);
        }
      }
      _persistState();
      renderConversations();
    },
  });
}

function findConversation(convId) {
  for (const aid of Object.keys(conversations)) {
    const found = conversations[aid].find(c => c.id === convId);
    if (found) return found;
  }
  return null;
}

function getActiveConversation() {
  if (!activeConvId) {
    newConversation();
  }
  return findConversation(activeConvId);
}

function renderConversations() {
  const container = document.getElementById('conversationList');
  if (!currentAssistantInstance) {
    container.innerHTML = '<div class="sidebar-empty">请先新建助手</div>';
    return;
  }
  const convs = conversations[currentAssistantInstance] || [];
  if (convs.length === 0) {
    container.innerHTML = '<div class="sidebar-empty">暂无对话</div>';
    return;
  }
  container.innerHTML = convs.map(c => `
    <div class="sb-item ${c.id === activeConvId ? 'active' : ''}"
         onclick="switchConversation('${c.id}')" title="${escapeAttr(c.title)}">
      <span class="sb-item-icon">
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,3 11,8 6,13"/></svg>
      </span>
      <span class="sb-item-name">${escapeHtml(c.title)}</span>
      <button class="sb-item-del" onclick="deleteConversation('${c.id}', event)" title="删除">
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>
      </button>
    </div>
  `).join('');
}

// ═══════════ Chat ═══════════

function clearChatMessages() {
  // Abort any in-progress stream
  _activeStreamBubble = null;
  _streamTokenCount = 0;
  const container = document.getElementById('chatMessages');
  container.querySelectorAll('.msg-row,.config-tip').forEach(el => el.remove());
}

function showEmptyState(show) {
  const el = document.getElementById('emptyState');
  if (show) { el.classList.remove('hidden'); }
  else { el.classList.add('hidden'); }
}

function quickCmd(text) {
  if (text === '生成 HTML') { generateHTMLBOM(); return; }
  document.getElementById('chatInput').value = text;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text && !currentImage) return;
  if (text === '生成 HTML' || text === '生成HTML') { removeImage(); input.value = ''; generateHTMLBOM(); return; }

  const hasImage = !!currentImage;
  const userText = text || '帮我分析这张图片';
  input.value = '';
  input.style.height = 'auto';
  showEmptyState(false);

  // Get or create conversation
  const conv = getActiveConversation();
  if (!conv) return;  // No assistant yet — newConversation showed the dialog

  // Update title from first message
  if (conv.messages.length === 0) {
    conv.title = userText.substring(0, 30) + (userText.length > 30 ? '...' : '');
    _persistConversation(conv);
    renderConversations();
  }

  // Abort any in-progress stream
  if (_activeStreamBubble) {
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }

  // Show user bubble
  if (hasImage) {
    appendBubbleWithImage('user', userText, currentImage);
    conv.messages.push({ role: 'user', content: userText, image: currentImage });
    _persistMessage(activeConvId, 'user', userText, currentImage);
  } else {
    appendBubble('user', userText);
    conv.messages.push({ role: 'user', content: userText });
    _persistMessage(activeConvId, 'user', userText);
  }

  setStatus('思考中...');
  disableInput(true);

  if (hasImage) {
    // Image analysis: keep non-streaming
    let resp;
    try {
      resp = await eel.send_image(userText, currentImage)();
    } catch(e) {
      resp = { ok: false, result: '网络错误: ' + e };
    }
    currentImage = null; hideImagePreview();
    disableInput(false);
    setStatus('就绪');

    if (resp && resp.ok) {
      appendBubble('ai', resp.result);
      conv.messages.push({ role: 'ai', content: resp.result });
      _persistMessage(activeConvId, 'ai', resp.result);
      showReport(resp.result);
    } else {
      const errMsg = '处理失败: ' + (resp ? resp.result : '未知错误');
      appendBubble('ai', errMsg);
      conv.messages.push({ role: 'ai', content: errMsg });
      _persistMessage(activeConvId, 'ai', errMsg);
    }
  } else {
    // Text message: use streaming API or Agent Loop
    _streamTokenCount = 0;
    _activeStreamBubble = createStreamingBubble();
    document.getElementById('chatMessages').appendChild(_activeStreamBubble.element);
    scrollChat();

    try {
      if (agentMode) {
        await eel.send_message_agent(userText)();
      } else {
        await eel.send_message_stream(userText)();
      }
      // on_stream_done callback handles finalization
    } catch (e) {
      // Network error: eel call itself failed
      if (_activeStreamBubble) {
        _activeStreamBubble.finalize(' 连接错误: ' + e);
        const conv2 = getActiveConversation();
        conv2.messages.push({ role: 'ai', content: _activeStreamBubble.getText() });
        _activeStreamBubble = null;
      }
      disableInput(false);
      setStatus('错误');
    }
  }
  renderConversations();
}

async function generateHTMLBOM() {
  setStatus('生成 HTML BOM...');
  try {
    const resp = await eel.generate_html_bom()();
    if (resp.ok) {
      appendBubble('ai', resp.report);
      showReport(resp.report);
      if (resp.path) {
        const frame = document.getElementById('htmlFrame');
        frame.src = 'file:///' + resp.path.replace(/\\/g, '/');
        frame.style.display = 'block';
        document.getElementById('htmlEmpty').style.display = 'none';
        switchTab('html');
      }
    } else {
      appendTip(resp.report || '生成失败', 'error');
    }
  } catch(e) { appendTip('生成失败: ' + e, 'error'); }
  setStatus('就绪');
}

// ═══════════ Bubbles ═══════════

function appendBubble(type, text) {
  if (type === 'user') showEmptyState(false);
  const row = document.createElement('div');
  row.className = `msg-row ${type}`;
  const bubble = document.createElement('div');
  bubble.className = type === 'system' ? 'bubble bubble-system' : `bubble bubble-${type}`;
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  if (type === 'ai' && typeof marked !== 'undefined') {
    // AI responses: render Markdown
    bubble.innerHTML = renderMarkdown(text) + `<div class="bubble-time">${time}</div>`;
  } else {
    // User / system messages: plain text (safe)
    bubble.innerHTML = escapeHtml(text) + `<div class="bubble-time">${time}</div>`;
  }

  row.appendChild(bubble);
  document.getElementById('chatMessages').appendChild(row);
  scrollChat();
}

/** Safe markdown render — strips raw HTML tags before parsing */
function renderMarkdown(text) {
  if (!text) return '';
  // Strip raw HTML to prevent XSS, then parse markdown
  const safe = String(text).replace(/<[^>]*>/g, '');
  try {
    return marked.parse(safe);
  } catch (e) {
    return escapeHtml(safe);
  }
}

function appendBubbleWithImage(type, text, imageDataUrl) {
  showEmptyState(false);
  const row = document.createElement('div');
  row.className = `msg-row ${type}`;
  const bubble = document.createElement('div');
  bubble.className = `bubble bubble-${type}`;
  const img = document.createElement('img');
  img.src = imageDataUrl;
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  bubble.appendChild(img);
  bubble.innerHTML += escapeHtml(text) + `<div class="bubble-time">${time}</div>`;
  row.appendChild(bubble);
  document.getElementById('chatMessages').appendChild(row);
  scrollChat();
}

// ── Streaming bubble support ──

/** Create a streaming AI bubble that updates incrementally.
 *  Returns { updateToken(token), finalize(fullText), element } */
function createStreamingBubble() {
  showEmptyState(false);
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'bubble bubble-ai streaming';
  const timeLabel = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

  let buffer = '';
  let tokenCount = 0;
  const RERENDER_EVERY = 3;  // throttle: rerender every N tokens

  function rerender() {
    // Build inner HTML with streamed content + blinking cursor
    const rendered = renderMarkdown(buffer);
    const cursor = '<span class="stream-cursor">▍</span>';
    bubble.innerHTML = rendered + cursor + `<div class="bubble-time">${timeLabel}</div>`;
  }

  return {
    element: bubble,
    updateToken(token) {
      buffer += token;
      tokenCount++;
      if (tokenCount % RERENDER_EVERY === 0) {
        rerender();
      }
    },
    finalize(fullText) {
      buffer = fullText || buffer;
      // Final render: no cursor
      bubble.innerHTML = renderMarkdown(buffer) + `<div class="bubble-time">${timeLabel}</div>`;
      bubble.classList.remove('streaming');
    },
    getText() { return buffer; },
  };
}

function appendSystem(text) {
  const row = document.createElement('div');
  row.className = 'msg-row system';
  const bubble = document.createElement('div');
  bubble.className = 'bubble bubble-system';
  bubble.textContent = text;
  row.appendChild(bubble);
  document.getElementById('chatMessages').appendChild(row);
  scrollChat();
}

function appendTip(text, type) {
  showEmptyState(false);
  const div = document.createElement('div');
  div.className = `config-tip ${type || 'info'}`;
  div.textContent = text;
  document.getElementById('chatMessages').appendChild(div);
  scrollChat();
}

function scrollChat() {
  const el = document.getElementById('chatMessages');
  el.scrollTop = el.scrollHeight;
}

// ═══════════ Report ═══════════

function showReport(text) {
  const stack = document.getElementById('reportStack');
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  const card = document.createElement('div');
  card.className = 'report-card';
  card.innerHTML = `<div class="report-card-time">${time}</div>` + formatReport(text);
  stack.insertBefore(card, stack.firstChild);
  document.getElementById('reportEmpty').style.display = 'none';
  switchTab('report');
}

function formatReport(text) {
  const lines = text.split('\n');
  let html = '';
  let inSection = false;
  const sevClass = { 'ERROR': 'rp-error', 'WARNING': 'rp-warning', 'INFO': 'rp-info' };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^={10,}/.test(line) && i < 2) continue;
    if (line.includes('设计规则检查报告') || line.includes('BOM 健康检查报告') ||
        line.includes('BOM 合并报告') || line.includes('封装校验') ||
        line.includes('位号查重') || line.includes('合并报告') ||
        line.includes('校验报告') || line.includes('AI 视觉分析')) {
      html += `<div class="rp-title">${escapeHtml(line.trim())}</div>`;
      continue;
    }
    if (/^[-=]{10,}/.test(line)) { html += '<hr class="rp-hr">'; continue; }
    const secMatch = line.match(/【(\w+)】(.+)/);
    if (secMatch) {
      const sev = sevClass[secMatch[1].toUpperCase()] || '';
      html += `<div class="rp-section ${sev}"><div class="rp-section-head">${escapeHtml(line.trim())}</div>`;
      inSection = true; continue;
    }
    if (inSection && line.startsWith('  •')) {
      html += `<div class="rp-item">${escapeHtml(line.replace(/^  •\s*/, ''))}</div>`;
      continue;
    }
    if (inSection && /^\s{4,}/.test(line)) {
      const sub = line.trim();
      if (sub.startsWith('位置:')) html += `<div class="rp-sub rp-loc">${escapeHtml(sub)}</div>`;
      else if (sub.startsWith('建议:')) html += `<div class="rp-sub rp-sug">${escapeHtml(sub)}</div>`;
      else if (sub.startsWith('理论:')) html += `<div class="rp-sub rp-theory">${escapeHtml(sub)}</div>`;
      continue;
    }
    if (line.trim() === '' && inSection) { html += '</div>'; inSection = false; continue; }
    if (line.trim()) html += `<div class="rp-line">${escapeHtml(line)}</div>`;
  }
  if (inSection) html += '</div>';
  return html;
}

// ═══════════ Image Handling ═══════════

function showImagePreview(dataUrl) {
  document.getElementById('imagePreviewThumb').src = dataUrl;
  document.getElementById('imagePreviewBar').style.display = 'flex';
}
function hideImagePreview() {
  document.getElementById('imagePreviewBar').style.display = 'none';
}
function removeImage() {
  currentImage = null; hideImagePreview();
  document.getElementById('imageFileInput').value = '';
}
function onImageFileSelected(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => { currentImage = e.target.result; showImagePreview(currentImage); };
  reader.readAsDataURL(file);
  input.value = '';
}

// ═══════════ File Imports ═══════════

function onFileSelected(type, input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async function(e) {
    const bytes = new Uint8Array(e.target.result);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    const b64 = btoa(binary);
    setStatus('加载中...');
    try {
      if (type === 'bom') {
        const resp = await eel.import_bom_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); renderBOMTable(resp.items); setStatus(`已加载 BOM (${resp.count} 条)`); showDesignSuggestions(); }
        else { appendTip(resp.msg, 'error'); setStatus('加载失败'); }
      } else if (type === 'pcb') {
        const resp = await eel.import_pcb_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); setStatus(`已加载 PCB`); }
        else { appendTip(resp.msg, 'error'); setStatus('加载失败'); }
      } else if (type === 'pos') {
        const resp = await eel.import_pos_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); setStatus('已加载坐标'); }
        else { appendTip(resp.msg, 'error'); setStatus('加载失败'); }
      }
    } catch(err) { appendTip('导入失败: ' + err, 'error'); setStatus('导入失败'); }
    input.value = '';
  };
  reader.readAsArrayBuffer(file);
}

function renderBOMTable(items) {
  const tbody = document.querySelector('#bomTable tbody');
  tbody.innerHTML = items.map((item, i) => `
    <tr>
      <td style="color:var(--text-muted);text-align:right;padding-right:8px;width:28px">${i + 1}</td>
      <td>${escapeHtml(item.reference)}</td>
      <td>${escapeHtml(item.value)}</td>
      <td>${escapeHtml(item.package)}</td>
      <td>${escapeHtml(item.part_number)}</td>
      <td style="text-align:right">${item.quantity}</td>
    </tr>
  `).join('');
  document.getElementById('bomEmpty').style.display = items.length ? 'none' : 'flex';
}

// ═══════════ Panel Tabs ═══════════

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const btn = document.querySelector(`[data-tab="${name}"]`);
  if (btn) btn.classList.add('active');
  const panel = document.getElementById(`tab-${name}`);
  if (panel) panel.classList.add('active');
}

function toggleRightPanel() {
  const panel = document.getElementById('rightPanel');
  const btn = document.getElementById('panelToggleBtn');
  const collapsed = panel.classList.toggle('collapsed');
  const chevronRight = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,3 11,8 6,13"/></svg>';
  const chevronLeft  = '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="10,3 5,8 10,13"/></svg>';
  if (collapsed) {
    btn.innerHTML = chevronLeft;
    btn.classList.add('collapsed');
  } else {
    btn.innerHTML = chevronRight;
    btn.classList.remove('collapsed');
  }
}

// ═══════════ Theme & Accent ═══════════

var _currentAccent = '#5b8def';

function applyTheme(name) {
  document.body.setAttribute('data-theme', name);
  try { eel.save_theme(name)(); } catch(e) {}
  // update theme radio buttons
  document.querySelectorAll('.theme-card input').forEach(function(r) {
    r.checked = r.value === name;
  });
}

function setAccentColor(color, btn) {
  _currentAccent = color;
  document.documentElement.style.setProperty('--accent', color);
  document.documentElement.style.setProperty('--accent-hover', color + 'dd');
  document.querySelectorAll('.accent-dot').forEach(function(d) { d.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  try { eel.save_accent(color)(); } catch(e) {}
}

function setFontSize(size, btn) {
  document.documentElement.style.setProperty('--font-size', size + 'px');
  document.querySelectorAll('.font-size-btn').forEach(function(b) { b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  try { eel.save_font_size(size)(); } catch(e) {}
}

// ═══════════ Premium Settings ═══════════

var PROVIDERS = {
  deepseek:  { icon: 'DS', name: 'DeepSeek', url: 'https://api.deepseek.com/v1', models: ['deepseek-v4-pro', 'deepseek-v4.5-flash', 'deepseek-v4-flash'], defaultModel: 'deepseek-v4-pro', desc: 'DeepSeek V4-Pro / 1.6T MoE / 100万上下文' },
  openai:    { icon: 'OA', name: 'OpenAI', url: 'https://api.openai.com/v1', models: ['gpt-5.5', 'gpt-5.4', 'gpt-5.3', 'gpt-4o', 'gpt-4o-mini', 'o4-mini'], defaultModel: 'gpt-5.5', desc: 'GPT-5.5 / 最新旗舰 / 多模态' },
  gemini:    { icon: 'GM', name: 'Gemini', url: 'https://generativelanguage.googleapis.com/v1beta/openai', models: ['gemini-3.5-flash', 'gemini-3.1-pro-preview', 'gemini-3.1-flash-lite', 'gemini-3.0-flash-preview', 'gemini-2.5-pro', 'gemini-2.5-flash'], defaultModel: 'gemini-3.5-flash', desc: 'Gemini 3.5 Flash / 最新稳定 GA / Agent & Coding' },
  claude:    { icon: 'CL', name: 'Claude', url: 'https://api.anthropic.com/v1/messages', models: ['claude-opus-4-8', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'], defaultModel: 'claude-opus-4-8', desc: 'Claude Opus 4.8 / 原生 Messages API / 200K上下文' },
  qwen:      { icon: 'QW', name: '通义千问', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen3.7-max', 'qwen3.6-plus', 'qwen3.6-flash', 'qwen3-coder-plus'], defaultModel: 'qwen3.7-max', desc: '通义千问 3.7-Max / 最新旗舰 (2026.05)' },
  glm:       { icon: 'GL', name: '智谱', url: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-5.1', 'glm-5.1-flash', 'glm-5.1-coder'], defaultModel: 'glm-5.1', desc: 'GLM-5.1 / 全自治旗舰' },
  moonshot:  { icon: 'KM', name: 'Kimi', url: 'https://api.moonshot.cn/v1', models: ['kimi-k2.6', 'kimi-k2-flash'], defaultModel: 'kimi-k2.6', desc: 'Kimi K2.6 / 1T MoE / Agent集群' },
  doubao:    { icon: 'DB', name: '豆包', url: 'https://ark.cn-beijing.volces.com/api/v3', models: ['doubao-1.5-pro-256k', 'doubao-1.5-lite-32k'], defaultModel: 'doubao-1.5-pro-256k', desc: '豆包 1.5 Pro / 字节跳动 / 256K上下文' },
  minimax:   { icon: 'MM', name: 'MiniMax', url: 'https://api.minimax.io/v1', models: ['MiniMax-M3', 'MiniMax-M2.7', 'MiniMax-M2.5'], defaultModel: 'MiniMax-M3', desc: 'MiniMax M3 / 最新旗舰 / 1M上下文' },
  siliconflow: { icon: 'SF', name: '硅基流动', url: 'https://api.siliconflow.cn/v1', models: ['deepseek-ai/DeepSeek-V4-Flash', 'Qwen/Qwen3.6-Plus', 'Pro/Claude-Opus-4.8'], defaultModel: 'deepseek-ai/DeepSeek-V4-Flash', desc: '聚合 API / 多模型路由 / 高性价比' },
};

var _selectedProvider = 'deepseek';
var SETTINGS_LOADED = false;

// ── Settings tabs ──
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.settings-nav-item').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var tab = this.getAttribute('data-tab');
      switchSettingsTab(tab);
    });
  });
  renderProviderCards();
});

function switchSettingsTab(tabId) {
  document.querySelectorAll('.settings-nav-item').forEach(function(b) { b.classList.remove('active'); });
  document.querySelector('[data-tab="' + tabId + '"]').classList.add('active');
  document.querySelectorAll('.settings-tab').forEach(function(t) { t.classList.remove('active'); });
  document.getElementById(tabId).classList.add('active');
}

// ── Provider cards ──
function renderProviderCards() {
  var container = document.getElementById('providerCards');
  if (!container) return;
  container.innerHTML = '';
  Object.keys(PROVIDERS).forEach(function(key) {
    var p = PROVIDERS[key];
    var card = document.createElement('div');
    card.className = 'provider-card' + (key === _selectedProvider ? ' selected' : '');
    card.innerHTML = '<div class="provider-card-icon provider-icon-text">' + p.icon + '</div>' +
      '<div class="provider-card-name">' + p.name + '</div>' +
      '<div class="provider-card-model">' + p.desc + '</div>';
    card.setAttribute('data-provider', key);
    card.addEventListener('click', function() { selectProvider(key, card); });
    container.appendChild(card);
  });
}

function selectProvider(key, card) {
  _selectedProvider = key;
  document.querySelectorAll('.provider-card').forEach(function(c) { c.classList.remove('selected'); });
  if (card) card.classList.add('selected');
  // update URL placeholder
  var p = PROVIDERS[key] || {};
  document.getElementById('setBaseUrl').placeholder = p.url || '';
  // update model selector
  var sel = document.getElementById('setModelSelect');
  sel.innerHTML = '';
  (p.models || []).forEach(function(m) {
    var opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    if (m === p.defaultModel) opt.selected = true;
    sel.appendChild(opt);
  });
  var custom = document.createElement('option');
  custom.value = '__custom__'; custom.textContent = '自定义模型...';
  sel.appendChild(custom);
  document.getElementById('setModelCustom').style.display = 'none';
}

function onModelSelectChange() {
  var sel = document.getElementById('setModelSelect');
  document.getElementById('setModelCustom').style.display = sel.value === '__custom__' ? 'block' : 'none';
}

// ── Connection test ──
async function testConnection() {
  var btn = document.querySelector('.btn-test-conn');
  var icon = document.getElementById('connTestIcon');
  var text = document.getElementById('connTestText');
  var result = document.getElementById('connTestResult');
  if (!btn) return;
  btn.disabled = true; icon.textContent = ''; icon.className = 'spinner'; text.textContent = '检测中...';
  result.textContent = ''; result.style.color = '';

  var provider = _selectedProvider;
  var apiKey = document.getElementById('setApiKey').value;
  var baseUrl = document.getElementById('setBaseUrl').value || (PROVIDERS[provider] || {}).url || '';
  var modelSel = document.getElementById('setModelSelect');
  var model = modelSel.value === '__custom__' ? document.getElementById('setModelCustom').value : modelSel.value;
  if (!model) model = (PROVIDERS[provider] || {}).defaultModel || '';

  try {
    var resp = await eel.test_llm_connection(provider, apiKey, baseUrl, model)();
    if (resp.ok) {
      icon.textContent = ''; icon.className = '';
      text.textContent = '连接成功';
      result.textContent = resp.latency ? '延迟 ' + resp.latency + 'ms' : '';
      result.style.color = '#2ecc71';
    } else {
      icon.textContent = ''; icon.className = '';
      text.textContent = '连接失败';
      result.textContent = resp.error || '未知错误';
      result.style.color = '#e74c3c';
    }
  } catch(e) {
    icon.textContent = ''; icon.className = '';
    text.textContent = '连接失败';
    result.textContent = e.message || '网络错误';
    result.style.color = '#e74c3c';
  }
  btn.disabled = false;
}

// ── Toggle settings ──
function toggleSettings() {
  var overlay = document.getElementById('settingsOverlay');
  overlay.classList.toggle('show');
  if (overlay.classList.contains('show') && !SETTINGS_LOADED) {
    SETTINGS_LOADED = true;
    loadSettingsIntoUI();
  }
}

async function loadSettingsIntoUI() {
  try {
    var sett = await eel.get_settings()();
    if (!sett) return;
    _selectedProvider = sett.provider || 'deepseek';
    document.getElementById('setApiKey').value = sett.api_key || '';
    document.getElementById('setBaseUrl').value = sett.base_url || '';
    if (sett.temperature != null) {
      document.getElementById('setTemperature').value = sett.temperature;
      document.getElementById('tempDisplay').textContent = sett.temperature;
    }
    // update provider cards
    renderProviderCards();
    // update model selector
    selectProvider(_selectedProvider);
    var savedModel = sett.model || '';
    if (savedModel) {
      var sel = document.getElementById('setModelSelect');
      var found = false;
      for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === savedModel) { sel.selectedIndex = i; found = true; break; }
      }
      if (!found && savedModel) {
        sel.value = '__custom__';
        document.getElementById('setModelCustom').value = savedModel;
        document.getElementById('setModelCustom').style.display = 'block';
      }
    }
    // theme
    if (sett.theme) {
      applyTheme(sett.theme);
    }
    // accent
    if (sett.accent) {
      setAccentColor(sett.accent);
      document.querySelectorAll('.accent-dot').forEach(function(d) {
        if (d.getAttribute('data-accent') === sett.accent) d.classList.add('active');
      });
    }
    // font size
    if (sett.font_size) {
      document.querySelectorAll('.font-size-btn').forEach(function(b) {
        b.classList.toggle('active', b.getAttribute('data-size') === String(sett.font_size));
      });
      document.documentElement.style.setProperty('--font-size', sett.font_size + 'px');
    }
    // data dir
    if (sett.data_dir) {
      document.getElementById('setDataDir').value = sett.data_dir;
    }
  } catch(e) { console.error('Load settings failed:', e); }
}

function closeSettings(e) {
  if (!e || e.target === document.getElementById('settingsOverlay')) {
    document.getElementById('settingsOverlay').classList.remove('show');
  }
}

// ── Save all settings ──
async function saveAllSettings() {
  var status = document.getElementById('settingsStatus');
  if (status) { status.textContent = '保存中...'; status.style.color = ''; }

  var provider = _selectedProvider;
  var apiKey = document.getElementById('setApiKey').value;
  var baseUrl = document.getElementById('setBaseUrl').value;
  var modelSel = document.getElementById('setModelSelect');
  var model = modelSel.value === '__custom__'
    ? document.getElementById('setModelCustom').value
    : modelSel.value;
  if (!model) model = (PROVIDERS[provider] || {}).defaultModel || '';
  var temperature = parseFloat(document.getElementById('setTemperature').value) || 0.7;
  var theme = document.body.getAttribute('data-theme') || 'dark';
  var accent = _currentAccent;

  try {
    var resp = await eel.save_all_settings(provider, apiKey, baseUrl, model, temperature, theme, accent)();
    if (resp.ok) {
      if (status) { status.textContent = '设置已保存'; status.style.color = '#2ecc71'; }
      setTimeout(function() { document.getElementById('settingsOverlay').classList.remove('show'); }, 600);
    } else {
      if (status) { status.textContent = '保存失败: ' + (resp.error || ''); status.style.color = '#e74c3c'; }
    }
  } catch(e) {
    if (status) { status.textContent = '' + (e.message || '保存失败'); status.style.color = '#e74c3c'; }
  }
}

// ── Misc ──
function toggleApiKeyVisibility(btn) {
  var input = btn.parentElement.querySelector('input');
  if (input.type === 'password') { input.type = 'text'; btn.textContent = 'Hide'; }
  else { input.type = 'password'; btn.textContent = 'Show'; }
}

function openDataDir() {
  var dir = document.getElementById('setDataDir').value;
  if (dir) { window.open('file:///' + dir.replace(/\\/g, '/')); }
}

async function clearAllData() {
  if (!confirm('确定要清除所有本地数据吗？此操作不可撤销。')) return;
  try {
    await eel.clear_all_data()();
    alert('数据已清除。应用将重新加载。');
    location.reload();
  } catch(e) { alert('清除失败: ' + e.message); }
}

// ═══════════ Utils ═══════════

function setStatus(msg) { /* simplified — no status bar in new UI */ }
function disableInput(disabled) {
  document.getElementById('chatInput').disabled = disabled;
  document.getElementById('sendBtn').disabled = disabled;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}

function escapeAttr(str) {
  return String(str).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ═══════════ Confirm Dialog ═══════════

let _confirmCallback = null;

function showConfirmDialog({ title, message, okText, onOk }) {
  document.getElementById('confirmTitle').textContent = title || '确认操作';
  document.getElementById('confirmMessage').textContent = message || '';
  const okBtn = document.getElementById('confirmOkBtn');
  okBtn.textContent = okText || '确定';
  _confirmCallback = onOk || null;
  okBtn.onclick = () => {
    const cb = _confirmCallback;
    closeConfirmDialog();
    if (cb) cb();
  };
  document.getElementById('confirmOverlay').classList.add('show');
  // Focus the cancel button by default (safer)
  document.getElementById('confirmCancelBtn').focus();
}

function closeConfirmDialog() {
  document.getElementById('confirmOverlay').classList.remove('show');
  _confirmCallback = null;
}

// Close on Escape key
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (document.getElementById('confirmOverlay').classList.contains('show')) {
      closeConfirmDialog();
    } else if (document.getElementById('newAssistantOverlay').classList.contains('show')) {
      closeNewAssistantDialog();
    }
  }
});

// Called by Python file watcher
eel.expose(onPCBChanged, 'on_pcb_changed');
function onPCBChanged(filepath) {
  appendSystem(`[PCB]  检测到 PCB 文件变化: ${filepath}`);
}

// ── Streaming callbacks (called by Python) ──

eel.expose(onStreamToken, 'on_stream_token');
function onStreamToken(token) {
  if (_activeStreamBubble) {
    _streamTokenCount++;
    _activeStreamBubble.updateToken(token);
  }
}

eel.expose(onStreamDone, 'on_stream_done');
function onStreamDone(fullText) {
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
}

eel.expose(onStreamError, 'on_stream_error');
function onStreamError(errorMsg) {
  if (_activeStreamBubble) {
    _activeStreamBubble.finalize(' 流式输出中断: ' + errorMsg);
    const conv = getActiveConversation();
    conv.messages.push({ role: 'ai', content: _activeStreamBubble.getText() });
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }
  disableInput(false);
  setStatus('错误');
}

// ══════════════════════════════════════════
//  Multi-Agent Review
// ══════════════════════════════════════════

async function runMultiAgentReview() {
  const startBtn = document.querySelector('.review-start-btn');
  const resultDiv = document.getElementById('reviewResult');
  const emptyHint = document.getElementById('reviewEmpty');
  if (startBtn) startBtn.disabled = true;
  if (emptyHint) emptyHint.style.display = 'none';
  setStatus('多智能体审查中...');

  try {
    const raw = await eel.review_design_multi_agent()();
    const data = JSON.parse(raw);
    if (data.error) { setStatus('审查失败'); if (startBtn) startBtn.disabled = false; alert(data.error); return; }
    renderReviewResult(data);
    if (resultDiv) resultDiv.style.display = 'block';
    if (startBtn) startBtn.style.display = 'none';
    setStatus('审查完成');
  } catch (e) { console.error(e); setStatus('审查失败'); if (startBtn) startBtn.disabled = false; }
}

function renderReviewResult(data) {
  if (data.radar_data) drawRadarChart(data.radar_data);
  const ge = document.getElementById('reviewGrade');
  const se = document.getElementById('reviewScore');
  if (ge) { ge.textContent = data.overall_grade || '?'; ge.style.color = _gradeColor(data.overall_score); }
  if (se) se.textContent = data.overall_score != null ? data.overall_score : '?';
  const ce = document.getElementById('reviewConsensus');
  if (ce) ce.innerHTML = data.consensus || '';
  _renderAgentCards(data.agents);
  _renderRoadmap(data.improvement_roadmap);
}

function drawRadarChart(data) {
  var c = document.getElementById('radarChart');
  if (!c || !data || data.length < 3) return;
  var ctx = c.getContext('2d'), w = c.width, h = c.height, cx = w / 2, cy = h / 2;
  var n = data.length, maxR = Math.min(cx, cy) - 20;
  ctx.clearRect(0, 0, w, h);
  // grid
  for (var lv = 1; lv <= 4; lv++) {
    var r = (maxR / 4) * lv; ctx.beginPath();
    for (var i = 0; i < n; i++) {
      var a = (Math.PI * 2 / n) * i - Math.PI / 2;
      var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath(); ctx.strokeStyle = '#e0e4ea'; ctx.lineWidth = 0.5; ctx.stroke();
  }
  // axes
  for (var i = 0; i < n; i++) {
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + maxR * Math.cos(a), cy + maxR * Math.sin(a));
    ctx.strokeStyle = '#e0e4ea'; ctx.lineWidth = 0.5; ctx.stroke();
  }
  // polygon
  ctx.beginPath();
  for (var i = 0; i < n; i++) {
    var d = data[i], r = (d.score / 100) * maxR;
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath(); ctx.fillStyle = 'rgba(91,141,239,0.15)'; ctx.fill();
  ctx.strokeStyle = '#5b8def'; ctx.lineWidth = 1.5; ctx.stroke();
  // dots + labels
  ctx.font = '9px sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = '#555';
  for (var i = 0; i < n; i++) {
    var d = data[i], r = (d.score / 100) * maxR;
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath(); ctx.arc(cx + r * Math.cos(a), cy + r * Math.sin(a), 3, 0, Math.PI * 2);
    ctx.fillStyle = d.color || '#5b8def'; ctx.fill();
    ctx.fillText(d.label, cx + (maxR + 14) * Math.cos(a), cy + (maxR + 14) * Math.sin(a) + 3);
  }
}

function _renderAgentCards(agents) {
  var ct = document.getElementById('reviewAgentCards');
  if (!ct || !agents) return; ct.innerHTML = '';
  var order = ['power', 'signal', 'thermal', 'emc', 'dfm'];
  for (var o = 0; o < order.length; o++) {
    var a = agents[order[o]]; if (!a) continue;
    var hasCrit = a.findings && a.findings.some(function(f) { return f.severity === 'critical'; });
    var cls = hasCrit ? 'critical' : (a.score >= 90 ? 'clean' : 'major');
    var fhtml = '';
    if (a.findings && a.findings.length) {
      fhtml = a.findings.map(function(f) {
        return '<div class="review-finding sev-' + f.severity + '">' + f.title + (f.suggestion ? ' — ' + f.suggestion : '') + '</div>';
      }).join('');
    }
    ct.innerHTML += '<div class="review-agent-card ' + cls + '">' +
      '<div class="review-agent-header"><span>' + (a.emoji || '') + '</span> ' +
      '<span class="review-agent-name">' + a.name + '</span>' +
      '<span class="review-agent-score">' + (a.score != null ? a.score.toFixed(1) : '?') + ' 分</span></div>' +
      '<div class="review-agent-summary">' + (a.summary || '') + '</div>' +
      (fhtml ? '<div class="review-agent-findings">' + fhtml + '</div>' : '') + '</div>';
  }
}

function _renderRoadmap(items) {
  var ct = document.getElementById('reviewRoadmap');
  if (!ct || !items || !items.length) return;
  ct.innerHTML = '<h3> 改进路线图</h3>' + items.map(function(i) { return '<div class="review-roadmap-item">' + i + '</div>'; }).join('');
}

function _gradeColor(score) {
  if (score == null) return '#888';
  if (score >= 88) return '#2ecc71';
  if (score >= 70) return '#5b8def';
  if (score >= 55) return '#e67e22';
  return '#e74c3c';
}

// ═══════════ Toast Notifications ═══════════

function showToast(msg, type) {
  type = type || 'info';
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  t.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:9999;' +
    'padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;' +
    'animation:toastIn .3s ease;pointer-events:none;' +
    (type === 'success' ? 'background:#2ecc71;color:#fff;' :
     type === 'error' ? 'background:#e74c3c;color:#fff;' :
     'background:var(--accent);color:#fff;');
  document.body.appendChild(t);
  setTimeout(function() { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; }, 2500);
  setTimeout(function() { if (t.parentNode) t.parentNode.removeChild(t); }, 3000);
}

// ═══════════ Design Suggestions (proactive) ═══════════

async function showDesignSuggestions() {
  try {
    var raw = await eel.get_design_suggestions()();
    if (!raw) return;
    // Show in right panel report tab
    var stack = document.getElementById('reportStack');
    if (stack) {
      var div = document.createElement('div');
      div.className = 'design-suggestion-card';
      div.innerHTML = '<div class="design-suggestion-title">AI 设计意图识别</div>' +
        '<div class="design-suggestion-body">' + marked.parse(raw) + '</div>';
      stack.insertBefore(div, stack.firstChild);
    }
    // Also toast
    var firstLine = raw.split('\n')[1] || '';
    if (firstLine) showToast('AI: ' + firstLine.replace(/^#+\s*/, '').replace(/\[.*?\]/, '').trim(), 'info');
  } catch(e) { /* silent */ }
}

// ═══════════ Keyboard Shortcuts ═══════════

document.addEventListener('keydown', function(e) {
  // Ctrl+Enter: send message
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault();
    sendChat();
    return;
  }
  // Escape: close settings/modal
  if (e.key === 'Escape') {
    var overlay = document.getElementById('settingsOverlay');
    if (overlay && overlay.classList.contains('show')) {
      closeSettings();
      return;
    }
  }
  // Ctrl+B: import BOM
  if (e.ctrlKey && e.key === 'b') {
    e.preventDefault();
    document.getElementById('bomFileInput').click();
    return;
  }
  // Ctrl+R: run multi-agent review
  if (e.ctrlKey && e.key === 'r') {
    e.preventDefault();
    runMultiAgentReview();
    return;
  }
});

// ═══════════ Keyboard shortcut hint ═══════════

(function addShortcutHints() {
  var input = document.getElementById('chatInput');
  if (input) {
    input.title = 'Enter 发送 | Shift+Enter 换行 | Ctrl+Enter 快速发送 | Ctrl+B 导入BOM | Ctrl+R 多智能体审查';
  }
})();
