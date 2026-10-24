// ═══════════════════════════════════════════
//  Chat —— P1-6 阶段C 自 app.js 拆出（原 1586-2014 行）
//  featureCmd / sendChat / 生成 HTML BOM / 气泡渲染（含 renderMarkdown）/ Report
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

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
      appendBubble('ai', '请输入要查询的内容，如「查询知识库: IPC-2221载流能力」');
      return;
    }
    showEmptyState(false);
    const conv = getActiveConversation();
    if (!conv) { input.value = userText; return; }  // 无助手弹了新建框：别吞用户输入
    // P1-22(a)（验收 2026-10-24）：发起时绑定会话与气泡 —— await 期间用户
    // 可切走会话/发起新流，完成回调用 activeConvId 落库会写进别的会话，
    // 用 _activeStreamBubble 会 finalize 到别人的气泡（两者都可能已被换掉）。
    const convId = activeConvId;
    const myBubble = _activeStreamBubble;

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
        if (_activeStreamBubble === myBubble) _activeStreamBubble.finalize(resp.result);
        conv.messages.push({ role: 'ai', content: resp.result });
        _persistMessage(convId, 'ai', resp.result);
      } else {
        const failText = '查询失败：' + (resp ? resp.result : '未知错误');
        if (_activeStreamBubble === myBubble) _activeStreamBubble.finalize(failText);
        conv.messages.push({ role: 'ai', content: failText });
        _persistMessage(convId, 'ai', failText);
      }
    } catch(e) {
      const errText = '网络错误：' + e;
      if (_activeStreamBubble === myBubble) _activeStreamBubble.finalize(errText);
      conv.messages.push({ role: 'ai', content: errText });
      _persistMessage(convId, 'ai', errText);
    }
    if (_activeStreamBubble === myBubble) _activeStreamBubble = null;
    disableInput(false);
    setStatus('就绪');
    renderConversations();
    return;
  }

  showEmptyState(false);

  // Get or create conversation
  const conv = getActiveConversation();
  if (!conv) { input.value = userText; return; }  // 无助手弹了新建框：别吞用户输入

  // Update title from first message
  if (conv.messages.length === 0) {
    conv.title = userText.substring(0, 30) + (userText.length > 30 ? '...' : '');
    _persistConversation(conv);
    renderConversations();
  }

  // P1-22(b)（验收 2026-10-24）：新消息打断旧流必须 finalize 旧气泡 ——
  // 只置 null 会让光标残留、thinking 计时器永不清理；半截回复按发起会话
  // 落库（新流起跑时后端代次 +1，旧流其后的 token/done/error 不再下发）。
  _abortActiveStream('\n\n*(已停止生成)*');

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
    // Image analysis: 非流式接口，但同样给加载动效（多模态推理常要十几秒）
    _streamTokenCount = 0;
    _activeStreamBubble = createStreamingBubble();
    // P1-22(a)（验收 2026-10-24）：发起时绑定会话与气泡（同知识库路径）——
    // await 期间切走会话时旧气泡可能已被清掉、activeConvId 已指向别的会话，
    // 完成 时直接 finalize/落库会崩溃或写错会话。
    const convId = activeConvId;
    const myBubble = _activeStreamBubble;
    document.getElementById('chatMessages').appendChild(_activeStreamBubble.element);
    _activeStreamBubble.setStatus('正在分析图片…');
    scrollChat();

    let resp;
    try {
      resp = await eel.send_image(userText, currentImage)();
    } catch(e) {
      resp = { ok: false, result: '网络错误: ' + e };
    }
    currentImage = null; hideImagePreview();
    disableInput(false);
    setStatus('就绪');

    const resultText = (resp && resp.ok)
      ? resp.result
      : ('处理失败: ' + (resp ? resp.result : '未知错误'));
    if (_activeStreamBubble === myBubble) _activeStreamBubble.finalize(resultText);
    conv.messages.push({ role: 'ai', content: resultText });
    _persistMessage(convId, 'ai', resultText);
    if (resp && resp.ok) showReport(resp.result);
    if (_activeStreamBubble === myBubble) _activeStreamBubble = null;
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
      // P1-22(c)（验收 2026-10-24）：丢弃工具卡先停计时器（只 remove 会泄漏 setInterval）
      _discardToolCards();
      // P1-22(a)（验收 2026-10-24）：按发起会话定格落库半截回复，
      // 并 finalize 旧气泡（清光标 + 停 thinking 计时器，见 _abortActiveStream）。
      _abortActiveStream('\n\n*(连接错误: ' + e + ')*');
      setStatus('错误');
    }
  }
  renderConversations();
}

/** 停止生成（2026-10-10 前端批）：作废在途流（后端代次 +1，其后的
 *  token/done/error 不再下发），气泡定格在已收到的半截内容并落库。
 *  后端 LLM 请求本身无法中断，跑完即弃；知识库/图片两条非流式路径
 *  不受影响（它们没有 cancel 概念，等结果即可）。 */
async function stopGeneration() {
  try { await eel.cancel_stream()(); } catch (e) { /* 后端不在也不影响前端收尾 */ }
  _activeToolCards.forEach(c => _finishToolCard(c));
  _activeToolCards = [];
  if (_activeStreamBubble) {
    const text = _activeStreamBubble.getText() + '\n\n*(已停止生成)*';
    _activeStreamBubble.finalize(text);
    const conv = getActiveConversation();
    conv.messages.push({ role: 'ai', content: text });
    _persistMessage(activeConvId, 'ai', text);
    _activeStreamBubble = null;
    _streamTokenCount = 0;
  }
  disableInput(false);
  setStatus('已停止');
  renderConversations();
}

async function generateHTMLBOM() {
  const btn = _btnFromEvent();
  _btnLoading(btn, '生成中');
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
  _btnLoaded(btn);
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
  let html;
  try {
    html = marked.parse(safe);
  } catch (e) {
    return escapeHtml(safe);
  }
  // 2026-10-08（P1-12）：剥裸 HTML 挡不住 markdown 链接 —— [x](javascript:…)
  // 不含尖括号，marked v15 实测原样产出 href="javascript:…"。
  // 2026-10-24（验收 A-2）：按字面量匹配协议可被实体编码绕过 —— 浏览器解析
  // 属性值时先解码 HTML 实体再解析 URL，`javascript&colon;alert(1)`、
  // `&#106;avascript&#58;…` 都能执行。枚举实体变体打不完，改为：先把
  // href/src 的值解码回真实字符，再做 scheme 白名单（http/https/mailto，
  // 图片另放行 data:image/…）。
  const decodeEntities = (s) => s.replace(
    /&(#[xX]?[0-9a-fA-F]+|colon|amp|quot|apos|lt|gt|semi);?/g,
    (m, body) => {
      let code;
      if (body.charCodeAt(0) === 35) { // '#'
        code = (body[1] === 'x' || body[1] === 'X')
          ? parseInt(body.slice(2), 16)
          : parseInt(body.slice(1), 10);
      } else {
        code = { colon: 58, amp: 38, quot: 34, apos: 39,
                 lt: 60, gt: 62, semi: 59 }[body.toLowerCase()];
      }
      return Number.isFinite(code) ? String.fromCharCode(code) : m;
    });
  const isSafeUrl = (url) => {
    const decoded = decodeEntities(url).trim();
    // 控制字符（\t\n\r 可用来拆分 scheme）直接拒绝
    if (/[\x00-\x1f\x7f]/.test(decoded)) return false;
    const m = decoded.match(/^([a-zA-Z][a-zA-Z0-9+.\-]*):/);
    if (!m) return true;  // 相对地址 / #锚 / //host
    const scheme = m[1].toLowerCase();
    return scheme === 'http' || scheme === 'https' || scheme === 'mailto';
  };
  return html.replace(
    /(\b(href|src)\s*=\s*)(["'])([\s\S]*?)\3/gi,
    (m, pre, attr, q, val) => {
      const decoded = decodeEntities(val).trim();
      const ok = isSafeUrl(val) ||
        (attr.toLowerCase() === 'src' && /^data:image\//i.test(decoded));
      return ok ? m : pre + q + '#' + q;
    });
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

// P1-22(a)（验收 2026-10-24）：本轮流式请求的「发起时会话」。流式完成回调
// 到达时 activeConvId 可能已被切走（切换/删除/新建），落库必须用它而不是
// 完成时的 activeConvId，否则回复落错会话。
let _activeStreamConvId = null;
// P1-26（验收 2026-10-24）：本轮流式回答是否真的调用了工具（产出报告/工具
// 成果）。onToolCall 置位，createStreamingBubble 复位；纯闲聊不进报告栈。
let _streamHadToolCall = false;

/** P1-22(a/b)（验收 2026-10-24）：作废在途流的前端收尾 —— 旧气泡 finalize
 *  （清光标 + 停 thinking 计时器），半截回复落到「发起该流」的会话。
 *  切换会话/新消息打断时 activeConvId 已指向目标会话，按它落库会把回复
 *  写进错误的会话（与后端 cancel_stream 代次作废配套：调用方负责 cancel，
 *  本函数不调 —— 打断后立即发新流时避免代次竞态）。
 *  半截内容为空时不落库：非流式路径（图片/知识库）的空占位气泡不值得
 *  留一条「已停止」消息，完整结果由其自身完成路径按发起会话补落。 */
function _abortActiveStream(note) {
  if (!_activeStreamBubble) return;
  const partial = _activeStreamBubble.getText();
  const convId = _activeStreamConvId || activeConvId;
  _activeStreamBubble.finalize(partial ? partial + note : partial);
  _activeStreamBubble = null;
  _streamTokenCount = 0;
  disableInput(false);
  if (partial.trim()) {
    const conv = findConversation(convId);
    if (conv) {
      conv.messages.push({ role: 'ai', content: partial + note });
      _persistMessage(convId, 'ai', partial + note);
    }
  }
  renderConversations();
}

/** Create a streaming AI bubble that updates incrementally.
 *  首个 token 到达前显示「思考中」动效（三点脉冲 + 轮换文案 + 计时），
 *  避免用户对着空气泡干等。
 *  Returns { updateToken(token), finalize(fullText), setStatus(text), element } */
function createStreamingBubble() {
  showEmptyState(false);
  // Clear leftover tool-call cards from a previous turn
  // P1-22(c)（验收 2026-10-24）：先停计时器再移除（只 remove 泄漏 setInterval）
  _discardToolCards();
  // P1-22(a)：记录发起会话；P1-26：新一轮流的工具成果标记复位
  _activeStreamConvId = activeConvId;
  _streamHadToolCall = false;
  // 注意：element 必须是 .msg-row 外壳（不是裸 .bubble）：
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
  const thinking = _mountThinking(bubble);   // 立刻进入加载动效

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
      if (bubble.classList.contains('thinking')) {
        thinking.stop();
        buffer += token;
        tokenCount++;
        rerender();                       // 首个 token 立即出字，不等节流
        return;
      }
      buffer += token;
      tokenCount++;
      if (tokenCount % RERENDER_EVERY === 0) {
        rerender();
      }
    },
    /** 运行中的状态文案（不走 Markdown，保持加载动效） */
    setStatus(text) { thinking.become(text); },
    /** 让思考文案跟随当前动作（如「正在调用工具」） */
    think(text) { thinking.become(text); },
    finalize(fullText) {
      thinking.stop();
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

/** P1-26（验收 2026-10-24）：用户是否正开着右面板看「报告」以外的 Tab。
 *  抽成纯函数便于回归（面板折叠 = 没在看任何面板，强切无代价）。 */
function _userReadingOtherTab(panelCollapsed, activeTabName) {
  return !panelCollapsed && !!activeTabName && activeTabName !== 'report';
}

function showReport(text) {
  const stack = document.getElementById('reportStack');
  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  const card = document.createElement('div');
  card.className = 'report-card';
  card.innerHTML = `<div class="report-card-time">${time}</div>` + formatReport(text);
  stack.insertBefore(card, stack.firstChild);
  document.getElementById('reportEmpty').style.display = 'none';
  // P1-26（验收 2026-10-24）：报告照常入栈，但用户正开着面板看别的 Tab
  // （如 BOM 表）时不再强切 —— 只在「报告」页签上加未读角标；面板折叠
  // 或已停在报告页时维持原强切（此时不存在抢用户视线的代价）。
  const panel = document.getElementById('rightPanel');
  const activeBtn = document.querySelector('.tab-btn.active');
  const activeTab = activeBtn ? activeBtn.dataset.tab : null;
  if (_userReadingOtherTab(!!(panel && panel.classList.contains('collapsed')), activeTab)) {
    _badgeReportTab();
  } else {
    switchTab('report');
  }
}

/** 「报告」页签未读角标（无新 CSS 可用，用内联样式小圆点） */
function _badgeReportTab() {
  const btn = document.querySelector('.tab-btn[data-tab="report"]');
  if (!btn || btn.querySelector('.tab-notify-dot')) return;
  const dot = document.createElement('span');
  dot.className = 'tab-notify-dot';
  dot.style.cssText = 'display:inline-block;width:6px;height:6px;border-radius:50%;'
    + 'background:var(--accent);margin-left:4px;vertical-align:2px;';
  btn.appendChild(dot);
}

// P1-26：角标是「未读」语义 —— 用户点开报告页即清。switchTab 定义在
// imports.js（本批不可改文件），这里用事件委托补上清除时机。
(function() {
  document.addEventListener('click', (e) => {
    const t = e.target;
    const btn = (t && typeof t.closest === 'function') ? t.closest('.tab-btn[data-tab="report"]') : null;
    if (!btn) return;
    const dot = btn.querySelector('.tab-notify-dot');
    if (dot) dot.remove();
  });
})();

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

