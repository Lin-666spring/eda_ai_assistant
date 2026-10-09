// ═══════════════════════════════════════════
//  Assistant Management —— P1-6 阶段C 自 app.js 拆出（原 374-817 行）
//  助手实例渲染与菜单 / 工作区选择 / Agent 模式 / 窗口模式 / 新建助手对话框
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ Assistant Management ═══════════

function getActiveAssistant() {
  const inst = assistantInstances.find(i => i.instanceId === currentAssistantInstance);
  if (!inst) return null;
  const type = ASSISTANT_TYPES[inst.typeId];
  return { ...type, instanceId: inst.instanceId, name: inst.name };
}

function renderAssistants() {
  renderAssistantMenu();
  const container = document.getElementById('configAssistantList');
  const countEl = document.getElementById('configAssistantCount');
  if (countEl) countEl.textContent = `${assistantInstances.length} 个`;
  if (!container) return;  // only render when the config sub-page is open
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

/** 侧边栏底部的助手选择菜单 */
function renderAssistantMenu() {
  const box = document.getElementById('assistantList');
  const nameEl = document.getElementById('assistantChipName');
  const active = getActiveAssistant();
  if (nameEl) nameEl.textContent = active ? active.name : '未创建助手';
  if (!box) return;
  if (assistantInstances.length === 0) {
    box.innerHTML = '<div class="session-empty">暂无助手实例</div>';
    return;
  }
  box.innerHTML = assistantInstances.map(inst => {
    const type = ASSISTANT_TYPES[inst.typeId] || {};
    const isActive = inst.instanceId === currentAssistantInstance;
    return `<div class="sb-asst-item ${isActive ? 'active' : ''}"
        onclick="selectAssistant('${inst.instanceId}'); closeAssistantMenu();"
        title="${escapeAttr(type.description || '')}">
      <span class="sb-asst-item-name">${escapeHtml(inst.name)}</span>
      <span class="sb-asst-item-count">${(getWorkspaceConversations(inst.instanceId) || []).length}</span>
    </div>`;
  }).join('');
}

function toggleAssistantMenu(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const menu = document.getElementById('assistantMenu');
  if (!menu) return;
  const willOpen = !menu.classList.contains('show');
  closeWorkspaceMenu();
  menu.classList.toggle('show', willOpen);
  if (willOpen) renderAssistantMenu();
}

function closeAssistantMenu() {
  const menu = document.getElementById('assistantMenu');
  if (menu) menu.classList.remove('show');
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
  const convs = getWorkspaceConversations(instanceId);
  if (convs.length > 0) {
    switchConversation(convs[0].id);
  } else {
    activeConvId = null;
    clearChatMessages();
    closeSubPage();
    showEmptyState(true);
    _persistState();
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
          closeSubPage();
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
  // 侧边栏底部显示当前助手；对话本身在左侧列表中高亮，不再有独立的会话下拉。
  const a = getActiveAssistant();
  const nameEl = document.getElementById('assistantChipName');
  if (nameEl) nameEl.textContent = a ? a.name : '未创建助手';
  const wsEl = document.getElementById('workspaceChipName');
  const ws = workspaces.find(w => w.id === currentWorkspaceId);
  if (wsEl) wsEl.textContent = ws ? ws.name : '默认工作区';
}

// 兼容旧调用点
function updateChatHeader() { updateSessionBar(); }

// ── 工作区选择（左侧栏顶部，conversations 按工作区隔离） ──

let _editingWorkspaceId = null;

function toggleWorkspaceMenu(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const menu = document.getElementById('workspaceMenu');
  if (!menu) return;
  const willOpen = !menu.classList.contains('show');
  closeAssistantMenu();
  menu.classList.toggle('show', willOpen);
  if (willOpen) renderWorkspaces();
}

function closeWorkspaceMenu() {
  const menu = document.getElementById('workspaceMenu');
  if (menu) menu.classList.remove('show');
}

function renderWorkspaces() {
  const box = document.getElementById('workspaceList');
  const nameEl = document.getElementById('workspaceChipName');
  const cur = workspaces.find(w => w.id === currentWorkspaceId);
  if (nameEl) nameEl.textContent = cur ? cur.name : '默认工作区';
  if (!box) return;
  box.innerHTML = workspaces.map(w => {
    const n = Object.values(conversations).flat()
      .filter(c => (c.workspaceId || DEFAULT_WORKSPACE_ID) === w.id).length;
    const isDefault = w.id === DEFAULT_WORKSPACE_ID;
    return `<div class="sb-ws-item ${w.id === currentWorkspaceId ? 'active' : ''}"
        onclick="selectWorkspace('${w.id}')" title="${escapeAttr(w.path || w.name)}">
      <span class="sb-ws-item-main">
        <span class="sb-ws-item-name">${escapeHtml(w.name)}</span>
        <span class="sb-ws-item-path">${escapeHtml(w.path || '未绑定目录')}</span>
      </span>
      <span class="sb-ws-item-count">${n}</span>
      <button class="sb-ws-item-edit" onclick="openWorkspaceDialog(event, '${w.id}')" title="编辑">
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M11 2.5l2.5 2.5L5 13.5 2 14l.5-3z"/></svg>
      </button>
      ${isDefault ? '' : `<button class="sb-ws-item-del" onclick="deleteWorkspace('${w.id}', event)" title="删除">
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="3" y1="3" x2="13" y2="13"/><line x1="13" y1="3" x2="3" y2="13"/></svg>
      </button>`}
    </div>`;
  }).join('');
}

function selectWorkspace(wsId) {
  const ws = workspaces.find(w => w.id === wsId);
  if (!ws) return;
  closeWorkspaceMenu();
  if (wsId === currentWorkspaceId) return;
  currentWorkspaceId = wsId;
  _persistActiveWorkspace(wsId);
  renderWorkspaces();
  renderConversations();
  renderAssistantMenu();
  const convs = getWorkspaceConversations();
  if (convs.length > 0) {
    switchConversation(convs[0].id);
  } else {
    activeConvId = null;
    clearChatMessages();
    closeSubPage();
    showEmptyState(true);
    _persistState();
  }
  showToast(`已切换到工作区「${ws.name}」`, 'info');
}

function openWorkspaceDialog(e, editId) {
  if (e && e.stopPropagation) e.stopPropagation();
  closeWorkspaceMenu();
  _editingWorkspaceId = editId || null;
  const title = document.getElementById('workspaceDialogTitle');
  const nameInput = document.getElementById('wsNameInput');
  const pathInput = document.getElementById('wsPathInput');
  const err = document.getElementById('wsDialogError');
  if (err) { err.style.display = 'none'; err.textContent = ''; }
  const ws = editId ? workspaces.find(w => w.id === editId) : null;
  if (title) title.textContent = ws ? '编辑工作区' : '新建工作区';
  if (nameInput) nameInput.value = ws ? ws.name : '';
  if (pathInput) pathInput.value = ws ? ws.path : '';
  const overlay = document.getElementById('workspaceOverlay');
  if (overlay) overlay.classList.add('show');
  if (nameInput) setTimeout(() => nameInput.focus(), 30);
}

function closeWorkspaceDialog() {
  const overlay = document.getElementById('workspaceOverlay');
  if (overlay) overlay.classList.remove('show');
  _editingWorkspaceId = null;
}

async function saveWorkspaceFromDialog() {
  const nameInput = document.getElementById('wsNameInput');
  const pathInput = document.getElementById('wsPathInput');
  const err = document.getElementById('wsDialogError');
  const name = (nameInput.value || '').trim();
  let path = (pathInput.value || '').trim();
  const fail = (msg) => { if (err) { err.textContent = msg; err.style.display = ''; } };
  if (!name) { fail('请填写工作区名称'); return; }
  if (err) { err.style.display = 'none'; }
  if (path) {
    // 让后端确认目录可用（不存在则创建），避免存下一个假路径
    try {
      const resp = await eel.create_workspace_dir(path)();
      if (resp && resp.ok) path = resp.path;
      else { fail('目录不可用：' + ((resp && resp.error) || path)); return; }
    } catch (e) { fail('目录校验失败：' + e); return; }
  }
  if (_editingWorkspaceId) {
    const ws = workspaces.find(w => w.id === _editingWorkspaceId);
    if (ws) { ws.name = name; ws.path = path; _persistWorkspace(ws); }
    closeWorkspaceDialog();
    renderWorkspaces();
    showToast('工作区已更新', 'success');
    return;
  }
  const ws = { id: 'ws_' + Date.now().toString(36), name, path };
  workspaces.push(ws);
  _persistWorkspace(ws);
  closeWorkspaceDialog();
  currentWorkspaceId = ws.id;
  _persistActiveWorkspace(ws.id);
  activeConvId = null;
  clearChatMessages();
  closeSubPage();
  showEmptyState(true);
  renderWorkspaces();
  renderConversations();
  _persistState();
  showToast(`已创建工作区「${name}」`, 'success');
}

async function browseWorkspaceDir() {
  const pathInput = document.getElementById('wsPathInput');
  const err = document.getElementById('wsDialogError');
  const btn = _btnFromEvent();
  _btnLoading(btn, '选择中');
  setStatus('等待选择目录…');
  try {
    const resp = await eel.pick_workspace_dir()();
    if (resp && resp.ok && resp.path) {
      pathInput.value = resp.path;
      if (err) err.style.display = 'none';
    } else if (resp && !resp.cancelled && err) {
      err.textContent = resp.error || '未选择目录';
      err.style.display = '';
    }
  } catch (e) {
    if (err) { err.textContent = '无法打开目录选择器，请手动输入路径'; err.style.display = ''; }
  }
  _btnLoaded(btn);
  setStatus('就绪');
}

async function openWorkspacePath() {
  const pathInput = document.getElementById('wsPathInput');
  const cur = workspaces.find(w => w.id === currentWorkspaceId) || {};
  const p = (pathInput && pathInput.value.trim()) || cur.path || '';
  if (!p) { showToast('该工作区未绑定目录', 'warning'); return; }
  try {
    const resp = await eel.open_workspace_dir(p)();
    if (resp && !resp.ok) showToast(resp.error || '无法打开目录', 'warning');
  } catch (e) {}
}

function deleteWorkspace(wsId, event) {
  if (event) event.stopPropagation();
  const ws = workspaces.find(w => w.id === wsId);
  if (!ws) return;
  showConfirmDialog({
    title: '删除工作区',
    message: `确定要删除工作区「${ws.name}」吗？\n其中的对话会移动到默认工作区，不会丢失。`,
    okText: '删除',
    onOk: () => {
      _persistDeleteWorkspace(wsId);
      workspaces = workspaces.filter(w => w.id !== wsId);
      // 前端同步迁移，和后端行为保持一致
      Object.values(conversations).forEach(list => list.forEach(c => {
        if ((c.workspaceId || DEFAULT_WORKSPACE_ID) === wsId) c.workspaceId = DEFAULT_WORKSPACE_ID;
      }));
      if (currentWorkspaceId === wsId) {
        currentWorkspaceId = DEFAULT_WORKSPACE_ID;
        _persistActiveWorkspace(DEFAULT_WORKSPACE_ID);
      }
      _persistState();
      renderWorkspaces();
      renderConversations();
      renderAssistantMenu();
      showToast('工作区已删除，对话已迁移到默认工作区', 'info');
    },
  });
}

document.addEventListener('click', (e) => {
  const wsWrap = document.getElementById('workspaceWrap');
  if (wsWrap && !wsWrap.contains(e.target)) closeWorkspaceMenu();
  const aWrap = document.getElementById('assistantWrap');
  if (aWrap && !aWrap.contains(e.target)) closeAssistantMenu();
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
  // 新助手没有对话 → 直接开一个，用户马上能说话
  newConversation();
}

