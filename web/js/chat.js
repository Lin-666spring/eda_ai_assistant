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
        _activeStreamBubble.finalize('查询失败：' + (resp ? resp.result : '未知错误'));
        const failText = _activeStreamBubble.getText();
        conv.messages.push({ role: 'ai', content: failText });
        _persistMessage(activeConvId, 'ai', failText);
      }
    } catch(e) {
      if (_activeStreamBubble) {
        _activeStreamBubble.finalize('网络错误：' + e);
        const errText = _activeStreamBubble.getText();
        conv.messages.push({ role: 'ai', content: errText });
        _persistMessage(activeConvId, 'ai', errText);
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
  if (!conv) { input.value = userText; return; }  // 无助手弹了新建框：别吞用户输入

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
    // Image analysis: 非流式接口，但同样给加载动效（多模态推理常要十几秒）
    _streamTokenCount = 0;
    _activeStreamBubble = createStreamingBubble();
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
    _activeStreamBubble.finalize(resultText);
    conv.messages.push({ role: 'ai', content: resultText });
    _persistMessage(activeConvId, 'ai', resultText);
    if (resp && resp.ok) showReport(resp.result);
    _activeStreamBubble = null;
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
  // 不含尖括号，marked v15 实测原样产出 href="javascript:…"。parse 后按协议
  // 中和为 '#'，http(s) 等正常链接不受影响。
  return html.replace(/href\s*=\s*["']?\s*(javascript|data):[^"'\s>]*/gi, 'href="#"');
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
 *  首个 token 到达前显示「思考中」动效（三点脉冲 + 轮换文案 + 计时），
 *  避免用户对着空气泡干等。
 *  Returns { updateToken(token), finalize(fullText), setStatus(text), element } */
function createStreamingBubble() {
  showEmptyState(false);
  // Clear leftover tool-call cards from a previous turn
  _activeToolCards.forEach(c => c.remove());
  _activeToolCards = [];
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

