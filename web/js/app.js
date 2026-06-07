/* ═══════════════════════════════════════════
   EDA AI 智能助手 — Cherry Studio Frontend
   ═══════════════════════════════════════════ */

// ═══════════ State ═══════════

const ASSISTANTS = {
  'eda-general': {
    id: 'eda-general', name: 'EDA 通用助手', icon: '(´｡• ᵕ •｡`)',
    systemPrompt: 'general',
    quickActions: ['合并 BOM', '校验封装', '设计规则', 'BOM健康'],
    description: 'BOM管理、设计规则检查、PCB分析的通用助手',
  },
  'bom-expert': {
    id: 'bom-expert', name: 'BOM 管理专家', icon: '( •̀ᴗ•́ )و',
    systemPrompt: 'bom',
    quickActions: ['合并 BOM', 'AI智能合并', '校验封装', '查重', 'BOM健康', '生成 HTML'],
    description: '专注于物料清单管理、合并、验证和供应链检查',
  },
  'pcb-reviewer': {
    id: 'pcb-reviewer', name: 'PCB 设计审查', icon: '(｡･ω･｡)',
    systemPrompt: 'pcb',
    quickActions: ['设计规则', '分析PCB', '检查走线', '查看PCB'],
    description: '专注于PCB布局分析、设计规则检查和信号完整性',
  },
  'vision-analyst': {
    id: 'vision-analyst', name: '视觉分析', icon: '(=^･^=)',
    systemPrompt: 'vision',
    quickActions: ['分析图片'],
    description: '上传PCB截图或原理图进行AI视觉分析',
  },
};

let currentAssistant = 'eda-general';
let conversations = {};      // { assistantId: [{ id, title, messages: [] }] }
let activeConvId = null;     // currently selected conversation id
let currentImage = null;
let convCounter = 0;
let _activeStreamBubble = null;  // streaming bubble controller
let _streamTokenCount = 0;

// Initialize conversations for each assistant
Object.keys(ASSISTANTS).forEach(aid => { conversations[aid] = []; });

// ── Marked.js configuration ──
// Safe defaults: no raw HTML passthrough, GFM tables & task lists enabled
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true,        // single \n → <br>
    gfm: true,           // tables, task lists, strikethrough
    headerIds: false,    // no id attributes on headings
    mangle: false,       // no email obfuscation
  });
}

// ═══════════ Init ═══════════

document.addEventListener('DOMContentLoaded', async () => {
  renderAssistants();
  renderConversations();
  selectAssistant('eda-general');

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
  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
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

// ═══════════ Assistant Management ═══════════

function renderAssistants() {
  const container = document.getElementById('assistantList');
  container.innerHTML = Object.values(ASSISTANTS).map(a => `
    <div class="sb-item ${a.id === currentAssistant ? 'active' : ''}"
         onclick="selectAssistant('${a.id}')" title="${a.description}">
      <span class="sb-item-icon">${a.icon}</span>
      <span class="sb-item-name">${a.name}</span>
    </div>
  `).join('');
}

function selectAssistant(id) {
  currentAssistant = id;
  renderAssistants();
  renderConversations();
  updateChatHeader();

  // Auto-select first conversation or show empty state
  const convs = conversations[id] || [];
  if (convs.length > 0) {
    switchConversation(convs[0].id);
  } else {
    activeConvId = null;
    showEmptyState(true);
    document.getElementById('chatMessages').querySelectorAll('.msg-row').forEach(el => el.remove());
  }

  // Update quick actions
  renderQuickActions();
}

function updateChatHeader() {
  const a = ASSISTANTS[currentAssistant];
  document.getElementById('assistantIcon').textContent = a.icon;
  document.getElementById('assistantName').textContent = a.name;
}

function switchAssistant(id) {
  selectAssistant(id);
}

function renderQuickActions() {
  const a = ASSISTANTS[currentAssistant];
  const container = document.getElementById('quickActions');
  container.innerHTML = (a.quickActions || []).map(cmd =>
    `<button class="qa-btn" onclick="quickCmd('${cmd}')">${cmd}</button>`
  ).join('');
}

// ═══════════ Conversation Management ═══════════

function newConversation() {
  const convs = conversations[currentAssistant];
  convCounter++;
  const conv = {
    id: `conv_${Date.now()}_${convCounter}`,
    title: '新对话',
    messages: [],
  };
  convs.unshift(conv);
  activeConvId = conv.id;
  renderConversations();
  clearChatMessages();
  showEmptyState(true);
  document.getElementById('chatInput').focus();
}

function switchConversation(convId) {
  activeConvId = convId;
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
  const convs = conversations[currentAssistant];
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
  renderConversations();
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
  const convs = conversations[currentAssistant] || [];
  container.innerHTML = convs.map(c => `
    <div class="sb-item ${c.id === activeConvId ? 'active' : ''}"
         onclick="switchConversation('${c.id}')" title="${escapeAttr(c.title)}">
      <span class="sb-item-icon">▸</span>
      <span class="sb-item-name">${escapeHtml(c.title)}</span>
      <button class="sb-item-del" onclick="deleteConversation('${c.id}', event)">✕</button>
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

  // Update title from first message
  if (conv.messages.length === 0) {
    conv.title = userText.substring(0, 30) + (userText.length > 30 ? '...' : '');
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
  } else {
    appendBubble('user', userText);
    conv.messages.push({ role: 'user', content: userText });
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
      showReport(resp.result);
    } else {
      const errMsg = '处理失败: ' + (resp ? resp.result : '未知错误');
      appendBubble('ai', errMsg);
      conv.messages.push({ role: 'ai', content: errMsg });
    }
  } else {
    // Text message: use streaming API
    _streamTokenCount = 0;
    _activeStreamBubble = createStreamingBubble();
    document.getElementById('chatMessages').appendChild(_activeStreamBubble.element);
    scrollChat();

    try {
      await eel.send_message_stream(userText)();
      // on_stream_done callback handles finalization
    } catch (e) {
      // Network error: eel call itself failed
      if (_activeStreamBubble) {
        _activeStreamBubble.finalize('⚠️ 连接错误: ' + e);
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
        if (resp.ok) { appendSystem(resp.msg); renderBOMTable(resp.items); setStatus(`已加载 BOM (${resp.count} 条)`); }
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
  document.getElementById('rightPanel').classList.toggle('collapsed');
}

// ═══════════ Theme ═══════════

function applyTheme(name) {
  document.body.setAttribute('data-theme', name);
  try { eel.save_theme(name)(); } catch(e) {}
}

// ═══════════ LLM Settings ═══════════

const PROVIDERS = {
  deepseek:  { url: 'https://api.deepseek.com/v1', models: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-v3'], defaultModel: 'deepseek-v4-pro' },
  openai:    { url: 'https://api.openai.com/v1', models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1'], defaultModel: 'gpt-4o' },
  qwen:      { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', models: ['qwen3.6-plus', 'qwen3.6-flash'], defaultModel: 'qwen3.6-plus' },
  glm:       { url: 'https://open.bigmodel.cn/api/paas/v4', models: ['glm-5.1', 'glm-5.1-flash'], defaultModel: 'glm-5.1' },
  moonshot:  { url: 'https://api.moonshot.cn/v1', models: ['kimi-k2.6', 'kimi-k2-flash'], defaultModel: 'kimi-k2.6' },
  siliconflow: { url: 'https://api.siliconflow.cn/v1', models: ['deepseek-ai/DeepSeek-V4-Flash', 'Qwen/Qwen3.6-Plus'], defaultModel: 'deepseek-ai/DeepSeek-V4-Flash' },
};
const PROVIDER_NAMES = { deepseek:'DeepSeek', openai:'OpenAI', qwen:'通义千问', glm:'智谱', moonshot:'Kimi', siliconflow:'硅基流动' };

function toggleSettings() {
  document.getElementById('settingsOverlay').classList.toggle('show');
  if (document.getElementById('settingsOverlay').classList.contains('show')) {
    eel.get_settings()().then(sett => {
      if (!sett) return;
      document.getElementById('setProvider').value = sett.provider || 'deepseek';
      document.getElementById('setApiKey').value = sett.api_key || '';
      document.getElementById('setBaseUrl').value = sett.base_url || '';
      document.getElementById('setTheme').value = sett.theme || 'dark';
      onProviderChange();
      const savedModel = sett.model || '';
      if (savedModel) {
        const sel = document.getElementById('setModelSelect');
        for (let i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value === savedModel) { sel.selectedIndex = i; break; }
        }
        if (sel.value !== savedModel) {
          sel.value = '__custom__';
          document.getElementById('setModelCustom').value = savedModel;
          document.getElementById('setModelCustom').style.display = 'block';
        }
      }
    });
  }
}

function closeSettings(e) {
  if (!e || e.target === document.getElementById('settingsOverlay')) {
    document.getElementById('settingsOverlay').classList.remove('show');
  }
}

function onProviderChange() {
  const p = document.getElementById('setProvider').value;
  const preset = PROVIDERS[p] || {};
  if (!document.getElementById('setBaseUrl').value) {
    document.getElementById('setBaseUrl').placeholder = preset.url || '';
  }
  const sel = document.getElementById('setModelSelect');
  sel.innerHTML = '';
  (preset.models || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    if (m === preset.defaultModel) opt.selected = true;
    sel.appendChild(opt);
  });
  const custom = document.createElement('option');
  custom.value = '__custom__'; custom.textContent = '自定义...';
  sel.appendChild(custom);
}

function onModelSelectChange() {
  const sel = document.getElementById('setModelSelect');
  document.getElementById('setModelCustom').style.display = sel.value === '__custom__' ? 'block' : 'none';
}

async function saveLLMSettings() {
  const provider = document.getElementById('setProvider').value;
  const apiKey = document.getElementById('setApiKey').value;
  const baseUrl = document.getElementById('setBaseUrl').value;
  const modelSel = document.getElementById('setModelSelect');
  let model = modelSel.value === '__custom__'
    ? document.getElementById('setModelCustom').value
    : modelSel.value;
  if (!model) model = (PROVIDERS[provider] || {}).defaultModel || '';
  const resp = await eel.update_llm_config(provider, apiKey, baseUrl, model)();
  if (resp.ok) {
    const cfg = await eel.get_llm_config()();
    updateLLMStatus(cfg);
    appendTip(`${PROVIDER_NAMES[provider] || provider} AI Agent 已就绪 · ${cfg.model}`, 'success');
  }
  document.getElementById('settingsOverlay').classList.remove('show');
}

function updateLLMStatus(cfg) {
  // Status badge removed from header — settings gear indicates config state
  // Kept for potential future use
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

// Called by Python file watcher
eel.expose(onPCBChanged, 'on_pcb_changed');
function onPCBChanged(filepath) {
  appendSystem(`📁 检测到 PCB 文件变化: ${filepath}`);
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
    _activeStreamBubble.finalize('⚠️ 流式输出中断: ' + errorMsg);
    const conv = getActiveConversation();
    conv.messages.push({ role: 'ai', content: _activeStreamBubble.getText() });
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }
  disableInput(false);
  setStatus('错误');
}
