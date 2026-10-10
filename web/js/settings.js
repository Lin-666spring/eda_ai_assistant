// ═══════════════════════════════════════════
//  Settings —— P1-6 阶段C 自 app.js 拆出（原 2139-2543 行）
//  主题与强调色 / Premium 设置（提供商·模型·连接测试）/ 数据目录 / 清空数据
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ Theme & Accent ═══════════

var _currentAccent = '#2565fe';

/**
 * 应用主题到界面。**不落盘** —— 落盘只发生在用户真的点选主题卡片时
 * （见 saveThemePreference）。
 *
 * 历史坑（2026-10-03 修）：这里以前无条件 `eel.save_theme(theme)`，
 * 而启动流程本身会调用 applyTheme(已保存的值)，等于每次开机都把当前值
 * 原样写回 settings.json。于是"把默认主题改成浅色"永远不生效：用户改完
 * 设置文件、下次启动又被前端按内存里的旧值写回去，只有重启后仍在库里的
 * 旧值存活。读配置的动作不该有写副作用。
 */
function applyTheme(name) {
  var theme = (name === 'dark') ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', theme);
  document.body.setAttribute('data-theme', theme);
  // update theme radio buttons
  document.querySelectorAll('.theme-card input').forEach(function(r) {
    r.checked = r.value === theme;
  });
}

/** 用户点选主题时调用：写 localStorage（首屏引导用）+ 后端 settings。 */
function saveThemePreference(theme) {
  var t = (theme === 'dark') ? 'dark' : 'light';
  try { localStorage.setItem('eda-theme', t); } catch (e) {}
  try { eel.save_theme(t)(); } catch (e) {}
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
  }  var note = document.getElementById('providerNote');
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
  // 注意：不要写成 `e.target === overlay`：按钮传进来的 target 是按钮自己，
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
  // confirm()/alert() 在这里是漏网的原生弹窗（项目约定：一律走自定义对话框）
  showConfirmDialog({
    title: '清除本地数据',
    message: '确定要清除所有本地数据吗？\n此操作不可撤销，清除后应用将重新加载。',
    okText: '清除',
    onOk: async () => {
      try {
        await eel.clear_all_data()();
        showToast('数据已清除，应用即将重新加载', 'success');
        setTimeout(() => location.reload(), 600);
      } catch (e) {
        showToast('清除失败: ' + (e.message || e), 'error');
      }
    },
  });
}

