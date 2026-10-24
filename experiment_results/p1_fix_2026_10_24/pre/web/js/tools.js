// ═══════════════════════════════════════════
//  Tools & Views —— P1-6 阶段C 自 app.js 拆出（原 964-1585 行）
//  统一工具目录（TOOL_CATALOG）/ 两级视图 VIEWS + ICONS / 工具箱 / 工具启动 / 演示入口
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ Chat ═══════════

function clearChatMessages() {
  // Abort any in-progress stream
  _activeStreamBubble = null;
  _streamTokenCount = 0;
  _activeToolCards.forEach(c => c.remove());
  _activeToolCards = [];
  const container = document.getElementById('chatMessages');
  if (!container) return;
  // 注意：只能保留空态相关节点（占位 #chatEmpty + 空态粒子画布
  // #chatEmptyParticles，见 js/particles.js），其余一律清掉。
  // 过去只删 `.msg-row,.config-tip`，而流式 AI 气泡（裸 .bubble）和
  // `.tool-call-card` 都不带 .msg-row，切换助手/会话后它们会留在 DOM 里，
  // 造成「同一个回答显示两遍」（2026-09-10 实测：bareBubbles 存活 1 个）。
  Array.from(container.children).forEach(el => {
    if (el.id !== 'chatEmpty' && el.id !== 'chatEmptyParticles') el.remove();
  });
  _syncChatEmpty();
}

// ═══════════ Chat empty-state sync ═══════════
function _syncChatEmpty() {
  const cm = document.getElementById('chatMessages');
  const ce = document.getElementById('chatEmpty');
  if (!cm || !ce) return;
  ce.style.display = cm.querySelectorAll('.msg-row').length ? 'none' : '';
}
(function() {
  const cm = document.getElementById('chatMessages');
  if (cm) new MutationObserver(_syncChatEmpty).observe(cm, { childList: true, subtree: true });
})();

// ═══════════ 统一工具目录 (ToolRegistry 是唯一事实来源) ═══════════
//
// 前端不再复制工具的名称/描述/关键词：全部来自 eel.get_tools_catalog()，
// 也就是 src/agent/tools.py 的 ToolRegistry。视图只声明「展示哪些工具」，
// 卡片样式、状态徽标、运行入口全部统一。

const TOOL_CATEGORIES = {
  bom:    { label: 'BOM 物料', short: 'BOM',   tone: 'blue' },
  pcb:    { label: 'PCB 设计', short: 'PCB',   tone: 'violet' },
  health: { label: '供应链健康', short: '供应链', tone: 'green' },
  report: { label: '报告导出', short: '报告',   tone: 'amber' },
  vision: { label: '视觉分析', short: '视觉',   tone: 'pink' },
};

// tool name → ICONS 中的语义键（统一走同一套线性 SVG 图标）
const TOOL_ICONS = {
  ai_merge_bom: 'robot', merge_bom: 'link', validate_package: 'ruler',
  check_duplicates: 'search', filter_components: 'magnet',
  generate_html_bom: 'globe', export_bom_csv: 'upload', summary_report: 'chart',
  bom_cost_summary: 'coins', bom_health: 'pulse', find_alternatives: 'swap', supply_risk: 'truck',
  check_rule: 'ruler', pcb_status: 'monitor', pcb_analysis: 'puzzle', calc_trace_width: 'ruler-diag',
  explain_design_rule: 'book', generate_drc_rule: 'receipt', review_multi_agent: 'users',
  verify_suggestion: 'check-circle', component_lookup: 'search-plus', search_component: 'search',
  analyze_image: 'image', rag_query: 'book-open',
};

// 少数能力的启动方式不是「直接执行」
const TOOL_LAUNCH = {
  review_multi_agent: { kind: 'run', run: () => featureCmd('__review') },
  generate_html_bom:  { kind: 'run', run: () => generateHTMLBOM() },
  analyze_image:      { kind: 'image' },
  rag_query:          { kind: 'prompt', prefix: '查询知识库: ' },
};

let TOOL_CATALOG = [];
let _toolQuery = '';
let _toolCategory = 'all';
let _toolOnlyReady = false;

async function loadToolCatalog(force) {
  if (TOOL_CATALOG.length && !force) return TOOL_CATALOG;
  try {
    const resp = await eel.get_tools_catalog()();
    TOOL_CATALOG = (resp && resp.ok && resp.tools) ? resp.tools : [];
  } catch (e) {
    console.warn('工具目录加载失败', e);
    TOOL_CATALOG = [];
  }
  return TOOL_CATALOG;
}

function getTool(name) {
  return TOOL_CATALOG.find(t => t.name === name) || null;
}

/** 数据可用性变了（导入 BOM / PCB / 坐标、一键演示）后刷新工具目录。
 *  可用性是后端按「当前有没有 BOM」实时算的，不刷新的话工具箱里的
 *  「需先导入 BOM」徽标会一直停在旧状态。 */
async function refreshToolCatalog() {
  await loadToolCatalog(true);
  const vc = document.getElementById('viewContainer');
  const sub = document.getElementById('subPage');
  const view = VIEWS[_currentView];
  // 只在子页面打开时就地重绘；对话为主时不要把用户拽回子页面
  if (vc && sub && view && !sub.classList.contains('hidden')) {
    const keepScroll = vc.scrollTop;
    vc.innerHTML = renderViewHTML(view);
    if (view.hub) renderToolGrid();
    if (view.assistantSection) renderAssistants();
    vc.scrollTop = keepScroll;
  }
  return TOOL_CATALOG;
}

function _toolState(t) {
  // 顺序很重要：先把「没数据跑不了」判掉，否则像 generate_html_bom /
  // review_multi_agent 这种走面板的能力会显示「面板直达」，掩盖了它还缺 BOM。
  if (!t.ready) return { key: 'blocked', text: t.blocked_reason || '不可用' };
  const spec = TOOL_LAUNCH[t.name];
  if (spec && spec.kind === 'run') return { key: 'panel', text: '面板直达' };
  if (spec && spec.kind === 'image') return { key: 'input', text: '需上传图片' };
  if (t.needs_input) return { key: 'input', text: '需补参数' };
  return { key: 'ready', text: '可直接运行' };
}

/** 统一工具卡片 — 工具箱与各视图共用同一个组件 */
function renderToolCard(t, index) {
  const cat = TOOL_CATEGORIES[t.category] || { short: t.category, tone: 'blue' };
  const st = _toolState(t);
  const icon = ICONS[TOOL_ICONS[t.name]] || ICONS['settings'] || '';
  return `<article class="tool-card" data-tool="${t.name}" data-cat="${t.category}" data-state="${st.key}"
      style="--i:${index || 0}" onclick="launchTool('${t.name}')" title="${escapeAttr(t.description)}">
    <div class="tool-card-top">
      <span class="tool-card-icon">${icon}</span>
      <span class="tool-card-cat tone-${cat.tone}">${cat.short}</span>
    </div>
    <div class="tool-card-label">${escapeHtml(t.label)}</div>
    <p class="tool-card-desc">${escapeHtml(t.description)}</p>
    <div class="tool-card-foot">
      <span class="tool-card-state ${st.key}"><i class="state-dot"></i>${escapeHtml(st.text)}</span>
      <span class="tool-card-go">运行<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,3 11,8 6,13"/></svg></span>
    </div>
  </article>`;
}

/** 非工具类快捷入口也用同一种卡片外观，保持视觉统一 */
function renderActionCard(item, index) {
  const icon = ICONS[item.icon] || item.icon || ICONS['settings'];
  return `<article class="tool-card tool-card--action" style="--i:${index || 0}"
      onclick="${item.onClick}" title="${escapeAttr(item.desc || item.title)}">
    <div class="tool-card-top">
      <span class="tool-card-icon">${icon}</span>
      <span class="tool-card-cat tone-slate">快捷</span>
    </div>
    <div class="tool-card-label">${escapeHtml(item.title)}</div>
    <p class="tool-card-desc">${escapeHtml(item.desc || '')}</p>
    <div class="tool-card-foot">
      <span class="tool-card-state action"><i class="state-dot"></i>${escapeHtml(item.hint || '打开')}</span>
      <span class="tool-card-go">前往<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6,3 11,8 6,13"/></svg></span>
    </div>
  </article>`;
}

function renderToolCards(names) {
  return (names || [])
    .map((n, i) => { const t = getTool(n); return t ? renderToolCard(t, i) : ''; })
    .filter(Boolean)
    .join('');
}

// ═══════════ Two-level Views (阶梯式导航) ═══════════

const VIEWS = {
  bom: {
    title: 'BOM 分析',
    subtitle: '物料清单的导入、校验、合并与供应链健康检查 — 确保每一颗元件可用、对、省。',
    metrics: [
      { num: '24', label: '系统能力', icon: 'puzzle' },
      { num: '71', label: '设计规则' },
      { num: '3', label: '自研 ML 模型' },
      { num: '98%', label: '缺陷检出率' },
    ],
    actions: [
      { label: '一键演示', sub: '加载示例缺陷 MCU 板', primary: true, onClick: 'startDemo()' },
      { label: '导入 BOM 文件', sub: 'CSV / Excel', primary: false, onClick: "document.getElementById('bomFileInput').click()" },
    ],
    tools: ['merge_bom', 'ai_merge_bom', 'validate_package', 'check_duplicates', 'filter_components', 'bom_health'],
  },
  review: {
    title: '设计审查',
    subtitle: '71 条 PCB 设计规则全量扫描 · 多智能体协同评审 · 违规密度可视化定位。',
    metrics: [
      { num: '71', label: 'DRC 规则', icon: 'ruler' },
      { num: '5', label: '审查 Agent', icon: 'users' },
      { num: '18s', label: '平均耗时', icon: 'eye' },
      { num: 'V2.8', label: '模型版本', icon: 'settings' },
    ],
    actions: [
      { label: '启动多智能体审查', sub: '5 个专业 Agent 并行评审', primary: true, onClick: "featureCmd('__review')" },
      { label: '加载 DRC 热力图', sub: '违规密度可视化', primary: false, onClick: "featureCmd('__heatmap')" },
    ],
    tools: ['check_rule', 'pcb_analysis', 'review_multi_agent', 'verify_suggestion', 'pcb_status', 'explain_design_rule'],
    extras: [
      { icon: 'flame', title: 'DRC 热力图', desc: '违规密度的空间分布定位', onClick: "featureCmd('__heatmap')", hint: '右侧面板' },
      { icon: 'download', title: '导入 PCB', desc: '.json / .epro 电路板文件', onClick: "document.getElementById('pcbFileInput').click()", hint: '选择文件' },
    ],
  },
  tools: {
    hub: true,
    title: '工具箱',
    subtitle: '全部系统能力集中于此 — 搜索、按类别筛选、一键运行。目录由后端 ToolRegistry 派生，与实际可执行能力永远一致。',
  },
  report: {
    title: '报告中心',
    subtitle: '生成交互式 HTML BOM · 查看历史报告栈 · 导出审查结果。',
    metrics: [
      { num: 'HTML', label: '报告格式', icon: 'file-text' },
      { num: 'CSV', label: '数据导出', icon: 'upload' },
      { num: '历史', label: '报告栈', icon: 'book-open' },
      { num: '一键', label: '生成', icon: 'check-circle' },
    ],
    actions: [
      { label: '生成 HTML BOM', sub: '交互式物料表', primary: true, onClick: "generateHTMLBOM()" },
      { label: '打开任务面板', sub: '查看报告与审查结果', primary: false, onClick: "toggleRightPanel()" },
    ],
    tools: ['generate_html_bom', 'export_bom_csv', 'summary_report', 'bom_cost_summary'],
    extras: [
      { icon: 'file-text', title: '报告栈', desc: '操作历史报告归档', onClick: "switchTab('report'); toggleRightPanel()", hint: '右侧面板' },
      { icon: 'chart', title: '审查结果', desc: '多智能体评审卡片', onClick: "switchTab('review'); toggleRightPanel()", hint: '右侧面板' },
      { icon: 'receipt', title: 'BOM 表格', desc: '当前物料明细', onClick: "switchTab('bom'); toggleRightPanel()", hint: '右侧面板' },
      { icon: 'eye', title: 'HTML 预览', desc: '生成的 BOM 预览', onClick: "switchTab('html'); toggleRightPanel()", hint: '右侧面板' },
    ],
  },
  config: {
    title: '配置管理',
    subtitle: 'AI 模型 · 外观主题 · 通用设置 · 助手实例管理 — 一切可调项集中于此。',
    metrics: [
      { num: '5+', label: 'LLM 服务商', icon: 'robot' },
      { num: '4', label: '助手类型', icon: 'cpu' },
      { num: '本地', label: 'ML 离线', icon: 'package' },
      { num: 'SQLite', label: '持久化', icon: 'database' },
    ],
    actions: [
      { label: 'AI 模型配置', sub: 'API Key · 模型 · 温度', primary: true, onClick: "openSettingsAt('s-ai')" },
      { label: '新建助手', sub: '多实例助手模型', primary: false, onClick: "showNewAssistantDialog()" },
    ],
    extras: [
      { icon: 'robot', title: 'AI 模型', desc: '服务商 · API Key · 模型 · 温度', onClick: "openSettingsAt('s-ai')", hint: '设置' },
      { icon: 'palette', title: '外观主题', desc: '深浅色 · 强调色 · 字号', onClick: "openSettingsAt('s-appearance')", hint: '设置' },
      { icon: 'settings', title: '通用设置', desc: '自动保存 · 文件监听 · 操作确认', onClick: "openSettingsAt('s-general')", hint: '设置' },
      { icon: 'database', title: '数据存储', desc: '数据目录与清除本地数据', onClick: "openSettingsAt('s-general')", hint: '设置' },
      { icon: 'folder', title: '导入 PCB', desc: '.json / .epro 电路板文件', onClick: "document.getElementById('pcbFileInput').click()", hint: '选择文件' },
      { icon: 'map-pin', title: '导入坐标', desc: '.csv 元件坐标文件', onClick: "document.getElementById('posFileInput').click()", hint: '选择文件' },
    ],
    assistantSection: true,
  },
};

// ═══════════ SVG 图标映射（Lucide 风格线性图标） ═══════════
// 键是语义名，不再用 emoji 当键：源码里不出现 emoji 字符，
// 名字也说得清是什么图标。新增图标请沿用 kebab-case 语义名。
const ICONS = {
  'pulse':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12h3l3-8 4 16 3-8h6"/></svg>',
  'ruler':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h12L4 16z"/></svg>',
  'search':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/></svg>',
  'link':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M9 15l6-6M10 6l1.5-1.5a3.5 3.5 0 0 1 5 5L15 11M14 18l-1.5 1.5a3.5 3.5 0 0 1-5-5L9 13"/></svg>',
  'robot':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V5M9 5h6"/><path d="M9 13v1M15 13v1"/></svg>',
  'clipboard':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4a3 3 0 0 1 6 0"/><path d="M9 11h6M9 15h6"/></svg>',
  'route':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19a2 2 0 1 0 0-8h8a2 2 0 1 1 0 8M4 11V7a2 2 0 0 1 2-2h2"/></svg>',
  'monitor':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
  'flame':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2c2 4-1 5 0 8a2.5 2.5 0 0 0 5 0c0-3-2-4-2-4 3 2 5 6 4 9a6 6 0 1 1-12 0c0-5 3-7 5-13"/></svg>',
  'users':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="8" r="3.5"/><path d="M3 19a6 6 0 0 1 12 0M16 5a3.5 3.5 0 0 1 0 6M14 13a5.5 5.5 0 0 1 6 6"/></svg>',
  'check-circle':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>',
  'globe':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a13 13 0 0 1 0 18M12 3a13 13 0 0 0 0 18"/></svg>',
  'file-text':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6M9 16h4"/></svg>',
  'chart':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 20h16M7 20V11M12 20V6M17 20v-5"/></svg>',
  'map':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 6l8-3 5 3-6 3-7-3zM8 6v12m8-12v12M8 18l-5 3V9l5-3m8 12l5-3"/></svg>',
  'receipt':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 3h14v18l-2.3-1.6L14.4 21l-2.4-1.6L9.6 21l-2.3-1.7L5 21z"/><path d="M9 8h6M9 12h6"/></svg>',
  'eye':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"/><circle cx="12" cy="12" r="2.5"/></svg>',
  'palette':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22a10 10 0 1 1 10-10c0 2.5-1.8 3-4 3.5a2.5 2.5 0 0 0-2.5 2.5c0 2 1.2 2.5 1.2 4"/><path d="M7 10.5h.01M11 7h.01M15 8.5h.01"/></svg>',
  'settings':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>',
  'database':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></svg>',
  'cpu':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 5V2M12 5V2M15 5V2M9 22v-3M12 22v-3M15 22v-3M5 9H2M5 12H2M5 15H2M22 9h-3M22 12h-3M22 15h-3"/></svg>',
  'folder':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  // ── 工具目录补充图标 ──
  'package':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/></svg>',
  'puzzle':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M10 3h4v4a2 2 0 1 0 4 0h3v4h-3a2 2 0 1 0 0 4h3v4h-4a2 2 0 1 0-4 0H9v-4a2 2 0 1 0-4 0H2v-4h3a2 2 0 1 0 0-4H2V5h4a2 2 0 0 1 4-2z"/></svg>',
  'magnet':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3v8a6 6 0 0 0 12 0V3"/><path d="M6 8h4M14 8h4"/></svg>',
  'upload':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="M12 15V3M8 7l4-4 4 4"/></svg>',
  'coins':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 4h12M6 9h12M12 4v16M8 13c4 0 8 1 8 4"/></svg>',
  'swap':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 10a6 6 0 0 1 10-4l3 3M20 14a6 6 0 0 1-10 4l-3-3"/><path d="M17 3v6h-6M7 21v-6h6"/></svg>',
  'truck':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="6" width="12" height="10" rx="1"/><path d="M14 9h4l3 3v4h-7z"/><circle cx="6" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/></svg>',
  'ruler-diag':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 15L15 3l6 6L9 21z"/><path d="M7 11l2 2M10 8l2 2M13 5l2 2"/></svg>',
  'book':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4h6a3 3 0 0 1 3 3v13a2.5 2.5 0 0 0-2.5-2.5H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a2.5 2.5 0 0 1 2.5-2.5H20z"/></svg>',
  'search-plus':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21M8 11h6"/></svg>',
  'image':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.5"/><path d="M4 18l5-5 3 3 3-4 5 6"/></svg>',
  'book-open':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 5a2 2 0 0 1 2-2h5v18H6a2 2 0 0 0-2 2z"/><path d="M20 5a2 2 0 0 0-2-2h-5v18h5a2 2 0 0 1 2 2z"/></svg>',
  'download':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/><path d="M12 3v12M8 11l4 4 4-4"/></svg>',
  'map-pin':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 22s7-7 7-12a7 7 0 1 0-14 0c0 5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  'wrench':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14.7 6.3a4 4 0 0 1 5 5L11 20H4v-7z"/><path d="M12 9l3 3"/></svg>',
};
// KPI 指标图标（按 label 关键词匹配）
function _metricIcon(label) {
  if (/规则/.test(label)) return 'ruler';
  if (/ML/.test(label)) return 'cpu';
  if (/检出/.test(label)) return 'check-circle';
  if (/Agent/.test(label)) return 'users';
  if (/耗时/.test(label)) return 'eye';
  if (/版本/.test(label)) return 'settings';
  if (/格式/.test(label)) return 'file-text';
  return 'chart';
}

let _currentView = 'bom';

async function switchView(viewId) {
  _currentView = viewId;
  const view = VIEWS[viewId];
  if (!view) return;
  // 视图里要用工具目录渲染统一卡片 → 首次进入前先拉目录
  if (!TOOL_CATALOG.length) await loadToolCatalog();
  if (_currentView !== viewId) return;   // 期间用户又切了视图
  // Top mode bar active state
  document.querySelectorAll('.nav-item').forEach(n => {
    n.classList.toggle('active', n.dataset.view === viewId);
  });
  // 打开功能子页面：聊天流让位给该模式的工具卡片
  const sub = document.getElementById('subPage');
  const cm = document.getElementById('chatMessages');
  if (sub) sub.classList.remove('hidden');
  if (cm) cm.classList.add('hidden');
  const crumb = document.getElementById('subpageCrumb');
  if (crumb) crumb.textContent = view.title;
  const vc = document.getElementById('viewContainer');
  vc.classList.remove('hidden');
  vc.innerHTML = renderViewHTML(view);
  vc.scrollTop = 0;
  if (view.hub) renderToolGrid();
  // Re-render assistants list if entering config sub-page
  if (viewId === 'config') {
    setTimeout(() => { renderAssistants(); }, 0);
  }
}

/** 关闭功能子页面，回到对话主页面 */
function closeSubPage() {
  const sub = document.getElementById('subPage');
  const cm = document.getElementById('chatMessages');
  if (sub) sub.classList.add('hidden');
  if (cm) cm.classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  _syncChatEmpty();
}

function renderMetrics(metrics) {
  return (metrics || []).map(m =>
    `<div class="kpi-card">
       <div class="kpi-icon">${ICONS[m.icon || _metricIcon(m.label)] || ''}</div>
       <div class="kpi-body">
         <div class="kpi-num">${m.num}</div>
         <div class="kpi-label">${m.label}</div>
       </div>
     </div>`
  ).join('');
}

function renderViewHTML(view) {
  const actions = (view.actions || []).map(a =>
    `<button class="${a.primary ? 'btn-primary' : 'btn-secondary'}" onclick="${a.onClick}">
       <span class="view-action-label">${a.label}</span>
       <span class="view-action-sub">${a.sub || ''}</span>
     </button>`
  ).join('');

  const grid = view.hub
    ? renderToolHub()
    : `<div class="tool-grid">${renderToolCards(view.tools)}${(view.extras || []).map(renderActionCard).join('')}</div>`;

  // Config view gets an extra inline assistants section
  const assistantSection = view.assistantSection ? `
    <div class="config-section">
      <div class="config-section-head">
        <span class="config-section-icon">${ICONS['cpu']}</span>
        <span class="config-section-title">助手实例</span>
        <span class="config-section-count" id="configAssistantCount"></span>
      </div>
      <div id="configAssistantList" class="assistant-list-inline"></div>
      <div class="config-section-foot"><button class="btn-secondary" onclick="showNewAssistantDialog()">+ 新建助手</button></div>
    </div>` : '';

  return `
    <div class="view-header">
      <h1 class="view-title">${view.title}</h1>
      <p class="view-subtitle">${view.subtitle}</p>
    </div>
    ${view.metrics ? `<div class="kpi-row">${renderMetrics(view.metrics)}</div>` : ''}
    ${actions ? `<div class="view-actions">${actions}</div>` : ''}
    ${grid}
    ${assistantSection}
  `;
}

// ── 工具箱（统一管理界面） ──

function renderToolHub() {
  const total = TOOL_CATALOG.length;
  const ready = TOOL_CATALOG.filter(t => t.ready).length;
  const catIds = Object.keys(TOOL_CATEGORIES).filter(c => TOOL_CATALOG.some(t => t.category === c));
  const metrics = [
    { num: String(total), label: '系统能力', icon: 'puzzle' },
    { num: String(catIds.length), label: '能力分类', icon: 'package' },
    { num: String(ready), label: '当前可直接运行', icon: 'check-circle' },
    { num: String(total - ready), label: '需先导入数据', icon: 'download' },
  ];
  const chips = ['all'].concat(catIds).map(c => {
    const n = c === 'all' ? total : TOOL_CATALOG.filter(t => t.category === c).length;
    const label = c === 'all' ? '全部' : (TOOL_CATEGORIES[c] || {}).label || c;
    const icon = c === 'all' ? ICONS['puzzle'] : (ICONS[TOOL_ICONS[(TOOL_CATALOG.find(t => t.category === c) || {}).name]] || '');
    return `<button class="hub-chip ${c === _toolCategory ? 'active' : ''}" data-cat="${c}" onclick="setToolCategory('${c}')">
      <span class="hub-chip-icon">${icon}</span>${label}<span class="hub-chip-num">${n}</span>
    </button>`;
  }).join('');

  return `
    <div class="kpi-row">${renderMetrics(metrics)}</div>
    <div class="tool-hub-bar">
      <div class="tool-search">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7"/><path d="M16.5 16.5L21 21"/></svg>
        <input id="toolSearchInput" type="text" placeholder="搜索能力名称或说明，如 合并 / DRC / 知识库 / 替代料" value="${escapeAttr(_toolQuery)}" oninput="setToolQuery(this.value)">
        <button class="tool-search-clear" onclick="clearToolQuery()" title="清空">✕</button>
      </div>
      <label class="tool-ready-toggle">
        <input type="checkbox" ${_toolOnlyReady ? 'checked' : ''} onchange="setToolOnlyReady(this.checked)">
        <span class="tool-ready-track"></span>
        <span class="tool-ready-text">仅显示可运行</span>
      </label>
    </div>
    <div class="hub-chips">${chips}</div>
    <div class="tool-grid" id="toolGrid"></div>
    <div class="tool-empty" id="toolEmpty" style="display:none">
      <div class="tool-empty-icon">${ICONS['search-plus']}</div>
      <div class="tool-empty-title">没有匹配的能力</div>
      <div class="tool-empty-desc">换个关键词，或切换到「全部」分类</div>
    </div>
  `;
}

function setToolQuery(q) {
  _toolQuery = q || '';
  renderToolGrid();
}

function clearToolQuery() {
  _toolQuery = '';
  const input = document.getElementById('toolSearchInput');
  if (input) { input.value = ''; input.focus(); }
  renderToolGrid();
}

function setToolCategory(cat) {
  _toolCategory = cat;
  document.querySelectorAll('.hub-chip').forEach(c => c.classList.toggle('active', c.dataset.cat === cat));
  renderToolGrid();
}

function setToolOnlyReady(on) {
  _toolOnlyReady = !!on;
  renderToolGrid();
}

function renderToolGrid() {
  const grid = document.getElementById('toolGrid');
  if (!grid) return;
  const q = _toolQuery.trim().toLowerCase();
  const list = TOOL_CATALOG.filter(t => {
    if (_toolCategory !== 'all' && t.category !== _toolCategory) return false;
    if (_toolOnlyReady && !t.ready) return false;
    if (!q) return true;
    const hay = [t.label, t.description, t.name].concat(t.keywords || []).join(' ').toLowerCase();
    return hay.includes(q);
  });
  grid.innerHTML = list.map(renderToolCard).join('');
  const empty = document.getElementById('toolEmpty');
  if (empty) empty.style.display = list.length ? 'none' : '';
}

// ── 工具启动 ──

/** 切到聊天流：关闭功能子页面，显示消息流 */
function _enterChatStream() {
  closeSubPage();
}

async function launchTool(toolName) {
  const t = getTool(toolName);
  if (!t) {
    // 目录未加载（例如离线打开）→ 退回自然语言指令
    quickCmd(toolName);
    return;
  }
  const spec = TOOL_LAUNCH[t.name];
  if (spec && spec.kind === 'run') { spec.run(); return; }
  if (!t.ready) {
    showToast(`「${t.label}」${t.blocked_reason || '暂不可用'}`, 'warning');
    return;
  }
  if (spec && spec.kind === 'image') { triggerImagePick(); return; }
  if (t.needs_input) { prefillToolInput(t); return; }
  await runToolInline(t);
}

function prefillToolInput(t) {
  const spec = TOOL_LAUNCH[t.name];
  const prefix = (spec && spec.prefix) || t.prompt_prefix || (t.label + ' ');
  _enterChatStream();
  const input = document.getElementById('chatInput');
  input.value = prefix;
  input.focus();
  input.setSelectionRange(prefix.length, prefix.length);
  const hint = (t.params || []).map(p => p.hint || p.name).filter(Boolean).join(' / ');
  showToast(`「${t.label}」需要参数：${hint || '请补充输入'}`, 'info');
}

async function runToolInline(t) {
  _enterChatStream();
  const conv = getActiveConversation();
  const prompt = `▶ 运行工具：${t.label}`;
  appendBubble('user', prompt);
  if (conv) {
    conv.messages.push({ role: 'user', content: prompt });
    _persistMessage(activeConvId, 'user', prompt);
  }
  disableInput(true);
  const stream = createStreamingBubble();
  document.getElementById('chatMessages').appendChild(stream.element);
  stream.setStatus(`正在执行 ${t.label} …`);
  scrollChat();

  let resp;
  try { resp = await eel.run_tool(t.name)(); }
  catch (e) { resp = { ok: false, error: String(e) }; }
  disableInput(false);

  const ok = resp && resp.ok;
  const text = ok ? (resp.result || '（该能力没有返回文本输出）') : `执行失败：${(resp && resp.error) || '未知错误'}`;
  stream.finalize(text);
  if (conv) {
    conv.messages.push({ role: 'ai', content: text });
    _persistMessage(activeConvId, 'ai', text);
  }
  if (ok && resp.result) showReport(resp.result);
  renderConversations();
  refreshToolCatalog();
}

/** 打开设置弹窗并直达指定分页 */
function openSettingsAt(tabId) {
  const overlay = document.getElementById('settingsOverlay');
  if (!overlay) return;
  if (!SETTINGS_LOADED) { SETTINGS_LOADED = true; loadSettingsIntoUI(); }
  if (tabId) switchSettingsTab(tabId);
  overlay.classList.add('show');
}

function switchConfigAssistants() {
  switchView('config').then(() => {
    const el = document.getElementById('configAssistantList');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
}

function showEmptyState(show) {
  const el = document.getElementById('chatEmpty');
  if (!el) return;
  el.style.display = show ? '' : 'none';
}

/** One-click demo: load sample defective MCU board, then run rule check */
async function startDemo() {
  // Switch to chat-stream mode: hide view container, show chat messages
  _enterChatStream();
  const demoBtn = _btnFromEvent();
  _btnLoading(demoBtn, '演示加载中');

  // 注意：先把会话准备好：否则首条消息发送时 getActiveConversation() →
  //    newConversation() → clearChatMessages() 会把刚展示的演示结果清空
  //    （2026-09-10 实测：用户视角就是「刚看到的结论消失了」）。
  const conv = getActiveConversation();
  const _record = (role, content) => {
    if (!conv) return;
    conv.messages.push({ role, content });
    _persistMessage(activeConvId, role, content);
  };
  if (conv && conv.messages.length === 0) {
    conv.title = '示例 MCU 板审查';
    _persistConversation(conv);
  }

  appendSystem(' 加载示例数据: 有缺陷的 MCU 板 BOM + 坐标');
  setStatus('加载演示数据...');
  disableInput(true);
  try {
  let resp;
  try { resp = await eel.load_demo_data()(); } catch(e) {
    appendTip(' 加载失败: ' + e, 'error'); setStatus('就绪'); disableInput(false); return;
  }
  if (resp && resp.ok) {
    const okText = ` 已加载示例 BOM: **${resp.count}** 个元件${resp.pos_count ? ` · ${resp.pos_count} 个坐标` : ''}\n\n点击顶栏面板按钮查看 BOM 表格。可继续:\n- 输入「设计规则」运行 71 条 DRC 扫描\n- 进入「设计审查」启动多智能体评审\n- 输入「BOM健康」检查库存与替代料`;
    appendBubble('ai', okText);
    _record('ai', okText);
    if (resp.items && resp.items.length) renderBOMTable(resp.items);
    // 自动跑一次规则检查，让面板有内容
    try {
      const r = await eel.check_rules()();
      if (r && r.ok) showReport(r.report);
    } catch(e) {}
  } else {
    appendTip(' 加载失败: ' + (resp ? resp.msg : '未知错误'), 'error');
  }
  setStatus('就绪');
  disableInput(false);
  renderConversations();
  // 演示数据也是一次「BOM 到位」，工具可用性跟着变
  if (resp && resp.ok) await refreshToolCatalog();
  } finally {
    _btnLoaded(demoBtn);
  }
}

/** Feature card click dispatcher */
