// ═══════════════════════════════════════════
//  Misc —— P1-6 阶段C 自 app.js 拆出（原 3243-3320 行）
//  Toast / 主动设计建议 / 键盘快捷键 / 快捷键提示
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

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
