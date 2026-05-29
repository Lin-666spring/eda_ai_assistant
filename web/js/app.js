/* ═══════════════════════════════════════════
   EDA AI 智能助手 — Frontend Logic
   ═══════════════════════════════════════════ */

let welcomeVisible = true;

// ═══════════ Init ═══════════

document.addEventListener('DOMContentLoaded', async () => {
  // Theme
  const sett = await eel.get_settings()();
  if (sett && sett.theme) applyTheme(sett.theme);

  // LLM config
  const cfg = await eel.get_llm_config()();
  updateLLMStatus(cfg);

  // Tab switching
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Enter key
  document.getElementById('chatInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
});

// ═══════════ Theme ═══════════

function applyTheme(name) {
  document.body.setAttribute('data-theme', name);
}

async function toggleTheme() {
  const current = document.body.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  await eel.save_theme(next)();
}

// ═══════════ Chat ═══════════

function quickCmd(text) {
  if (text === '生成 HTML') {
    generateHTMLBOM();
    return;
  }
  document.getElementById('chatInput').value = text;
  sendChat();
}

async function generateHTMLBOM() {
  setStatus('生成 HTML BOM 中...');
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
      appendConfigTip(resp.report || '生成失败', 'error');
    }
  } catch(e) { appendConfigTip('生成失败: ' + e, 'error'); }
  setStatus('就绪');
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  if (text === '生成 HTML' || text === '生成HTML') { input.value = ''; generateHTMLBOM(); return; }
  input.value = '';
  hideWelcome();
  appendBubble('user', text);
  setStatus('思考中...');
  disableInput(true);
  const resp = await eel.send_message(text)();
  disableInput(false);
  setStatus('就绪');
  if (resp && resp.ok) {
    appendBubble('ai', resp.result);
    showReport(resp.result);
  } else {
    appendBubble('ai', '处理失败: ' + (resp ? resp.result : '未知错误'));
  }
}

function hideWelcome() {
  if (!welcomeVisible) return;
  document.getElementById('welcomeBlock').style.display = 'none';
  welcomeVisible = false;
}

function appendBubble(type, text) {
  if (type === 'user') hideWelcome();
  const row = document.createElement('div');
  row.className = `msg-row ${type}`;

  const bubble = document.createElement('div');
  if (type === 'system') {
    bubble.className = 'bubble bubble-system';
  } else {
    bubble.className = `bubble bubble-${type}`;
  }

  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  bubble.innerHTML = escapeHtml(text) + `<div class="bubble-time">${time}</div>`;
  row.appendChild(bubble);
  document.getElementById('chatMessages').appendChild(row);
  scrollChat();
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

function appendConfigTip(text, type) {
  hideWelcome();
  const div = document.createElement('div');
  div.className = `config-tip ${type || detectSemantic(text)}`;
  div.textContent = text;
  document.getElementById('chatMessages').appendChild(div);
  scrollChat();
}

function detectSemantic(text) {
  const tl = text.toLowerCase();
  if (/未配置|无效|禁用|失败|错误/.test(tl)) return 'error';
  if (/通过|完成|已生成|成功|就绪/.test(tl)) return 'success';
  if (/请先|缺少|待处理|部分|注意/.test(tl)) return 'warning';
  return 'info';
}

function scrollChat() {
  const el = document.getElementById('chatMessages');
  el.scrollTop = el.scrollHeight;
}

function clearReport() {
  document.getElementById('reportStack').innerHTML = '';
  document.getElementById('reportEmpty').style.display = 'flex';
}

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
  // Parse the structured report into styled HTML
  const lines = text.split('\n');
  let html = '';
  let inHeader = false, inSection = false, currentSeverity = '';
  const sevClass = { 'ERROR': 'rp-error', 'WARNING': 'rp-warning', 'INFO': 'rp-info' };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    // Skip top border
    if (/^={10,}/.test(line) && i < 2) continue;
    // Report title
    if (line.includes('设计规则检查报告') || line.includes('BOM 健康检查报告') || line.includes('BOM 合并报告') || line.includes('封装校验') || line.includes('位号查重') || line.includes('BOM 健康') || line.includes('合并报告') || line.includes('校验报告')) {
      html += `<div class="rp-title">${escapeHtml(line.trim())}</div>`;
      continue;
    }
    // Separator
    if (/^[-=]{10,}/.test(line)) {
      html += '<hr class="rp-hr">';
      continue;
    }
    // Section header: 【ERROR】 or 【WARNING】 or 【INFO】
    const secMatch = line.match(/【(\w+)】(.+)/);
    if (secMatch) {
      const sev = secMatch[1].toUpperCase();
      currentSeverity = sevClass[sev] || '';
      html += `<div class="rp-section ${currentSeverity}"><div class="rp-section-head">${escapeHtml(line.trim())}</div>`;
      inSection = true;
      continue;
    }
    // Item within section
    if (inSection && line.startsWith('  •')) {
      const item = line.replace(/^  •\s*/, '');
      html += `<div class="rp-item">${escapeHtml(item)}</div>`;
      continue;
    }
    // Sub-line (位置/建议/理论)
    if (inSection && /^\s{4,}/.test(line)) {
      const sub = line.trim();
      if (sub.startsWith('位置:')) {
        html += `<div class="rp-sub rp-loc">${escapeHtml(sub)}</div>`;
      } else if (sub.startsWith('建议:')) {
        html += `<div class="rp-sub rp-sug">${escapeHtml(sub)}</div>`;
      } else if (sub.startsWith('理论:')) {
        html += `<div class="rp-sub rp-theory">${escapeHtml(sub)}</div>`;
      }
      continue;
    }
    // Close section if blank line
    if (line.trim() === '' && inSection) {
      html += '</div>';
      inSection = false;
      continue;
    }
    // Regular text
    if (line.trim()) {
      html += `<div class="rp-line">${escapeHtml(line)}</div>`;
    }
  }
  if (inSection) html += '</div>';
  return html;
}

function setStatus(msg) {
  document.getElementById('statusMsg').textContent = msg;
}

function disableInput(disabled) {
  document.getElementById('chatInput').disabled = disabled;
  document.getElementById('sendBtn').disabled = disabled;
}

// ═══════════ File imports (native browser picker — always on top) ═══════════

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
        else { appendConfigTip(resp.msg, 'error'); setStatus('加载失败'); }
      } else if (type === 'pcb') {
        const resp = await eel.import_pcb_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); setStatus(`已加载 PCB: ${resp.pcb ? resp.pcb.net_count + ' nets' : ''}`); }
        else { appendConfigTip(resp.msg, 'error'); setStatus('加载失败'); }
      } else if (type === 'pos') {
        const resp = await eel.import_pos_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); setStatus('已加载坐标'); }
        else { appendConfigTip(resp.msg, 'error'); setStatus('加载失败'); }
      }
    } catch(err) { appendConfigTip('导入失败: ' + err, 'error'); setStatus('导入失败'); }
    input.value = '';
  };
  reader.readAsArrayBuffer(file);
}

// ═══════════ BOM table ═══════════

function renderBOMTable(items) {
  const tbody = document.querySelector('#bomTable tbody');
  tbody.innerHTML = items.map((item, i) => `
    <tr>
      <td style="color:var(--text-muted);text-align:right;padding-right:12px;width:32px">${i + 1}</td>
      <td>${escapeHtml(item.reference)}</td>
      <td>${escapeHtml(item.value)}</td>
      <td>${escapeHtml(item.package)}</td>
      <td>${escapeHtml(item.part_number)}</td>
      <td style="text-align:right">${item.quantity}</td>
      <td style="color:var(--text-muted)">${escapeHtml(item.description)}</td>
      <td style="color:var(--text-muted)">${escapeHtml(item.manufacturer)}</td>
    </tr>
  `).join('');
  document.getElementById('bomEmpty').style.display = items.length ? 'none' : 'flex';
}

// ═══════════ Operations (quick-commands) ═══════════

async function runOp(name, fn) {
  setStatus(`正在${name}...`);
  const resp = await fn();
  if (resp.ok) {
    appendBubble('ai', resp.report);
    showReport(resp.report);
    setStatus('就绪');
  } else {
    appendConfigTip(resp.report || '操作失败', 'error');
    setStatus('操作失败');
  }
}

// Provider presets with model lists
const PROVIDERS = {
  deepseek: {
    url: 'https://api.deepseek.com/v1',
    models: ['deepseek-v4-pro', 'deepseek-v4-flash', 'deepseek-v3', 'deepseek-r1'],
    defaultModel: 'deepseek-v4-pro',
  },
  openai: {
    url: 'https://api.openai.com/v1',
    models: ['gpt-5.4', 'gpt-4o', 'gpt-4o-mini', 'gpt-4.1'],
    defaultModel: 'gpt-5.4',
  },
  qwen: {
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen3.6-plus', 'qwen3.6-flash', 'qwen-plus', 'qwen-max'],
    defaultModel: 'qwen3.6-plus',
  },
  glm: {
    url: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-5.1', 'glm-5.1-flash', 'glm-4-plus', 'glm-4-flash'],
    defaultModel: 'glm-5.1',
  },
  moonshot: {
    url: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2.6', 'kimi-k2-flash', 'kimi-k2-turbo'],
    defaultModel: 'kimi-k2.6',
  },
  siliconflow: {
    url: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V4-Flash', 'deepseek-ai/DeepSeek-V3', 'Qwen/Qwen3.6-Plus', 'Pro/GLM-5.1'],
    defaultModel: 'deepseek-ai/DeepSeek-V4-Flash',
  },
};

function onProviderChange() {
  const p = document.getElementById('setProvider').value;
  const preset = PROVIDERS[p] || {};
  if (!document.getElementById('setBaseUrl').value) {
    document.getElementById('setBaseUrl').placeholder = preset.url || '';
  }
  // Populate model dropdown
  const sel = document.getElementById('setModelSelect');
  sel.innerHTML = '';
  (preset.models || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    if (m === preset.defaultModel) opt.selected = true;
    sel.appendChild(opt);
  });
  // Also add custom option
  const custom = document.createElement('option');
  custom.value = '__custom__'; custom.textContent = '自定义...';
  sel.appendChild(custom);
  onModelSelectChange();
}

function onModelSelectChange() {
  const sel = document.getElementById('setModelSelect');
  const customInput = document.getElementById('setModelCustom');
  if (sel.value === '__custom__') {
    customInput.style.display = 'block';
    customInput.focus();
  } else {
    customInput.style.display = 'none';
  }
}

// ═══════════ LLM settings ═══════════

function toggleSettings() {
  document.getElementById('settingsOverlay').classList.toggle('show');
  if (document.getElementById('settingsOverlay').classList.contains('show')) {
    eel.get_settings()().then(sett => {
      if (!sett) return;
      document.getElementById('setProvider').value = sett.provider || 'deepseek';
      document.getElementById('setApiKey').value = sett.api_key || '';
      document.getElementById('setBaseUrl').value = sett.base_url || '';
      // Populate model dropdown, then select saved model
      onProviderChange();
      const savedModel = sett.model || '';
      if (savedModel) {
        const sel = document.getElementById('setModelSelect');
        for (let i = 0; i < sel.options.length; i++) {
          if (sel.options[i].value === savedModel) {
            sel.selectedIndex = i; break;
          }
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

async function saveLLMSettings() {
  const provider = document.getElementById('setProvider').value;
  const apiKey = document.getElementById('setApiKey').value;
  const baseUrl = document.getElementById('setBaseUrl').value;
  const modelSel = document.getElementById('setModelSelect');
  let model = modelSel.value === '__custom__'
    ? document.getElementById('setModelCustom').value
    : modelSel.value;
  if (!model) {
    const preset = PROVIDERS[provider];
    model = preset ? preset.defaultModel : '';
  }
  const resp = await eel.update_llm_config(provider, apiKey, baseUrl, model)();
  if (resp.ok) {
    const cfg = await eel.get_llm_config()();
    updateLLMStatus(cfg);
    appendConfigTip(`${PROVIDER_NAMES[provider] || provider} AI Agent 已就绪  |  模型: ${cfg.model}`, 'success');
  }
  document.getElementById('settingsOverlay').classList.remove('show');
}

const PROVIDER_NAMES = {
  deepseek: 'DeepSeek', openai: 'OpenAI', qwen: '通义千问',
  glm: '智谱', moonshot: 'Kimi', siliconflow: '硅基流动',
};

function updateLLMStatus(cfg) {
  const el = document.getElementById('llmStatus');
  if (cfg && cfg.is_configured) {
    const name = PROVIDER_NAMES[cfg.provider] || cfg.provider;
    el.textContent = `${name} · ${cfg.model}`;
    el.className = 'llm-status configured';
  } else {
    el.textContent = '未配置';
    el.className = 'llm-status';
    appendConfigTip('未配置 LLM API Key，使用本地关键词匹配模式。点击右上角设置。', 'error');
  }
}

// ═══════════ Panel tabs ═══════════

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelector(`[data-tab="${name}"]`).classList.add('active');
  document.getElementById(`tab-${name}`).classList.add('active');
}

// ═══════════ Utils ═══════════

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}

// Called by Python file watcher as eel.on_pcb_changed()
eel.expose(onPCBChanged, 'on_pcb_changed');
function onPCBChanged(filepath) {
  appendSystem(`📁 检测到 PCB 文件变化: ${filepath}`);
  setStatus(`已同步 PCB`);
}
