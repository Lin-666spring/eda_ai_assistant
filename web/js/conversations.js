// ═══════════════════════════════════════════
//  Conversation Management —— P1-6 阶段C 自 app.js 拆出（原 818-963 行）
//  会话的建立/切换/删除/渲染
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

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
    workspaceId: currentWorkspaceId || DEFAULT_WORKSPACE_ID,
    messages: [],
    _loaded: true,
  };
  convs.unshift(conv);
  activeConvId = conv.id;
  _persistConversation(conv);
  _persistState();
  renderConversations();
  clearChatMessages();
  closeSubPage();
  showEmptyState(true);
  document.getElementById('chatInput').focus();
}

async function switchConversation(convId) {
  activeConvId = convId;
  _persistState();
  renderConversations();
  clearChatMessages();
  showEmptyState(false);
  closeSubPage();

  // 历史会话的消息是按需加载的（load_all 不带 messages）
  const conv = findConversation(convId);
  if (conv && !conv._loaded) {
    try {
      const resp = await eel.db_load_messages(convId)();
      if (resp && resp.ok) {
        conv.messages = (resp.messages || []).map(m => ({
          role: m.role,
          content: m.content,
          image: m.image || undefined,
        }));
      }
    } catch (e) {}
    conv._loaded = true;
  }
  if (activeConvId !== convId) return;   // 加载期间用户又切走了

  const msgs = (conv && conv.messages) || [];
  if (msgs.length > 0) {
    msgs.forEach(m => {
      if (m.image) appendBubbleWithImage(m.role, m.content, m.image);
      else appendBubble(m.role, m.content);
    });
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
        const remaining = getWorkspaceConversations();
        if (remaining.length > 0) {
          switchConversation(remaining[0].id);
        } else {
          activeConvId = null;
          clearChatMessages();
          closeSubPage();
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
  const countEl = document.getElementById('conversationCount');
  if (!container) return;
  if (!currentAssistantInstance) {
    if (countEl) countEl.textContent = '';
    container.innerHTML = '<div class="session-empty">请先新建助手</div>';
    return;
  }
  // 左侧栏只显示「当前工作区」下的对话 —— 工作区隔离的核心
  const convs = getWorkspaceConversations();
  if (countEl) countEl.textContent = convs.length ? String(convs.length) : '';
  if (convs.length === 0) {
    container.innerHTML = '<div class="session-empty">暂无历史会话<br>点击上方「新建对话」开始</div>';
    return;
  }
  container.innerHTML = convs.map(c => {
    // 未加载过消息的历史会话用后端给的条数，别一律显示 0
    const n = (c.messages || []).length || c.messageCount || 0;
    return `
    <div class="session-item ${c.id === activeConvId ? 'active' : ''}"
         onclick="switchConversation('${c.id}')" title="${escapeAttr(c.title)}">
      <svg class="session-item-icon" width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 4.5A1.5 1.5 0 0 1 3.5 3h9A1.5 1.5 0 0 1 14 4.5v5A1.5 1.5 0 0 1 12.5 11H6l-3 2.5V11h-.5A1.5 1.5 0 0 1 2 9.5z"/></svg>
      <span class="session-item-name">${escapeHtml(c.title)}</span>
      <span class="session-item-count">${n}</span>
      <button class="session-item-del" onclick="deleteConversation('${c.id}', event)" title="删除会话">
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>
      </button>
    </div>`;
  }).join('');
}

