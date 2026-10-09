// ═══════════════════════════════════════════
//  Persistence —— P1-6 阶段C 自 app.js 拆出（原 232-373 行）
//  _persist* fire-and-forget 持久化（SQLite via main.py 的 db_* 端点）
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ Persistence ═══════════

async function loadPersistedState() {
  let resp;
  try { resp = await eel.db_load_all()(); } catch(e) { return; }
  if (!resp || !resp.ok || !resp.data) return;

  const { workspaces: savedWs, assistants: saved, conversations: savedConvs,
          active_workspace, active_assistant, active_conv } = resp.data;

  // 工作区：后端首跑会写入默认工作区；这里再兜底一次，保证至少有得选。
  workspaces = (savedWs || []).map(w => ({
    id: w.workspace_id,
    name: w.name || '工作区',
    path: w.path || '',
  }));
  if (!workspaces.length) {
    workspaces = [{ id: DEFAULT_WORKSPACE_ID, name: '默认工作区', path: '' }];
  }
  currentWorkspaceId = workspaces.some(w => w.id === active_workspace)
    ? active_workspace
    : workspaces[0].id;

  // 无持久化数据 → 自动创建默认助手实例（首跑引导）
  if (!saved || saved.length === 0) {
    // 注意：typeId 必须是 ASSISTANT_TYPES 里真实存在的键。
    //    过去写的是 'general'（不存在）→ createAssistantInstance 返回 null
    //    → 紧接着读 inst.instanceId 直接抛异常，首跑白屏（2026-09-10 修正）。
    const inst = createAssistantInstance('eda-general');
    if (inst) currentAssistantInstance = inst.instanceId;
    conversations[currentAssistantInstance] = conversations[currentAssistantInstance] || [];
    updateSessionBar();
    renderQuickActions();   // 首跑也要有快捷操作按钮（过去只有切助手后才渲染）
    renderWorkspaces();
    _persistState();
    // 首跑落地页就是对话页（不再自动切到 BOM 视图）
    closeSubPage();
    return;
  }

  // 恢复助手实例
  assistantInstances = saved.map(a => ({
    instanceId: a.instance_id,
    typeId: a.type_id,
    name: a.name,
  }));
  // 注意：归一化：SessionStore.load_all() 返回的会话记录字段是
  //    {conv_id, workspace_id, title, sort_order}（没有 id / messages），
  //    直接用会导致 switchConversation() 里 `conv.messages.length` 抛 undefined。
  conversations = {};
  saved.forEach(a => {
    conversations[a.instance_id] = (savedConvs[a.instance_id] || []).map(c => ({
      id: c.id || c.conv_id,
      title: c.title || '新对话',
      workspaceId: c.workspace_id || DEFAULT_WORKSPACE_ID,
      messages: [],
      // load_all 不带消息正文，但带条数：列表徽标不用再对历史会话恒显 0
      messageCount: c.message_count || 0,
      _loaded: false,
    }));
  });

  // 恢复活跃状态
  if (active_assistant && assistantInstances.find(i => i.instanceId === active_assistant)) {
    currentAssistantInstance = active_assistant;
  } else {
    currentAssistantInstance = assistantInstances[0].instanceId;
  }

  updateChatHeader();
  renderQuickActions();
  renderWorkspaces();
  renderAssistantMenu();

  // 恢复当前工作区里最近的对话
  const convs = getWorkspaceConversations();
  if (active_conv && convs.find(c => c.id === active_conv)) {
    await switchConversation(active_conv);
  } else if (convs.length > 0) {
    await switchConversation(convs[0].id);
  } else {
    activeConvId = null;
    clearChatMessages();
    closeSubPage();
    showEmptyState(true);
  }
}

/** 当前助手 + 当前工作区下的会话列表 */
function getWorkspaceConversations(instanceId) {
  const iid = instanceId || currentAssistantInstance;
  const all = conversations[iid] || [];
  return all.filter(c => (c.workspaceId || DEFAULT_WORKSPACE_ID) === currentWorkspaceId);
}

// ── Fire-and-forget persistence helpers ──

function _persistAssistant(inst) {
  try { eel.db_save_assistant(inst.instanceId, inst.typeId, inst.name)(); } catch(e) {}
}

function _persistDeleteAssistant(instanceId) {
  try { eel.db_delete_assistant(instanceId)(); } catch(e) {}
}

function _persistConversation(conv) {
  const inst = assistantInstances.find(i => i.instanceId === currentAssistantInstance);
  if (!inst) return;
  const ws = conv.workspaceId || currentWorkspaceId || DEFAULT_WORKSPACE_ID;
  try { eel.db_save_conversation(conv.id, inst.instanceId, conv.title, ws)(); } catch(e) {}
}

function _persistDeleteConversation(convId) {
  try { eel.db_delete_conversation(convId)(); } catch(e) {}
}

function _persistMessage(convId, role, content, image) {
  try { eel.db_save_message(convId, role, content, image || '')(); } catch(e) {}
}

function _persistState() {
  try { eel.db_save_active_state(
    currentAssistantInstance || '',
    activeConvId || '',
    currentWorkspaceId || ''
  )(); } catch(e) {}
}

// ── 工作区持久化（fire-and-forget，与其它 _persist* 一致）──

function _persistWorkspace(ws) {
  try { eel.db_save_workspace(ws.id, ws.name, ws.path || '')(); } catch(e) {}
}

function _persistDeleteWorkspace(wsId) {
  try { eel.db_delete_workspace(wsId)(); } catch(e) {}
}

function _persistActiveWorkspace(wsId) {
  try { eel.db_set_active_workspace(wsId)(); } catch(e) {}
}

