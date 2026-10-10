// ═══════════════════════════════════════════
//  Utils —— P1-6 阶段C 自 app.js 拆出（原 2544-2787 行）
//  setStatus / withBusy / 按钮忙碌态 / escapeHtml / 确认对话框
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ Utils ═══════════

// ── 全局忙碌反馈 ──
// setStatus() 以前是空实现（新 UI 没有状态栏），所有调用点都白调了。
// 现在它驱动两个全局指示器：顶栏状态胶囊 + 顶部不确定进度条。
// 终态（就绪/已加载/失败…）自动收尾，运行态自动点亮进度条。

const _DONE_PREFIXES = ['就绪', '完成', '审查完成', '错误', '失败', '取消',
                        '已', '无', '加载失败', '生成失败', '导入失败', '审查失败'];

function _isDoneStatus(msg) {
  const s = String(msg || '');
  return _DONE_PREFIXES.some(p => s.startsWith(p));
}

let _busyDepth = 0;
let _statusToken = 0;
let _statusHideTimer = null;

function setStatus(msg, forceDone) {
  const pill = document.getElementById('statusPill');
  const bar = document.getElementById('topProgress');
  const token = ++_statusToken;
  if (_statusHideTimer) { clearTimeout(_statusHideTimer); _statusHideTimer = null; }

  if (!msg) {
    if (pill) pill.classList.add('hidden');
    if (bar) bar.classList.remove('on');
    return;
  }

  const isDone = forceDone === true || _isDoneStatus(msg);
  if (pill) {
    pill.classList.remove('hidden');
    pill.classList.toggle('done', isDone);
    pill.innerHTML = (isDone ? '<span class="status-check">✓</span>'
                             : '<span class="status-spinner"></span>')
      + `<span class="status-pill-text">${escapeHtml(msg)}</span>`;
  }
  if (bar) bar.classList.toggle('on', !isDone);
  if (isDone) {
    _statusHideTimer = setTimeout(() => {
      if (_statusToken !== token) return;        // 期间又开始了新任务 → 不收回
      if (pill) pill.classList.add('hidden');
      if (bar) bar.classList.remove('on');
    }, 1500);
  }
}

/** 包住一段异步任务：进入即点亮全局加载态，结束还原（可嵌套）。 */
async function withBusy(label, fn) {
  _busyDepth++;
  setStatus(label);
  try {
    return await fn();
  } finally {
    _busyDepth = Math.max(0, _busyDepth - 1);
    if (_busyDepth === 0) setStatus('就绪');
  }
}

// ── 按钮内联 loading ──
function _btnLoading(btn, label) {
  if (!btn || btn.dataset.loading === '1') return;
  btn.dataset.loading = '1';
  btn.dataset.origHtml = btn.innerHTML;
  btn.classList.add('is-loading');
  btn.disabled = true;
  if (label) btn.textContent = label;
}
function _btnLoaded(btn) {
  if (!btn || btn.dataset.loading !== '1') return;
  btn.dataset.loading = '';
  btn.classList.remove('is-loading');
  btn.disabled = false;
  if (btn.dataset.origHtml !== undefined) btn.innerHTML = btn.dataset.origHtml;
}
/** 取当前点击事件所在按钮（inline onclick="fn()" 里同步调用才拿得到）。 */
function _btnFromEvent() {
  try {
    const t = window.event && window.event.target;
    return t && t.closest ? t.closest('button') : null;
  } catch (e) { return null; }
}

// ── 后端调用统一加载反馈（白名单：只包慢调用，不碰 500ms 轮询）──
const _BUSY_LABELS = {
  check_rules: '运行 71 条设计规则…',
  review_design_multi_agent: '多智能体审查中…',
  generate_html_bom: '生成 HTML BOM…',
  import_bom_file: '解析 BOM 文件…',
  import_project_file: '解析工程文件…',
  import_pcb_file: '解析 PCB 文件…',
  import_pos_file: '解析坐标文件…',
  query_knowledge_base: '检索知识库…',
  get_drc_heatmap: '统计违规热力图…',
  load_demo_data: '加载示例数据…',
  send_image: '分析图片…',
  test_llm_connection: '测试模型连接…',
  fetch_provider_models: '拉取模型列表…',
  get_design_suggestions: '识别设计意图…',
};

function _wrapBusyCall(orig, label) {
  const wrapped = function (...args) {
    const call = orig.apply(eel, args);
    if (typeof call !== 'function') return call;
    return function (...cbArgs) {
      const last = cbArgs[cbArgs.length - 1];
      if (typeof last === 'function') return call.apply(eel, cbArgs);  // 回调式，不接管
      const p = call.apply(eel, cbArgs);
      if (!p || typeof p.then !== 'function') return p;
      return withBusy(label, () => p);
    };
  };
  wrapped.__busyWrapped = true;
  return wrapped;
}

// 注意：不能在本文件解析时就 eel[name] 逐个替换：eel 的 Python 函数是
//    `_websocket.onopen` → `eel._import_py_function(name)` 时才挂上去的
//    （见 eel/eel.js），那时 app.js 早就跑完了 —— 直接替换会静默跳过全部。
//    所以钩住「安装动作」本身：每装一个就按白名单包一层。
(function hookPythonFunctionImport() {
  if (typeof eel === 'undefined') return;
  const install = () => {
    Object.keys(_BUSY_LABELS).forEach(name => {
      const fn = eel[name];
      if (typeof fn === 'function' && !fn.__busyWrapped) {
        eel[name] = _wrapBusyCall(fn, _BUSY_LABELS[name]);
      }
    });
  };
  if (typeof eel._import_py_function === 'function') {
    const origImport = eel._import_py_function;
    eel._import_py_function = function (name) {
      origImport.call(eel, name);
      install();
    };
  }
  install();   // 万一脚本在 websocket 已连上之后才执行（热重载等）
})();

function disableInput(disabled) {
  document.getElementById('chatInput').disabled = disabled;
  document.getElementById('sendBtn').disabled = disabled;
  // 生成期间把发送键换成「停止」键（2026-10-10 前端批）
  const stop = document.getElementById('stopBtn');
  if (stop) stop.style.display = disabled ? '' : 'none';
}

// ── 思考动效：三点脉冲 + 轮换文案 + 计时 ──
const THINK_PHRASES = ['正在理解你的问题', '正在读取设计数据', '正在组织回答', '马上就好'];
const THINK_SLOW_TEXT = '仍在处理，这一步比较耗时…';

/** 渲染/刷新气泡里的「思考中」块。返回 { setText, stop } */
function _mountThinking(bubble, firstText) {
  const start = Date.now();
  let idx = 0, forced = firstText || '', interval = null;

  bubble.classList.add('thinking');
  bubble.innerHTML =
    '<div class="think">' +
      '<span class="think-dots"><i></i><i></i><i></i></span>' +
      `<span class="think-text">${escapeHtml(forced || THINK_PHRASES[0])}</span>` +
      '<span class="think-timer">0.0s</span>' +
    '</div>';
  const timerEl = bubble.querySelector('.think-timer');

  function setText(text) {
    const el = bubble.querySelector('.think-text');
    if (!el || el.textContent === text) return;
    el.textContent = text;
    el.style.animation = 'none';
    void el.offsetWidth;                 // 强制重排，重放淡入动画
    el.style.animation = '';
  }

  interval = setInterval(() => {
    const el = (Date.now() - start) / 1000;
    if (timerEl) {
      timerEl.textContent = el.toFixed(1) + 's';
      timerEl.classList.toggle('slow', el > 15);
    }
    if (el > 25) { setText(THINK_SLOW_TEXT); return; }
    if (forced) return;
    const i = Math.min(Math.floor(el / 2.5), THINK_PHRASES.length - 1);
    if (i !== idx) { idx = i; setText(THINK_PHRASES[i]); }
  }, 120);

  return {
    setText,
    become(text) { forced = text || ''; idx = 0; setText(forced || THINK_PHRASES[0]); },
    stop() { if (interval) { clearInterval(interval); interval = null; } bubble.classList.remove('thinking'); },
  };
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

