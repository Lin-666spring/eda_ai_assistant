/* ═══════════════════════════════════════════
   EDA AI 智能助手 — Cherry Studio Frontend
   ═══════════════════════════════════════════ */

// ═══════════ State ═══════════

const ASSISTANT_TYPES = {
  'eda-general': {
    typeId: 'eda-general', name: 'EDA 通用助手', icon: '(´｡• ᵕ •｡`)',
    systemPrompt: 'general',
    quickActions: ['合并 BOM', '校验封装', '设计规则', 'BOM健康', '查询知识库'],
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
    quickActions: ['设计规则', '分析PCB', '检查走线', '查看PCB', '查询知识库'],
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

  // 统一工具目录（后端 ToolRegistry 派生）— 视图与工具箱共用
  await loadToolCatalog();
  updateSessionBar();
  renderConversations();

  // Default to BOM analysis view (two-level navigation)
  if (!activeConvId || (getActiveConversation() && (getActiveConversation().messages||[]).length === 0)) {
    switchView('bom');
  }

  // Theme — 以 settings 为准，未知值一律回落浅色
  try {
    const sett = await eel.get_settings()();
    if (sett && sett.theme) applyTheme(sett.theme);
    if (sett && sett.font_size) {
      document.documentElement.style.setProperty('--font-size', sett.font_size + 'px');
    }
  } catch(e) {}

  // LLM config
  try {
    const cfg = await eel.get_llm_config()();
    updateLLMStatus(cfg);
  } catch(e) {}

  // Right-panel tab switching
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

  // 无持久化数据 → 自动创建默认助手实例（首跑引导）
  if (!saved || saved.length === 0) {
    // ⚠️ typeId 必须是 ASSISTANT_TYPES 里真实存在的键。
    //    过去写的是 'general'（不存在）→ createAssistantInstance 返回 null
    //    → 紧接着读 inst.instanceId 直接抛异常，首跑白屏（2026-09-10 修正）。
    const inst = createAssistantInstance('eda-general');
    if (inst) currentAssistantInstance = inst.instanceId;
    conversations[currentAssistantInstance] = conversations[currentAssistantInstance] || [];
    updateSessionBar();
    _persistState();
    // First run → show BOM analysis view as the landing screen
    switchView('bom');
    return;
  }

  // 恢复助手实例
  assistantInstances = saved.map(a => ({
    instanceId: a.instance_id,
    typeId: a.type_id,
    name: a.name,
  }));
  // ⚠️ 归一化：SessionStore.load_all() 返回的会话记录字段是
  //    {conv_id, title, sort_order}（没有 id / messages），直接用会导致
  //    switchConversation() 里 `conv.messages.length` 抛 undefined
  //    （2026-09-10 实测：切换助手即崩，历史会话根本打不开）。
  conversations = {};
  saved.forEach(a => {
    conversations[a.instance_id] = (savedConvs[a.instance_id] || []).map(c => ({
      id: c.id || c.conv_id,
      title: c.title || '新对话',
      messages: c.messages || [],
    }));
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
  } else {
    // No conversations → land on BOM analysis view
    switchView('bom');
  }
}

async function restoreConversationMessages(convId) {
  let resp;
  try { resp = await eel.db_load_messages(convId)(); } catch(e) { return; }
  if (!resp || !resp.ok) return;
  const msgs = resp.messages || [];
  // 回填到会话对象，否则切走再切回来消息就没了（messages 一直是空的）
  const conv = findConversation(convId);
  if (conv) {
    conv.messages = msgs.map(m => ({
      role: m.role,
      content: m.content,
      image: m.image || undefined,
    }));
  }
  if (msgs.length === 0) { switchView(_currentView || 'bom'); return; }
  // Has messages → show chat stream, hide view
  const vc = document.getElementById('viewContainer');
  const cm = document.getElementById('chatMessages');
  if (vc) vc.classList.add('hidden');
  if (cm) cm.classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  msgs.forEach(m => {
    if (m.image) {
      appendBubbleWithImage(m.role, m.content, m.image);
    } else {
      appendBubble(m.role, m.content);
    }
  });
  renderConversations();
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
  // Legacy: sidebar tabs removed in the two-level nav redesign. Kept as no-op
  // so existing callers (e.g. newConversation) don't throw.
  sidebarTab = tab;
}

// ═══════════ Assistant Management ═══════════

function getActiveAssistant() {
  const inst = assistantInstances.find(i => i.instanceId === currentAssistantInstance);
  if (!inst) return null;
  const type = ASSISTANT_TYPES[inst.typeId];
  return { ...type, instanceId: inst.instanceId, name: inst.name };
}

function renderAssistants() {
  const container = document.getElementById('configAssistantList');
  const countEl = document.getElementById('configAssistantCount');
  if (countEl) countEl.textContent = `${assistantInstances.length} 个`;
  if (!container) return;  // only render when config view is active
  if (assistantInstances.length === 0) {
    container.innerHTML = '<div class="session-empty">暂无助手，点击下方按钮新建</div>';
    return;
  }
  container.innerHTML = assistantInstances.map(inst => {
    const type = ASSISTANT_TYPES[inst.typeId];
    if (!type) return '';
    const active = inst.instanceId === currentAssistantInstance ? 'active' : '';
    return `
      <div class="assistant-row ${active}"
           onclick="selectAssistant('${inst.instanceId}')" title="${type.description}">
        <span class="assistant-row-icon">${type.icon}</span>
        <span class="assistant-row-body">
          <span class="assistant-row-name">${escapeHtml(inst.name)}</span>
          <span class="assistant-row-desc">${escapeHtml(type.description)}</span>
        </span>
        <span class="assistant-row-badge">${type.quickActions.length} 个快捷操作</span>
        <button class="assistant-row-del" onclick="deleteAssistant('${inst.instanceId}', event)" title="删除助手">
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
    clearChatMessages();
    showEmptyState(true);
  }
  updateSessionBar();
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

function updateSessionBar() {
  // 顶栏只有一个「会话」入口，助手身份显示在下拉头部。
  const a = getActiveAssistant();
  const owner = document.getElementById('sessionMenuAssistant');
  if (owner) owner.textContent = a ? a.name : '未创建助手';
  const chip = document.getElementById('sessionChipName');
  const conv = activeConvId ? findConversation(activeConvId) : null;
  if (chip) chip.textContent = conv ? conv.title : (a ? '新对话' : '未创建助手');
}

// 兼容旧调用点
function updateChatHeader() { updateSessionBar(); }

// ── 会话下拉（conversations 的唯一 UI 入口） ──

function toggleSessionMenu(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const menu = document.getElementById('sessionMenu');
  if (!menu) return;
  const willOpen = !menu.classList.contains('show');
  menu.classList.toggle('show', willOpen);
  if (willOpen) renderConversations();
}

function closeSessionMenu() {
  const menu = document.getElementById('sessionMenu');
  if (menu) menu.classList.remove('show');
}

document.addEventListener('click', (e) => {
  const wrap = document.getElementById('sessionWrap');
  if (wrap && !wrap.contains(e.target)) closeSessionMenu();
});

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
  const input = document.getElementById('chatInput');
  if (companionMode) {
    document.body.classList.add('companion-mode');
    btn.classList.add('active');
    // 380px 宽的伴生窗里长 placeholder 会被裁掉，用短文案
    if (input && !agentMode) input.placeholder = '输入指令…';
    window.resizeTo(380, 540);
    window.moveTo(screen.width - 400, 40);
  } else {
    document.body.classList.remove('companion-mode');
    btn.classList.remove('active');
    if (input && !agentMode) input.placeholder = '输入审查指令或问题... (Enter 发送, Shift+Enter 换行)';
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
  const msgs = (conv && conv.messages) || [];
  if (msgs.length > 0) {
    msgs.forEach(m => appendBubble(m.role, m.content, m.image));
  } else {
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
      const convs = conversations[currentAssistantInstance] || [];
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
  updateSessionBar();
  const container = document.getElementById('conversationList');
  if (!container) return;
  if (!currentAssistantInstance) {
    container.innerHTML = '<div class="session-empty">请先新建助手</div>';
    return;
  }
  const convs = conversations[currentAssistantInstance] || [];
  if (convs.length === 0) {
    container.innerHTML = '<div class="session-empty">暂无历史会话</div>';
    return;
  }
  container.innerHTML = convs.map(c => {
    const n = (c.messages || []).length;
    return `
    <div class="session-item ${c.id === activeConvId ? 'active' : ''}"
         onclick="switchConversation('${c.id}'); closeSessionMenu();" title="${escapeAttr(c.title)}">
      <svg class="session-item-icon" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h9A1.5 1.5 0 0 1 14 4.5v5A1.5 1.5 0 0 1 12.5 11H6l-3 2.5V11h-.5A1.5 1.5 0 0 1 2 9.5z"/></svg>
      <span class="session-item-name">${escapeHtml(c.title)}</span>
      <span class="session-item-count">${n}</span>
      <button class="session-item-del" onclick="deleteConversation('${c.id}', event)" title="删除会话">
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>
      </button>
    </div>`;
  }).join('');
}

// ═══════════ Chat ═══════════

function clearChatMessages() {
  // Abort any in-progress stream
  _activeStreamBubble = null;
  _streamTokenCount = 0;
  _activeToolCards.forEach(c => c.remove());
  _activeToolCards = [];
  const container = document.getElementById('chatMessages');
  if (!container) return;
  // ⚠️ 只能保留空态占位节点，其余一律清掉。
  // 过去只删 `.msg-row,.config-tip`，而流式 AI 气泡（裸 .bubble）和
  // `.tool-call-card` 都不带 .msg-row，切换助手/会话后它们会留在 DOM 里，
  // 造成「同一个回答显示两遍」（2026-09-10 实测：bareBubbles 存活 1 个）。
  Array.from(container.children).forEach(el => {
    if (el.id !== 'chatEmpty') el.remove();
  });
  _syncChatEmpty();
}

// ═══════════ Chat empty-state sync ═══════════
function _syncChatEmpty() {
  const cm = document.getElementById('chatMessages');
  const ce = document.getElementById('chatEmpty');
  if (!cm || !ce) return;
  ce.style.display = cm.querySelectorAll('.msg-row').length ? 'none' : '';
}
(function() {
  const cm = document.getElementById('chatMessages');
  if (cm) new MutationObserver(_syncChatEmpty).observe(cm, { childList: true, subtree: true });
})();

// ═══════════ 统一工具目录 (ToolRegistry 是唯一事实来源) ═══════════
//
// 前端不再复制工具的名称/描述/关键词：全部来自 eel.get_tools_catalog()，
// 也就是 src/agent/tools.py 的 ToolRegistry。视图只声明「展示哪些工具」，
// 卡片样式、状态徽标、运行入口全部统一。

const TOOL_CATEGORIES = {
  bom:    { label: 'BOM 物料', short: 'BOM',   tone: 'blue' },
  pcb:    { label: 'PCB 设计', short: 'PCB',   tone: 'violet' },
  health: { label: '供应链健康', short: '供应链', tone: 'green' },
  report: { label: '报告导出', short: '报告',   tone: 'amber' },
  vision: { label: '视觉分析', short: '视觉',   tone: 'pink' },
};

// tool name → ICONS 中的 emoji 键（统一走同一套线性 SVG 图标）
const TOOL_ICONS = {
  ai_merge_bom: '🤖', merge_bom: '🔗', validate_package: '📐',
  check_duplicates: '🔍', filter_components: '🧲',
  generate_html_bom: '🌐', export_bom_csv: '📤', summary_report: '📊',
  bom_cost_summary: '💰', bom_health: '🩺', find_alternatives: '🔁', supply_risk: '🚚',
  check_rule: '📐', pcb_status: '🖥️', pcb_analysis: '🧩', calc_trace_width: '📏',
  explain_design_rule: '📖', generate_drc_rule: '🧾', review_multi_agent: '👥',
  verify_suggestion: '✅', component_lookup: '🔎', search_component: '🔍',
  analyze_image: '🖼️', rag_query: '📚',
};

// 少数能力的启动方式不是「直接执行」
const TOOL_LAUNCH = {
  review_multi_agent: { kind: 'run', run: () => featureCmd('__review') },
  generate_html_bom:  { kind: 'run', run: () => generateHTMLBOM() },
  analyze_image:      { kind: 'image' },
  rag_query:          { kind: 'prompt', prefix: '查询知识库: ' },
};

let TOOL_CATALOG = [];
let _toolQuery = '';
let _toolCategory = 'all';
let _toolOnlyReady = false;

async function loadToolCatalog(force) {
  if (TOOL_CATALOG.length && !force) return TOOL_CATALOG;
  try {
    const resp = await eel.get_tools_catalog()();
    TOOL_CATALOG = (resp && resp.ok && resp.tools) ? resp.tools : [];
  } catch (e) {
    console.warn('工具目录加载失败', e);
    TOOL_CATALOG = [];
  }
  return TOOL_CATALOG;
}

function getTool(name) {
  return TOOL_CATALOG.find(t => t.name === name) || null;
}

/** 数据可用性变了（导入 BOM / PCB / 坐标、一键演示）后刷新工具目录。
 *  可用性是后端按「当前有没有 BOM」实时算的，不刷新的话工具箱里的
 *  「需先导入 BOM」徽标会一直停在旧状态。 */
async function refreshToolCatalog() {
  await loadToolCatalog(true);
  const vc = document.getElementById('viewContainer');
  const view = VIEWS[_currentView];
  // 只在视图可见时就地重绘；聊天流模式下不要把用户拽回视图
  if (vc && view && !vc.classList.contains('hidden')) {
    const keepScroll = vc.scrollTop;
    vc.innerHTML = renderViewHTML(view);
    if (view.hub) renderToolGrid();
    if (view.assistantSection) renderAssistants();
    vc.scrollTop = keepScroll;
  }
  return TOOL_CATALOG;
}

function _toolState(t) {
  // 顺序很重要：先把「没数据跑不了」判掉，否则像 generate_html_bom /
  // review_multi_agent 这种走面板的能力会显示「面板直达」，掩盖了它还缺 BOM。
  if (!t.ready) return { key: 'blocked', text: t.blocked_reason || '不可用' };
  const spec = TOOL_LAUNCH[t.name];
  if (spec && spec.kind === 'run') return { key: 'panel', text: '面板直达' };
  if (spec && spec.kind === 'image') return { key: 'input', text: '需上传图片' };
  if (t.needs_input) return { key: 'input', text: '需补参数' };
  return { key: 'ready', text: '可直接运行' };
}

/** 统一工具卡片 — 工具箱与各视图共用同一个组件 */
function renderToolCard(t, index) {
  const cat = TOOL_CATEGORIES[t.category] || { short: t.category, tone: 'blue' };
  const st = _toolState(t);
  const icon = ICONS[TOOL_ICONS[t.name]] || ICONS['⚙️'] || '';
  return `<article class="tool-card" data-tool="${t.name}" data-cat="${t.category}" data-state="${st.key}"
      style="--i:${index || 0}" onclick="launchTool('${t.name}')" title="${escapeAttr(t.description)}">
    <div class="tool-card-top">
      <span class="tool-card-icon">${icon}</span>
      <span class="tool-card-cat tone-${cat.tone}">${cat.short}</span>
    </div>
    <div class="tool-card-label">${escapeHtml(t.label)}</div>
    <p class="tool-card-desc">${escapeHtml(t.description)}</p>
    <div class="tool-card-foot">
      <span class="tool-card-state ${st.key}"><i class="state-dot"></i>${escapeHtml(st.text)}</span>
      <span class="tool-card-go">运行<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,3 11,8 6,13"/></svg></span>
    </div>
  </article>`;
}

/** 非工具类快捷入口也用同一种卡片外观，保持视觉统一 */
function renderActionCard(item, index) {
  const icon = ICONS[item.icon] || item.icon || ICONS['⚙️'];
  return `<article class="tool-card tool-card--action" style="--i:${index || 0}"
      onclick="${item.onClick}" title="${escapeAttr(item.desc || item.title)}">
    <div class="tool-card-top">
      <span class="tool-card-icon">${icon}</span>
      <span class="tool-card-cat tone-slate">快捷</span>
    </div>
    <div class="tool-card-label">${escapeHtml(item.title)}</div>
    <p class="tool-card-desc">${escapeHtml(item.desc || '')}</p>
    <div class="tool-card-foot">
      <span class="tool-card-state action"><i class="state-dot"></i>${escapeHtml(item.hint || '打开')}</span>
      <span class="tool-card-go">前往<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,3 11,8 6,13"/></svg></span>
    </div>
  </article>`;
}

function renderToolCards(names) {
  return (names || [])
    .map((n, i) => { const t = getTool(n); return t ? renderToolCard(t, i) : ''; })
    .filter(Boolean)
    .join('');
}

// ═══════════ Two-level Views (阶梯式导航) ═══════════

const VIEWS = {
  bom: {
    title: 'BOM 分析',
    subtitle: '物料清单的导入、校验、合并与供应链健康检查 — 确保每一颗元件可用、对、省。',
    metrics: [
      { num: '24', label: '系统能力', icon: '🧩' },
      { num: '71', label: '设计规则' },
      { num: '3', label: '自研 ML 模型' },
      { num: '98%', label: '缺陷检出率' },
    ],
    actions: [
      { label: '一键演示', sub: '加载示例缺陷 MCU 板', primary: true, onClick: 'startDemo()' },
      { label: '导入 BOM 文件', sub: 'CSV / Excel', primary: false, onClick: "document.getElementById('bomFileInput').click()" },
    ],
    tools: ['merge_bom', 'ai_merge_bom', 'validate_package', 'check_duplicates', 'filter_components', 'bom_health'],
  },
  review: {
    title: '设计审查',
    subtitle: '71 条 PCB 设计规则全量扫描 · 多智能体协同评审 · 违规密度可视化定位。',
    metrics: [
      { num: '71', label: 'DRC 规则', icon: '📐' },
      { num: '5', label: '审查 Agent', icon: '👥' },
      { num: '18s', label: '平均耗时', icon: '👁️' },
      { num: 'V2.8', label: '模型版本', icon: '⚙️' },
    ],
    actions: [
      { label: '启动多智能体审查', sub: '5 个专业 Agent 并行评审', primary: true, onClick: "featureCmd('__review')" },
      { label: '加载 DRC 热力图', sub: '违规密度可视化', primary: false, onClick: "featureCmd('__heatmap')" },
    ],
    tools: ['check_rule', 'pcb_analysis', 'review_multi_agent', 'verify_suggestion', 'pcb_status', 'explain_design_rule'],
    extras: [
      { icon: '🔥', title: 'DRC 热力图', desc: '违规密度的空间分布定位', onClick: "featureCmd('__heatmap')", hint: '右侧面板' },
      { icon: '📥', title: '导入 PCB', desc: '.json / .epro 电路板文件', onClick: "document.getElementById('pcbFileInput').click()", hint: '选择文件' },
    ],
  },
  tools: {
    hub: true,
    title: '工具箱',
    subtitle: '全部系统能力集中于此 — 搜索、按类别筛选、一键运行。目录由后端 ToolRegistry 派生，与实际可执行能力永远一致。',
  },
  report: {
    title: '报告中心',
    subtitle: '生成交互式 HTML BOM · 查看历史报告栈 · 导出审查结果。',
    metrics: [
      { num: 'HTML', label: '报告格式', icon: '📑' },
      { num: 'CSV', label: '数据导出', icon: '📤' },
      { num: '历史', label: '报告栈', icon: '📚' },
      { num: '一键', label: '生成', icon: '✅' },
    ],
    actions: [
      { label: '生成 HTML BOM', sub: '交互式物料表', primary: true, onClick: "generateHTMLBOM()" },
      { label: '打开任务面板', sub: '查看报告与审查结果', primary: false, onClick: "toggleRightPanel()" },
    ],
    tools: ['generate_html_bom', 'export_bom_csv', 'summary_report', 'bom_cost_summary'],
    extras: [
      { icon: '📑', title: '报告栈', desc: '操作历史报告归档', onClick: "switchTab('report'); toggleRightPanel()", hint: '右侧面板' },
      { icon: '📊', title: '审查结果', desc: '多智能体评审卡片', onClick: "switchTab('review'); toggleRightPanel()", hint: '右侧面板' },
      { icon: '🧾', title: 'BOM 表格', desc: '当前物料明细', onClick: "switchTab('bom'); toggleRightPanel()", hint: '右侧面板' },
      { icon: '👁️', title: 'HTML 预览', desc: '生成的 BOM 预览', onClick: "switchTab('html'); toggleRightPanel()", hint: '右侧面板' },
    ],
  },
  config: {
    title: '配置管理',
    subtitle: 'AI 模型 · 外观主题 · 通用设置 · 助手实例管理 — 一切可调项集中于此。',
    metrics: [
      { num: '5+', label: 'LLM 服务商', icon: '🤖' },
      { num: '4', label: '助手类型', icon: '🧠' },
      { num: '本地', label: 'ML 离线', icon: '📦' },
      { num: 'SQLite', label: '持久化', icon: '💾' },
    ],
    actions: [
      { label: 'AI 模型配置', sub: 'API Key · 模型 · 温度', primary: true, onClick: "openSettingsAt('s-ai')" },
      { label: '新建助手', sub: '多实例助手模型', primary: false, onClick: "showNewAssistantDialog()" },
    ],
    extras: [
      { icon: '🤖', title: 'AI 模型', desc: '服务商 · API Key · 模型 · 温度', onClick: "openSettingsAt('s-ai')", hint: '设置' },
      { icon: '🎨', title: '外观主题', desc: '深浅色 · 强调色 · 字号', onClick: "openSettingsAt('s-appearance')", hint: '设置' },
      { icon: '⚙️', title: '通用设置', desc: '自动保存 · 文件监听 · 操作确认', onClick: "openSettingsAt('s-general')", hint: '设置' },
      { icon: '💾', title: '数据存储', desc: '数据目录与清除本地数据', onClick: "openSettingsAt('s-general')", hint: '设置' },
      { icon: '📁', title: '导入 PCB', desc: '.json / .epro 电路板文件', onClick: "document.getElementById('pcbFileInput').click()", hint: '选择文件' },
      { icon: '📍', title: '导入坐标', desc: '.csv 元件坐标文件', onClick: "document.getElementById('posFileInput').click()", hint: '选择文件' },
    ],
    assistantSection: true,
  },
};

// ═══════════ SVG 图标映射（Lucide 风格线性图标，替换 emoji） ═══════════
const ICONS = {
  '🩺':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12h3l3-8 4 16 3-8h6"/></svg>',
  '📐':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h12L4 16z"/></svg>',
  '🔍':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/></svg>',
  '🔗':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 15l6-6M10 6l1.5-1.5a3.5 3.5 0 0 1 5 5L15 11M14 18l-1.5 1.5a3.5 3.5 0 0 1-5-5L9 13"/></svg>',
  '🤖':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V5M9 5h6"/><path d="M9 13v1M15 13v1"/></svg>',
  '📋':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4a3 3 0 0 1 6 0"/><path d="M9 11h6M9 15h6"/></svg>',
  '🛤️':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19a2 2 0 1 0 0-8h8a2 2 0 1 1 0 8M4 11V7a2 2 0 0 1 2-2h2"/></svg>',
  '🖥️':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
  '🔥':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2c2 4-1 5 0 8a2.5 2.5 0 0 0 5 0c0-3-2-4-2-4 3 2 5 6 4 9a6 6 0 1 1-12 0c0-5 3-7 5-13"/></svg>',
  '👥':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="8" r="3.5"/><path d="M3 19a6 6 0 0 1 12 0M16 5a3.5 3.5 0 0 1 0 6M14 13a5.5 5.5 0 0 1 6 6"/></svg>',
  '✅':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>',
  '🌐':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18"/></svg>',
  '📑':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>',
  '📊':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 20h16M7 20V11M12 20V6M17 20v-5"/></svg>',
  '🗺️':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 6l8-3 5 3-6 3-7-3zM8 6v12m8-12v12M8 18l-5 3V9l5-3m8 12l5-3"/></svg>',
  '🧾':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 3h14v18l-2.3-1.6L14.4 21l-2.4-1.6L9.6 21l-2.3-1.7L5 21z"/><path d="M9 8h6M9 12h6"/></svg>',
  '👁️':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/></svg>',
  '🎨':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22a10 10 0 1 1 10-10c0 2.5-1.8 3-4 3.5a2.5 2.5 0 0 0-2.5 2.5c0 2 1.2 2.5 1.2 4"/><path d="M7 10.5h.01M11 7h.01M15 8.5h.01"/></svg>',
  '⚙️':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
  '💾':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
  '🧠':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 5V2M12 5V2M15 5V2M9 22v-3M12 22v-3M15 22v-3M5 9H2M5 12H2M5 15H2M22 9h-3M22 12h-3M22 15h-3"/></svg>',
  '📁':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  // ── 工具目录补充图标 ──
  '📦':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/></svg>',
  '🧩':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 3h4v4a2 2 0 1 0 4 0h3v4h-3a2 2 0 1 0 0 4h3v4h-4a2 2 0 1 0-4 0H9v-4a2 2 0 1 0-4 0H2v-4h3a2 2 0 1 0 0-4H2V5h4a2 2 0 0 1 4-2z"/></svg>',
  '🧲':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3v8a6 6 0 0 0 12 0V3"/><path d="M6 8h4M14 8h4"/></svg>',
  '📤':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="M12 15V3M8 7l4-4 4 4"/></svg>',
  '💰':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 4h12M6 9h12M12 4v16M8 13c4 0 8 1 8 4"/></svg>',
  '🔁':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 10a6 6 0 0 1 10-4l3 3M20 14a6 6 0 0 1-10 4l-3-3"/><path d="M17 3v6h-6M7 21v-6h6"/></svg>',
  '🚚':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="6" width="12" height="10" rx="1"/><path d="M14 9h4l3 3v4h-7z"/><circle cx="6" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/></svg>',
  '📏':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 15L15 3l6 6L9 21z"/><path d="M7 11l2 2M10 8l2 2M13 5l2 2"/></svg>',
  '📖':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h6a3 3 0 0 1 3 3v13a2.5 2.5 0 0 0-2.5-2.5H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a2.5 2.5 0 0 1 2.5-2.5H20z"/></svg>',
  '🔎':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21M8 11h6"/></svg>',
  '🖼️':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="M4 18l5-5 3 3 3-4 5 6"/></svg>',
  '📚':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 5a2 2 0 0 1 2-2h5v18H6a2 2 0 0 0-2 2z"/><path d="M20 5a2 2 0 0 0-2-2h-5v18h5a2 2 0 0 1 2 2z"/></svg>',
  '📥':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="M12 3v12M8 11l4 4 4-4"/></svg>',
  '📍':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s7-7 7-12a7 7 0 1 0-14 0c0 5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  '🔧':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14.7 6.3a4 4 0 0 1 5 5L11 20H4v-7z"/><path d="M12 9l3 3"/></svg>',
};
// KPI 指标图标（按 label 关键词匹配）
function _metricIcon(label) {
  if (/规则/.test(label)) return '📐';
  if (/ML/.test(label)) return '🧠';
  if (/检出/.test(label)) return '✅';
  if (/Agent/.test(label)) return '👥';
  if (/耗时/.test(label)) return '👁️';
  if (/版本/.test(label)) return '⚙️';
  if (/格式/.test(label)) return '📑';
  return '📊';
}

let _currentView = 'bom';

async function switchView(viewId) {
  _currentView = viewId;
  const view = VIEWS[viewId];
  if (!view) return;
  // 视图里要用工具目录渲染统一卡片 → 首次进入前先拉目录
  if (!TOOL_CATALOG.length) await loadToolCatalog();
  if (_currentView !== viewId) return;   // 期间用户又切了视图
  // Top nav active state
  document.querySelectorAll('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.view === viewId);
  });
  // Hide chat messages, show view
  document.getElementById('chatMessages').classList.add('hidden');
  const vc = document.getElementById('viewContainer');
  vc.classList.remove('hidden');
  vc.innerHTML = renderViewHTML(view);
  vc.scrollTop = 0;
  if (view.hub) renderToolGrid();
  // Re-render assistants list if entering config view
  if (viewId === 'config') {
    setTimeout(() => { renderAssistants(); }, 0);
  }
}

function renderMetrics(metrics) {
  return (metrics || []).map(m =>
    `<div class="kpi-card">
       <div class="kpi-icon">${ICONS[m.icon || _metricIcon(m.label)] || ''}</div>
       <div class="kpi-body">
         <div class="kpi-num">${m.num}</div>
         <div class="kpi-label">${m.label}</div>
       </div>
     </div>`
  ).join('');
}

function renderViewHTML(view) {
  const actions = (view.actions || []).map(a =>
    `<button class="${a.primary ? 'btn-primary' : 'btn-secondary'}" onclick="${a.onClick}">
       <span class="view-action-label">${a.label}</span>
       <span class="view-action-sub">${a.sub || ''}</span>
     </button>`
  ).join('');

  const grid = view.hub
    ? renderToolHub()
    : `<div class="tool-grid">${renderToolCards(view.tools)}${(view.extras || []).map(renderActionCard).join('')}</div>`;

  // Config view gets an extra inline assistants section
  const assistantSection = view.assistantSection ? `
    <div class="config-section">
      <div class="config-section-head">
        <span class="config-section-icon">${ICONS['🧠']}</span>
        <span class="config-section-title">助手实例</span>
        <span class="config-section-count" id="configAssistantCount"></span>
      </div>
      <div id="configAssistantList" class="assistant-list-inline"></div>
      <div class="config-section-foot"><button class="btn-secondary" onclick="showNewAssistantDialog()">+ 新建助手</button></div>
    </div>` : '';

  return `
    <div class="view-header">
      <h1 class="view-title">${view.title}</h1>
      <p class="view-subtitle">${view.subtitle}</p>
    </div>
    ${view.metrics ? `<div class="kpi-row">${renderMetrics(view.metrics)}</div>` : ''}
    ${actions ? `<div class="view-actions">${actions}</div>` : ''}
    ${grid}
    ${assistantSection}
  `;
}

// ── 工具箱（统一管理界面） ──

function renderToolHub() {
  const total = TOOL_CATALOG.length;
  const ready = TOOL_CATALOG.filter(t => t.ready).length;
  const catIds = Object.keys(TOOL_CATEGORIES).filter(c => TOOL_CATALOG.some(t => t.category === c));
  const metrics = [
    { num: String(total), label: '系统能力', icon: '🧩' },
    { num: String(catIds.length), label: '能力分类', icon: '📦' },
    { num: String(ready), label: '当前可直接运行', icon: '✅' },
    { num: String(total - ready), label: '需先导入数据', icon: '📥' },
  ];
  const chips = ['all'].concat(catIds).map(c => {
    const n = c === 'all' ? total : TOOL_CATALOG.filter(t => t.category === c).length;
    const label = c === 'all' ? '全部' : (TOOL_CATEGORIES[c] || {}).label || c;
    const icon = c === 'all' ? ICONS['🧩'] : (ICONS[TOOL_ICONS[(TOOL_CATALOG.find(t => t.category === c) || {}).name]] || '');
    return `<button class="hub-chip ${c === _toolCategory ? 'active' : ''}" data-cat="${c}" onclick="setToolCategory('${c}')">
      <span class="hub-chip-icon">${icon}</span>${label}<span class="hub-chip-num">${n}</span>
    </button>`;
  }).join('');

  return `
    <div class="kpi-row">${renderMetrics(metrics)}</div>
    <div class="tool-hub-bar">
      <div class="tool-search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/></svg>
        <input id="toolSearchInput" type="text" placeholder="搜索能力名称或说明，如 合并 / DRC / 知识库 / 替代料" value="${escapeAttr(_toolQuery)}" oninput="setToolQuery(this.value)">
        <button class="tool-search-clear" onclick="clearToolQuery()" title="清空">✕</button>
      </div>
      <label class="tool-ready-toggle">
        <input type="checkbox" ${_toolOnlyReady ? 'checked' : ''} onchange="setToolOnlyReady(this.checked)">
        <span class="tool-ready-track"></span>
        <span class="tool-ready-text">仅显示可运行</span>
      </label>
    </div>
    <div class="hub-chips">${chips}</div>
    <div class="tool-grid" id="toolGrid"></div>
    <div class="tool-empty" id="toolEmpty" style="display:none">
      <div class="tool-empty-icon">${ICONS['🔎']}</div>
      <div class="tool-empty-title">没有匹配的能力</div>
      <div class="tool-empty-desc">换个关键词，或切换到「全部」分类</div>
    </div>
  `;
}

function setToolQuery(q) {
  _toolQuery = q || '';
  renderToolGrid();
}

function clearToolQuery() {
  _toolQuery = '';
  const input = document.getElementById('toolSearchInput');
  if (input) { input.value = ''; input.focus(); }
  renderToolGrid();
}

function setToolCategory(cat) {
  _toolCategory = cat;
  document.querySelectorAll('.hub-chip').forEach(c => c.classList.toggle('active', c.dataset.cat === cat));
  renderToolGrid();
}

function setToolOnlyReady(on) {
  _toolOnlyReady = !!on;
  renderToolGrid();
}

function renderToolGrid() {
  const grid = document.getElementById('toolGrid');
  if (!grid) return;
  const q = _toolQuery.trim().toLowerCase();
  const list = TOOL_CATALOG.filter(t => {
    if (_toolCategory !== 'all' && t.category !== _toolCategory) return false;
    if (_toolOnlyReady && !t.ready) return false;
    if (!q) return true;
    const hay = [t.label, t.description, t.name].concat(t.keywords || []).join(' ').toLowerCase();
    return hay.includes(q);
  });
  grid.innerHTML = list.map(renderToolCard).join('');
  const empty = document.getElementById('toolEmpty');
  if (empty) empty.style.display = list.length ? 'none' : '';
}

// ── 工具启动 ──

/** 切到聊天流：隐藏视图容器，显示消息流 */
function _enterChatStream() {
  const vc = document.getElementById('viewContainer');
  const cm = document.getElementById('chatMessages');
  if (vc) vc.classList.add('hidden');
  if (cm) cm.classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
}

async function launchTool(toolName) {
  const t = getTool(toolName);
  if (!t) {
    // 目录未加载（例如离线打开）→ 退回自然语言指令
    quickCmd(toolName);
    return;
  }
  const spec = TOOL_LAUNCH[t.name];
  if (spec && spec.kind === 'run') { spec.run(); return; }
  if (!t.ready) {
    showToast(`「${t.label}」${t.blocked_reason || '暂不可用'}`, 'warning');
    return;
  }
  if (spec && spec.kind === 'image') { triggerImagePick(); return; }
  if (t.needs_input) { prefillToolInput(t); return; }
  await runToolInline(t);
}

function prefillToolInput(t) {
  const spec = TOOL_LAUNCH[t.name];
  const prefix = (spec && spec.prefix) || t.prompt_prefix || (t.label + ' ');
  _enterChatStream();
  const input = document.getElementById('chatInput');
  input.value = prefix;
  input.focus();
  input.setSelectionRange(prefix.length, prefix.length);
  const hint = (t.params || []).map(p => p.hint || p.name).filter(Boolean).join(' / ');
  showToast(`「${t.label}」需要参数：${hint || '请补充输入'}`, 'info');
}

async function runToolInline(t) {
  _enterChatStream();
  const conv = getActiveConversation();
  const prompt = `▶ 运行工具：${t.label}`;
  appendBubble('user', prompt);
  if (conv) {
    conv.messages.push({ role: 'user', content: prompt });
    _persistMessage(activeConvId, 'user', prompt);
  }
  disableInput(true);
  const stream = createStreamingBubble();
  document.getElementById('chatMessages').appendChild(stream.element);
  stream.setStatus(`正在执行 ${t.label} …`);
  scrollChat();

  let resp;
  try { resp = await eel.run_tool(t.name)(); }
  catch (e) { resp = { ok: false, error: String(e) }; }
  disableInput(false);

  const ok = resp && resp.ok;
  const text = ok ? (resp.result || '（该能力没有返回文本输出）') : `❌ ${(resp && resp.error) || '执行失败'}`;
  stream.finalize(text);
  if (conv) {
    conv.messages.push({ role: 'ai', content: text });
    _persistMessage(activeConvId, 'ai', text);
  }
  if (ok && resp.result) showReport(resp.result);
  renderConversations();
  refreshToolCatalog();
}

/** 打开设置弹窗并直达指定分页 */
function openSettingsAt(tabId) {
  const overlay = document.getElementById('settingsOverlay');
  if (!overlay) return;
  if (!SETTINGS_LOADED) { SETTINGS_LOADED = true; loadSettingsIntoUI(); }
  if (tabId) switchSettingsTab(tabId);
  overlay.classList.add('show');
}

function switchConfigAssistants() {
  switchView('config').then(() => {
    const el = document.getElementById('configAssistantList');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}

function showEmptyState(show) {
  const el = document.getElementById('chatEmpty');
  if (!el) return;
  el.style.display = show ? '' : 'none';
}

/** One-click demo: load sample defective MCU board, then run rule check */
async function startDemo() {
  // Switch to chat-stream mode: hide view container, show chat messages
  _enterChatStream();

  // ⚠️ 先把会话准备好：否则首条消息发送时 getActiveConversation() →
  //    newConversation() → clearChatMessages() 会把刚展示的演示结果清空
  //    （2026-09-10 实测：用户视角就是「刚看到的结论消失了」）。
  const conv = getActiveConversation();
  const _record = (role, content) => {
    if (!conv) return;
    conv.messages.push({ role, content });
    _persistMessage(activeConvId, role, content);
  };
  if (conv && conv.messages.length === 0) {
    conv.title = '示例 MCU 板审查';
    _persistConversation(conv);
  }

  appendSystem(' 加载示例数据: 有缺陷的 MCU 板 BOM + 坐标');
  setStatus('加载演示数据...');
  disableInput(true);
  let resp;
  try { resp = await eel.load_demo_data()(); } catch(e) {
    appendTip(' 加载失败: ' + e, 'error'); setStatus('就绪'); disableInput(false); return;
  }
  if (resp && resp.ok) {
    const okText = ` 已加载示例 BOM: **${resp.count}** 个元件${resp.pos_count ? ` · ${resp.pos_count} 个坐标` : ''}\n\n点击顶栏面板按钮查看 BOM 表格。可继续:\n- 输入「设计规则」运行 71 条 DRC 扫描\n- 进入「设计审查」启动多智能体评审\n- 输入「BOM健康」检查库存与替代料`;
    appendBubble('ai', okText);
    _record('ai', okText);
    if (resp.items && resp.items.length) renderBOMTable(resp.items);
    // 自动跑一次规则检查，让面板有内容
    try {
      const r = await eel.check_rules()();
      if (r && r.ok) showReport(r.report);
    } catch(e) {}
  } else {
    appendTip(' 加载失败: ' + (resp ? resp.msg : '未知错误'), 'error');
  }
  setStatus('就绪');
  disableInput(false);
  renderConversations();
  // 演示数据也是一次「BOM 到位」，工具可用性跟着变
  if (resp && resp.ok) await refreshToolCatalog();
}

/** Feature card click dispatcher */
function featureCmd(key) {
  if (key === '__review') {
    openRightPanel();
    switchTab('review');
    runMultiAgentReview();
    return;
  }
  if (key === '__heatmap') {
    openRightPanel();
    switchTab('review');
    loadDrcHeatmap();
    return;
  }
  quickCmd(key);
}

function triggerImagePick() {
  document.getElementById('imageFileInput').click();
}

function askKnowledge() {
  const input = document.getElementById('chatInput');
  input.value = '查询知识库: ';
  input.focus();
  // place cursor after prefix
  const len = input.value.length;
  input.setSelectionRange(len, len);
}

function quickCmd(text) {
  if (text === '生成 HTML') { generateHTMLBOM(); return; }
  if (text === '查询知识库') {
    document.getElementById('chatInput').value = '查询知识库: ';
    document.getElementById('chatInput').focus();
    return;
  }
  // View-level shortcuts → map to natural-language commands
  const alias = {
    '__summary': 'BOM摘要',
    '__verify': '验证建议',
  };
  const cmd = alias[text] || text;
  document.getElementById('chatInput').value = cmd;
  sendChat();
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text && !currentImage) return;
  if (text === '生成 HTML' || text === '生成HTML') { removeImage(); input.value = ''; generateHTMLBOM(); return; }

  // Switch to chat-stream mode (hide view container, show messages)
  _enterChatStream();

  const hasImage = !!currentImage;
  const userText = text || '帮我分析这张图片';
  input.value = '';
  input.style.height = 'auto';

  // RAG 知识库查询路由 — 无图片且以「查询知识库:」开头时直接查询
  const isKnowledgeQuery = !hasImage && !agentMode && /^查询知识库[：:]\s*(.+)/.test(userText);
  if (isKnowledgeQuery) {
    const queryText = userText.replace(/^查询知识库[：:]\s*/, '').trim();
    if (!queryText) {
      appendBubble('ai', '📚 请输入要查询的内容，如「查询知识库: IPC-2221载流能力」');
      return;
    }
    showEmptyState(false);
    const conv = getActiveConversation();
    if (!conv) return;

    // Update title from first message
    if (conv.messages.length === 0) {
      conv.title = '知识库: ' + queryText.substring(0, 20) + (queryText.length > 20 ? '...' : '');
      _persistConversation(conv);
      renderConversations();
    }

    appendBubble('user', userText);
    conv.messages.push({ role: 'user', content: userText });
    _persistMessage(activeConvId, 'user', userText);

    setStatus('查询知识库...');
    disableInput(true);
    _streamTokenCount = 0;
    _activeStreamBubble = createStreamingBubble();
    document.getElementById('chatMessages').appendChild(_activeStreamBubble.element);
    scrollChat();

    try {
      const resp = await eel.query_knowledge_base(queryText)();
      if (resp && resp.ok) {
        _activeStreamBubble.finalize(resp.result);
        conv.messages.push({ role: 'ai', content: resp.result });
        _persistMessage(activeConvId, 'ai', resp.result);
      } else {
        _activeStreamBubble.finalize('❌ 查询失败: ' + (resp ? resp.result : '未知错误'));
        conv.messages.push({ role: 'ai', content: _activeStreamBubble.text });
        _persistMessage(activeConvId, 'ai', _activeStreamBubble.text);
      }
    } catch(e) {
      if (_activeStreamBubble) {
        _activeStreamBubble.finalize('❌ 网络错误: ' + e);
        conv.messages.push({ role: 'ai', content: _activeStreamBubble.text });
        _persistMessage(activeConvId, 'ai', _activeStreamBubble.text);
      }
    }
    _activeStreamBubble = null;
    disableInput(false);
    setStatus('就绪');
    renderConversations();
    return;
  }

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
      _activeToolCards.forEach(c => c.remove());
      _activeToolCards = [];
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
  // Clear leftover tool-call cards from a previous turn
  _activeToolCards.forEach(c => c.remove());
  _activeToolCards = [];
  // ⚠️ element 必须是 .msg-row 外壳（不是裸 .bubble）：
  //    否则 AI 气泡既不被 clearChatMessages() 清理，也不被 _syncChatEmpty()
  //    计入，切换会话后会出现重复回答 + 空态不消失（2026-09-10 修正）。
  const row = document.createElement('div');
  row.className = 'msg-row ai';
  const bubble = document.createElement('div');
  bubble.className = 'bubble bubble-ai streaming';
  row.appendChild(bubble);
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
    element: row,
    bubble: bubble,
    updateToken(token) {
      buffer += token;
      tokenCount++;
      if (tokenCount % RERENDER_EVERY === 0) {
        rerender();
      }
    },
    /** 运行中的状态文案（不走 Markdown，立即渲染） */
    setStatus(text) {
      bubble.innerHTML = `<span class="stream-status">${escapeHtml(text)}</span>`;
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
    // 数据到位 → 工具箱里「需先导入 BOM」的徽标要立刻变成可用
    await refreshToolCatalog();
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
  // Show heatmap section when review tab is active
  var hs = document.getElementById('drcHeatmapSection');
  if (hs) hs.style.display = (name === 'review') ? 'block' : 'none';
}

function toggleRightPanel() {
  const panel = document.getElementById('rightPanel');
  if (!panel) return;
  const collapsed = panel.classList.toggle('collapsed');
  _syncPanelToggle(collapsed);
}

/** 确保右面板展开（工具/快捷入口跳转时用） */
function openRightPanel() {
  const panel = document.getElementById('rightPanel');
  if (!panel || !panel.classList.contains('collapsed')) return;
  panel.classList.remove('collapsed');
  _syncPanelToggle(false);
}

function _syncPanelToggle(collapsed) {
  // 折叠按钮只剩顶栏一个（旧的悬浮圆钮会压住入口卡片，已移除）
  const btn = document.getElementById('panelToggleTop');
  if (btn) {
    btn.classList.toggle('active', !collapsed);
    btn.title = collapsed ? '展开任务面板' : '折叠任务面板';
  }
  const panel = document.getElementById('rightPanel');
  if (panel) panel.setAttribute('aria-expanded', String(!collapsed));
}

// ═══════════ Theme & Accent ═══════════

var _currentAccent = '#2565fe';

function applyTheme(name) {
  var theme = (name === 'dark') ? 'dark' : 'light';
  document.body.setAttribute('data-theme', theme);
  try { eel.save_theme(theme)(); } catch(e) {}
  // update theme radio buttons
  document.querySelectorAll('.theme-card input').forEach(function(r) {
    r.checked = r.value === theme;
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

// 厂商 + 模型目录 — 来自后端 LLM_PROVIDER_PRESETS（SSOT），前端不再手写。
// 过去这里有一份 10 家的硬编码副本，2026-09 核对时发现已经积了一堆
// 不存在 / 官方已退役 / 已被换代的型号（测试里用
// test_no_hardcoded_retired_model_ids 钉住了这些名字，别再抄回来）。
// 现在：后端下发兜底清单 + 「拉取最新模型」直接问厂商 GET /models。
var PROVIDERS = {};          // key → {key, brand, icon, base_url, default_model, models, ...}
var _providersLoaded = false;
var _liveModels = {};        // providerKey → ['实时拉到的模型']

async function loadProviders(force) {
  if (_providersLoaded && !force) return PROVIDERS;
  try {
    var resp = await eel.get_providers()();
    if (resp && resp.ok && resp.providers) {
      PROVIDERS = {};
      resp.providers.forEach(function(p) { PROVIDERS[p.key] = p; });
      if (!_selectedProvider) _selectedProvider = resp.default_provider || 'deepseek';
    }
  } catch (e) {
    console.warn('厂商目录加载失败', e);
  }
  _providersLoaded = true;
  return PROVIDERS;
}

/** 当前厂商可选项：优先实时拉取结果，其次后端兜底清单 */
function providerModels(key) {
  if (_liveModels[key] && _liveModels[key].length) return _liveModels[key];
  var p = PROVIDERS[key];
  return (p && p.models) ? p.models.slice() : [];
}

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
  loadProviders().then(renderProviderCards);
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
    card.innerHTML = '<div class="provider-card-icon provider-icon-text">' + escapeHtml(p.icon) + '</div>' +
      '<div class="provider-card-name">' + escapeHtml(p.brand || p.name) + '</div>' +
      '<div class="provider-card-model" title="' + escapeAttr(p.description || '') + '">' +
        escapeHtml(p.description || '') + '</div>';
    card.setAttribute('data-provider', key);
    card.addEventListener('click', function() { selectProvider(key, card); });
    container.appendChild(card);
  });
}

function selectProvider(key, card) {
  _selectedProvider = key;
  document.querySelectorAll('.provider-card').forEach(function(c) { c.classList.remove('selected'); });
  if (card) card.classList.add('selected');
  var p = PROVIDERS[key] || {};
  document.getElementById('setBaseUrl').placeholder = p.base_url || '';
  var link = document.getElementById('providerKeyLink');
  if (link) {
    if (p.key_url) { link.href = p.key_url; link.style.display = ''; }
    else { link.style.display = 'none'; }
  }
  var note = document.getElementById('providerNote');
  if (note) {
    note.textContent = p.notes || '';
    note.style.display = p.notes ? '' : 'none';
  }
  fillModelOptions(key, p.default_model);
}

/** 填充模型下拉：优先用实时拉取结果，否则后端兜底清单 */
function fillModelOptions(key, preferred) {
  var sel = document.getElementById('setModelSelect');
  if (!sel) return;
  var models = providerModels(key);
  sel.innerHTML = '';
  models.forEach(function(m) {
    var opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    if (m === preferred) opt.selected = true;
    sel.appendChild(opt);
  });
  var custom = document.createElement('option');
  custom.value = '__custom__'; custom.textContent = '自定义模型...';
  sel.appendChild(custom);
  document.getElementById('setModelCustom').style.display = 'none';
  _syncModelSourceBadge(key);
}

function _syncModelSourceBadge(key) {
  var badge = document.getElementById('modelSourceBadge');
  if (!badge) return;
  var live = _liveModels[key];
  if (live && live.length) {
    badge.textContent = '实时 · ' + live.length + ' 个';
    badge.className = 'model-source-badge live';
    badge.title = '模型列表来自厂商 GET /models 接口';
  } else {
    badge.textContent = '离线兜底';
    badge.className = 'model-source-badge';
    badge.title = '未实时拉取，显示的是内置兜底清单；点右侧按钮可获取厂商最新列表';
  }
}

/** 向厂商实时拉取模型列表（GET /models，只读免费） */
async function fetchModelsForProvider() {
  var btn = document.getElementById('fetchModelsBtn');
  var badge = document.getElementById('modelSourceBadge');
  var key = _selectedProvider;
  var apiKey = document.getElementById('setApiKey').value;
  var baseUrl = document.getElementById('setBaseUrl').value;
  if (btn) { btn.disabled = true; btn.textContent = '拉取中…'; }
  if (badge) { badge.textContent = '拉取中…'; badge.className = 'model-source-badge loading'; }
  try {
    var resp = await eel.fetch_provider_models(key, apiKey, baseUrl)();
    if (resp && resp.ok && resp.models && resp.models.length) {
      var live = resp.models;
      _liveModels[key] = live;
      var sel = document.getElementById('setModelSelect');
      var keep = sel ? sel.value : '';
      var prevCustom = (keep === '__custom__')
        ? document.getElementById('setModelCustom').value : '';
      var preferred = (keep && keep !== '__custom__' && live.indexOf(keep) >= 0)
        ? keep : (PROVIDERS[key] || {}).default_model;
      fillModelOptions(key, preferred);
      if (prevCustom) {
        // 用户自己填的模型名不能因为点了一下「拉取」就丢
        _useCustomModel(prevCustom);
      } else if (keep && keep !== '__custom__' && live.indexOf(keep) < 0) {
        // 原型号已从厂商列表消失 → 降级为自定义，不静默改掉用户配置
        _useCustomModel(keep);
      }
      showToast('已获取 ' + live.length + ' 个可用模型', 'success');
    } else {
      if (badge) { badge.textContent = '离线兜底'; badge.className = 'model-source-badge'; }
      showToast('拉取失败：' + ((resp && resp.error) || '未知错误'), 'error');
    }
  } catch (e) {
    if (badge) { badge.textContent = '离线兜底'; badge.className = 'model-source-badge'; }
    showToast('拉取失败：' + (e.message || e), 'error');
  }
  if (btn) { btn.disabled = false; btn.textContent = '拉取最新模型'; }
}

function onModelSelectChange() {
  var sel = document.getElementById('setModelSelect');
  document.getElementById('setModelCustom').style.display = sel.value === '__custom__' ? 'block' : 'none';
}

/** 切到「自定义模型」并填入指定型号 */
function _useCustomModel(name) {
  var sel = document.getElementById('setModelSelect');
  var custom = document.getElementById('setModelCustom');
  if (sel) sel.value = '__custom__';
  if (custom) { custom.value = name; custom.style.display = 'block'; }
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
  var baseUrl = document.getElementById('setBaseUrl').value || (PROVIDERS[provider] || {}).base_url || '';
  var modelSel = document.getElementById('setModelSelect');
  var model = modelSel.value === '__custom__' ? document.getElementById('setModelCustom').value : modelSel.value;
  if (!model) model = (PROVIDERS[provider] || {}).default_model || '';

  try {
    var resp = await eel.test_llm_connection(provider, apiKey, baseUrl, model)();
    if (resp.ok) {
      icon.textContent = ''; icon.className = '';
      text.textContent = '连接成功';
      result.textContent = (resp.latency ? '延迟 ' + resp.latency + 'ms' : '')
        + (resp.protocol === 'anthropic' ? ' · 原生 Messages API' : '');
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
    await loadProviders();           // 厂商目录来自后端，必须先拿到
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
  // 关闭条件：无参数调用（✕/取消/Esc 直接调 closeSettings()），
  // 或点击遮罩空白处，或点击关闭/取消控件本身。
  // ⚠️ 不要写成 `e.target === overlay`：按钮传进来的 target 是按钮自己，
  //    会导致 ✕ 和「取消」永远关不掉弹窗（2026-09-10 实测确认的 bug）。
  var overlay = document.getElementById('settingsOverlay');
  if (e && e.target && e.target !== overlay) {
    var inCloseControl = e.target.closest &&
      e.target.closest('.settings-close-btn, .settings-bottom-actions');
    if (!inCloseControl) return;
  }
  if (overlay) overlay.classList.remove('show');
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
  if (!model) model = (PROVIDERS[provider] || {}).default_model || '';
  var temperature = parseFloat(document.getElementById('setTemperature').value) || 0.7;
  var theme = document.body.getAttribute('data-theme') || 'light';
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

// Tool-call map: function name (from LLM Function Calling) → 中文标签
const TOOL_LABELS = {
  import_bom: '导入 BOM', merge_bom: '合并 BOM', ai_merge_bom: 'AI 合并 BOM',
  validate_packages: '校验封装', check_duplicates: '查重',
  check_rules: '设计规则检查', check_health: 'BOM 健康检查',
  generate_html_bom: '生成 HTML BOM', analyze_pcb: '分析 PCB',
  check_traces: '走线检查', query_knowledge_base: '查询知识库',
  review_design: '设计审查', verify_suggestion: '验证建议',
  get_bom_summary: 'BOM 摘要',
};

let _activeToolCards = [];

eel.expose(onToolCall, 'on_tool_call');
function onToolCall(toolName) {
  if (!_activeStreamBubble) return;
  const label = TOOL_LABELS[toolName] || toolName;
  // Create a card with spinner, inserted before the streaming bubble
  const card = document.createElement('div');
  card.className = 'tool-call-card';
  card.innerHTML = `<span class="tool-call-spinner"></span>
    <span class="tool-call-icon">🔧</span>
    <span class="tool-call-name">${label}</span>
    <span class="tool-call-status">执行中…</span>`;
  _activeStreamBubble.element.parentNode.insertBefore(card, _activeStreamBubble.element);
  _activeToolCards.push(card);
  // Mark previous card as done
  if (_activeToolCards.length > 1) {
    const prev = _activeToolCards[_activeToolCards.length - 2];
    prev.classList.add('done');
    prev.querySelector('.tool-call-spinner').replaceWith(makeDoneIcon());
    prev.querySelector('.tool-call-status').textContent = '已完成';
  }
  scrollChat();
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
  _activeToolCards.forEach(c => {
    if (!c.classList.contains('done')) {
      c.classList.add('done');
      const sp = c.querySelector('.tool-call-spinner');
      if (sp) sp.replaceWith(makeDoneIcon());
      const st = c.querySelector('.tool-call-status');
      if (st) st.textContent = '已完成';
    }
  });
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
  const ring = document.getElementById('scoreRing');
  if (ring && data.overall_score != null) {
    const c = 2 * Math.PI * 52;
    const s = Math.max(0, Math.min(data.overall_score, 100));
    ring.style.strokeDasharray = c;
    ring.style.strokeDashoffset = c * (1 - s / 100);
    ring.style.stroke = _gradeColor(data.overall_score);
  }
  const ce = document.getElementById('reviewConsensus');
  if (ce) ce.innerHTML = renderMarkdown(data.consensus);
  _renderAgentCards(data.agents);
  _renderRoadmap(data.improvement_roadmap);
}

function drawRadarChart(data) {
  var c = document.getElementById('radarChart');
  if (!c || !data || data.length < 3) return;
  var ctx = c.getContext('2d'), w = c.width, h = c.height, cx = w / 2, cy = h / 2;
  var n = data.length, maxR = Math.min(cx, cy) - 20;
  var rs = getComputedStyle(document.body);
  var accent = (rs.getPropertyValue('--accent') || '#2565fe').trim();
  var muted = (rs.getPropertyValue('--text-muted') || '#8b919c').trim();
  var grid = (rs.getPropertyValue('--border') || '#e4e7ec').trim();
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = grid; ctx.lineWidth = 0.5;
  // grid
  for (var lv = 1; lv <= 4; lv++) {
    var r = (maxR / 4) * lv; ctx.beginPath();
    for (var i = 0; i < n; i++) {
      var a = (Math.PI * 2 / n) * i - Math.PI / 2;
      var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath(); ctx.stroke();
  }
  // axes
  for (var i = 0; i < n; i++) {
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + maxR * Math.cos(a), cy + maxR * Math.sin(a));
    ctx.stroke();
  }
  // polygon
  ctx.beginPath();
  for (var i = 0; i < n; i++) {
    var d = data[i], r = (d.score / 100) * maxR;
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath(); ctx.fillStyle = 'rgba(91,141,239,0.12)'; ctx.fill();
  ctx.strokeStyle = accent; ctx.lineWidth = 1.5; ctx.stroke();
  // dots + labels
  ctx.font = '9px sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = muted;
  for (var i = 0; i < n; i++) {
    var d = data[i], r = (d.score / 100) * maxR;
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath(); ctx.arc(cx + r * Math.cos(a), cy + r * Math.sin(a), 3, 0, Math.PI * 2);
    ctx.fillStyle = accent; ctx.fill();
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
  if (score >= 70) return '#2565fe';
  if (score >= 55) return '#e67e22';
  return '#e74c3c';
}

// ═══════════ DRC Heatmap ═══════════

var drcHeatmapChart = null;

async function loadDrcHeatmap() {
  var section = document.getElementById('drcHeatmapSection');
  var chartDom = document.getElementById('drcHeatmapChart');
  var emptyHint = document.getElementById('drcHeatmapEmpty');
  if (!section || !chartDom) return;

  section.style.display = 'block';
  emptyHint.style.display = 'none';

  try {
    var raw = await eel.get_drc_heatmap()();
    var data = JSON.parse(raw);
    if (!data.ok || !data.data || !data.data.length) {
      chartDom.style.display = 'none';
      emptyHint.style.display = 'block';
      return;
    }
    chartDom.style.display = 'block';
    renderDrcHeatmap(chartDom, data.data);
  } catch (e) {
    console.error('Heatmap load failed:', e);
    emptyHint.style.display = 'block';
    chartDom.style.display = 'none';
  }
}

function renderDrcHeatmap(chartDom, gridData) {
  if (!window.echarts) {
    console.warn('ECharts not loaded');
    return;
  }
  if (drcHeatmapChart) drcHeatmapChart.dispose();

  drcHeatmapChart = echarts.init(chartDom, 'dark');
  var xs = gridData.map(function(d) { return d[0]; });
  var ys = gridData.map(function(d) { return d[1]; });
  var counts = gridData.map(function(d) { return d[2]; });
  var xMin = Math.min.apply(null, xs), xMax = Math.max.apply(null, xs);
  var yMin = Math.min.apply(null, ys), yMax = Math.max.apply(null, ys);
  var maxCount = Math.max.apply(null, counts);

  var xLabels = xs.map(function(v, i) {
    return i === 0 || xs.indexOf(v) === i ? '#' + v : '';
  });
  var yLabels = ys.map(function(v, i) {
    return i === 0 || ys.indexOf(v) === i ? '#' + v : '';
  });

  var option = {
    tooltip: {
      formatter: function(p) {
        return '网格 [' + p.value[0] + ', ' + p.value[1] + ']<br/>违规数: <b>' + p.value[2] + '</b>';
      }
    },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: Array.from(new Set(xs)).sort(function(a, b) { return a - b; }),
      name: 'X 网格',
      nameLocation: 'center',
      nameGap: 25,
      axisLabel: { fontSize: 9 }
    },
    yAxis: {
      type: 'category',
      data: Array.from(new Set(ys)).sort(function(a, b) { return a - b; }),
      name: 'Y 网格',
      nameLocation: 'center',
      nameGap: 45,
      axisLabel: { fontSize: 9 }
    },
    visualMap: {
      min: 0,
      max: maxCount,
      calculable: true,
      orient: 'vertical',
      right: 5,
      top: 'center',
      inRange: { color: ['#1a2a4a', '#4a90d9', '#e6a23c', '#e74c3c'] },
      text: ['高', '低'],
      textStyle: { color: '#aaa' }
    },
    series: [{
      type: 'heatmap',
      data: gridData,
      label: { show: true, fontSize: 9, color: '#ccc' },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(255,255,255,0.3)'
        }
      }
    }]
  };

  drcHeatmapChart.setOption(option);
  window.addEventListener('resize', function() { drcHeatmapChart && drcHeatmapChart.resize(); });
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
