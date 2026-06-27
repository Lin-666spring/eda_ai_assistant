/**
 * EDA AI Assistant — iframe panel logic.
 *
 * Handles:
 *  - Server health polling
 *  - Streaming chat via SSE
 *  - Quick action buttons (BOM, DRC, Review)
 *  - PostMessage communication with LCEDA host
 */

// ── State ────────────────────────────────────────────────────

var API_BASE = 'http://127.0.0.1:8710/api/v1';

var streamingES = null;
var activeStreamBubble = null;
var streamContent = '';
var serverConnected = false;

// ── DOM refs ─────────────────────────────────────────────────

var messages = document.getElementById('messages');
var chatInput = document.getElementById('chat-input');
var sendBtn = document.getElementById('send-btn');
var statusEl = document.getElementById('connection-status');

// ═════════════════════════════════════════════════════════════
//  Server Connection
// ═════════════════════════════════════════════════════════════

function checkServer() {
  var controller = new AbortController();
  var timeoutId = setTimeout(function () { controller.abort(); }, 2000);

  fetch(API_BASE + '/health', { signal: controller.signal })
    .then(function (resp) {
      clearTimeout(timeoutId);
      if (resp.ok) {
        setServerStatus(true);
      } else {
        setServerStatus(false);
      }
    })
    .catch(function () {
      setServerStatus(false);
    });
}

function setServerStatus(connected) {
  serverConnected = connected;
  if (connected) {
    statusEl.textContent = '● 已连接';
    statusEl.className = 'status-connected';
  } else {
    statusEl.textContent = '● 未连接';
    statusEl.className = 'status-disconnected';
  }
}

// Poll server health every 5 seconds
setInterval(checkServer, 5000);
checkServer();

// ═════════════════════════════════════════════════════════════
//  Messaging
// ═════════════════════════════════════════════════════════════

/** Handle keyboard: Enter to send, Shift+Enter for newline. */
function handleKeyDown(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

function sendMessage() {
  var text = chatInput.value.trim();
  if (!text || streamingES) return; // Don't send while streaming

  chatInput.value = '';
  chatInput.style.height = 'auto';

  // Clear empty state
  var emptyEl = messages.querySelector('.empty-state');
  if (emptyEl) emptyEl.remove();

  // Append user bubble
  appendBubble('user', text);

  // Create streaming AI bubble
  activeStreamBubble = createStreamingBubble();
  streamContent = '';

  // Connect SSE
  var params = new URLSearchParams({ text: text, agent_mode: 'false' });
  var url = API_BASE + '/chat/stream?' + params.toString();
  streamingES = new EventSource(url);

  streamingES.addEventListener('token', function (e) {
    streamContent += e.data;
    if (activeStreamBubble) {
      activeStreamBubble.textContent = streamContent;
      var cursor = document.createElement('span');
      cursor.className = 'stream-cursor';
      activeStreamBubble.appendChild(cursor);
    }
    scrollToBottom();
  });

  streamingES.addEventListener('done', function (e) {
    if (activeStreamBubble) {
      activeStreamBubble.textContent = e.data;
      activeStreamBubble.classList.remove('streaming');
    }
    if (streamingES) streamingES.close();
    streamingES = null;
    activeStreamBubble = null;
    streamContent = '';
    scrollToBottom();
  });

  streamingES.addEventListener('error', function () {
    if (activeStreamBubble) {
      if (!streamContent) {
        activeStreamBubble.textContent = '连接中断，请检查 API 服务器是否运行';
      }
      activeStreamBubble.classList.remove('streaming');
    }
    if (streamingES) streamingES.close();
    streamingES = null;
    activeStreamBubble = null;
    streamContent = '';
  });

  scrollToBottom();
}

// ═════════════════════════════════════════════════════════════
//  Quick Actions (send PostMessage to LCEDA host)
// ═════════════════════════════════════════════════════════════

function handleAction(command) {
  // Try PostMessage to LCEDA host first
  window.parent.postMessage({ command: command, payload: null }, '*');

  // HTTP fallback if server is connected
  switch (command) {
    case 'import-current-bom':
      if (serverConnected) {
        showSystemMessage('正在导入 BOM...（等待 LCEDA 响应）');
      }
      break;
    case 'drc-check':
      if (serverConnected) {
        runDrcCheck();
      }
      break;
    case 'multi-agent-review':
      if (serverConnected) {
        runMultiAgentReview();
      }
      break;
  }
}

function runDrcCheck() {
  showSystemMessage('正在运行 DRC 检查...');
  fetch(API_BASE + '/rules/check', { method: 'POST' })
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
      if (data.ok) {
        appendBubble('ai', data.report || 'DRC 检查完成');
      } else {
        appendBubble('ai', 'DRC 检查失败: ' + (data.report || '未知错误'));
      }
    })
    .catch(function () {
      appendBubble('ai', '无法连接 API 服务器');
    });
}

function runMultiAgentReview() {
  showSystemMessage('正在运行多智能体审查...');
  fetch(API_BASE + '/review/multi-agent', { method: 'POST' })
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
      if (data.ok) {
        appendBubble('ai', data.report || '审查完成');
      } else {
        appendBubble('ai', '审查失败: ' + (data.report || '未知错误'));
      }
    })
    .catch(function () {
      appendBubble('ai', '无法连接 API 服务器');
    });
}

// ═════════════════════════════════════════════════════════════
//  Bubble Rendering
// ═════════════════════════════════════════════════════════════

function appendBubble(role, text) {
  var row = document.createElement('div');
  row.className = 'bubble-row ' + role;

  var bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.classList.add(role);
  bubble.textContent = text;

  row.appendChild(bubble);
  messages.appendChild(row);
  scrollToBottom();
  return bubble;
}

function createStreamingBubble() {
  var row = document.createElement('div');
  row.className = 'bubble-row ai';

  var bubble = document.createElement('div');
  bubble.className = 'bubble ai streaming';
  bubble.textContent = '';

  row.appendChild(bubble);
  messages.appendChild(row);
  return bubble;
}

function showSystemMessage(text) {
  appendBubble('system', text);
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

// ═════════════════════════════════════════════════════════════
//  Receive messages from LCEDA host
// ═════════════════════════════════════════════════════════════

window.addEventListener('message', function (event) {
  if (!event.data || typeof event.data.type !== 'string') return;

  var msg = event.data;
  switch (msg.type) {
    case 'bom-data':
      showSystemMessage('BOM 数据已导入');
      break;
    case 'drc-result':
      appendBubble('ai', typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data));
      break;
    case 'review-result':
      appendBubble('ai', typeof msg.data === 'string' ? msg.data : JSON.stringify(msg.data));
      break;
    case 'notification':
      showSystemMessage(String(msg.data));
      break;
  }
});
