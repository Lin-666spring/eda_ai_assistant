// ═══════════════════════════════════════════
//  State & 启动流程 —— P1-6 阶段C 自 app.js 拆出（原 1-231 行）
//  ASSISTANT_TYPES / 实例·会话·工作区状态 / 两段式启动 / Marked 配置 / Init
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

/* ═══════════════════════════════════════════
   EDA AI 智能助手 — Cherry Studio Frontend
   ═══════════════════════════════════════════ */

// ═══════════ State ═══════════

const ASSISTANT_TYPES = {
  'eda-general': {
    typeId: 'eda-general', name: 'EDA 通用助手', icon: '(´｡• ᵕ •｡`)',
    systemPrompt: 'general',
    quickActions: ['合并 BOM', '校验封装', '设计规则', 'BOM健康', '查询知识库'],
    description: 'BOM管理、设计规则检查、PCB分析的通用助手',
  },
  'bom-expert': {
    typeId: 'bom-expert', name: 'BOM 管理专家', icon: '( •̀ᴗ•́ )و',
    systemPrompt: 'bom',
    quickActions: ['合并 BOM', 'AI智能合并', '校验封装', '查重', 'BOM健康', '生成 HTML'],
    description: '专注于物料清单管理、合并、验证和供应链检查',
  },
  'pcb-reviewer': {
    typeId: 'pcb-reviewer', name: 'PCB 设计审查', icon: '(｡･ω･｡)',
    systemPrompt: 'pcb',
    quickActions: ['设计规则', '分析PCB', '检查走线', '查看PCB', '查询知识库'],
    description: '专注于PCB布局分析、设计规则检查和信号完整性',
  },
  'vision-analyst': {
    typeId: 'vision-analyst', name: '视觉分析助手', icon: '(=^･^=)',
    systemPrompt: 'vision',
    quickActions: ['分析图片'],
    description: '上传PCB截图或原理图进行AI视觉分析',
  },
};

// ── Assistant instances (multi-instance model) ──
let assistantInstances = [];   // [{ instanceId, typeId, customName? }]
let currentAssistantInstance = null;  // instanceId
let instanceCounter = 0;

// ── Conversations per instance ──
let conversations = {};        // { instanceId: [{ id, title, messages: [] }] }
let activeConvId = null;
let convCounter = 0;

// ── Workspaces（工作区：对话的工程上下文）──
const DEFAULT_WORKSPACE_ID = 'ws_default';
let workspaces = [];            // [{ id, name, path }]
let currentWorkspaceId = null;  // 当前工作区 id

// ── UI state ──
let currentImage = null;
let _activeStreamBubble = null;
let _streamTokenCount = 0;
let agentMode = false;

function createAssistantInstance(typeId, customName) {
  const type = ASSISTANT_TYPES[typeId];
  if (!type) return null;
  instanceCounter++;
  const inst = {
    instanceId: `asst_${Date.now()}_${instanceCounter}`,
    typeId: typeId,
    name: customName || type.name,
  };
  assistantInstances.push(inst);
  _persistAssistant(inst);
  return inst;
}

// ── 启动流程（配合 index.html 里的 window.boot）──
// 分工：index.html 的收尾脚本负责「展开窗口 + 淡出遮罩」（它首帧就存在，
// 必须早于 app.js）；这里负责「报进度 + 等后端就绪」——这些步骤只有 app.js 知道。
// 两段式启动的完整链路见 main.py 的 _boot_worker / boot_status。

/** 启动界面文案 + 进度（0~1）。进度对应本页真实要做的几步，不是假百分比。 */
function splashStatus(text, ratio) {
  if (window.boot && typeof window.boot.step === 'function') window.boot.step(text, ratio);
}

/** 首屏渲染完成 → 交给 window.boot 展开窗口并淡出遮罩。幂等。 */
function hideSplash() {
  if (window.boot && window.boot.hold) return;   // URL 带 #boot-hold：停在启动界面
  if (window.boot && typeof window.boot.finish === 'function') window.boot.finish();
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/** 启动界面上的品牌信息：版本号 + 可选的自制 logo（后端只在文件存在时给路径）。 */
function applyBootBranding(st) {
  if (!st) return;
  if (window.boot && window.boot.state && st.main_size) {
    window.boot.state.mainSize = st.main_size;   // 展开尺寸以后端为准
  }
  const ver = document.getElementById('appSplashVersion');
  if (ver && st.app && st.app.version) ver.textContent = 'v' + st.app.version;

  const img = document.getElementById('appSplashLogoImg');
  if (img && st.logo && !img.getAttribute('src')) {
    img.addEventListener('load', () => {
      img.classList.add('is-on');           // 见 style.css：默认 display:none
      const svg = img.parentNode && img.parentNode.querySelector('svg');
      if (svg) svg.style.display = 'none';
    }, { once: true });
    img.setAttribute('src', st.logo);
  }
}

/**
 * 等后端关键步骤就绪（BootSequencer，见 src/core/boot.py）。
 *
 * 不是 main() 启动的场景（UI 冒烟测试 / 调试时直接 eel.start）started 为 false，
 * 立刻返回 —— 别把「两段式启动」强加给这些场景。
 * 后端迟迟不就绪也不等死：最多约 9s，之后照样放行。
 */
async function waitForBackendBoot() {
  if (typeof eel === 'undefined' || typeof eel.boot_status !== 'function') return null;
  let last = null;
  for (let i = 0; i < 60; i++) {
    let st = null;
    try { st = await eel.boot_status()(); } catch (e) { return last; }
    if (!st || st.started !== true) return null;
    last = st;
    applyBootBranding(st);
    if (st.ready) return st;
    splashStatus(st.text || '正在启动…', 0.72);
    await sleep(150);
  }
  return last;
}

/**
 * 界面展开之后，知识库预热可能还在跑（它不挡界面）。
 * 用顶栏状态胶囊如实报一句，别让人以为卡住了；报过才收尾成「就绪」。
 */
async function watchBackendWarmup() {
  if (typeof eel === 'undefined' || typeof eel.boot_status !== 'function') return;
  let announced = false;
  for (let i = 0; i < 200; i++) {           // 最多约 60s
    let st = null;
    try { st = await eel.boot_status()(); } catch (e) { return; }
    if (!st || st.started !== true) return;
    if (st.warm) {
      if (announced) setStatus('就绪');
      return;
    }
    announced = true;
    setStatus(st.text || '正在预热知识库…');
    await sleep(300);
  }
}

// ── Marked.js configuration ──
if (typeof marked !== 'undefined') {
  marked.setOptions({
    breaks: true, gfm: true, headerIds: false, mangle: false,
  });
}

// ═══════════ Init ═══════════

document.addEventListener('DOMContentLoaded', async () => {
  try {
    splashStatus('正在载入工作区…', 0.16);
    await loadPersistedState();

    // 统一工具目录（后端 ToolRegistry 派生）— 子页面与工具箱共用
    splashStatus('正在载入工具目录…', 0.42);
    await loadToolCatalog();
    renderWorkspaces();
    updateSessionBar();
    renderConversations();
    renderAssistantMenu();

    // 主页面默认就是对话：不自动打开任何模式子页面。
    closeSubPage();

    // Theme — 以 settings 为准，未知值一律回落浅色
    splashStatus('正在恢复设置…', 0.62);
    try {
      const sett = await eel.get_settings()();
      if (sett && sett.theme) applyTheme(sett.theme);
      if (sett && sett.font_size) {
        document.documentElement.style.setProperty('--font-size', sett.font_size + 'px');
      }
    } catch(e) {}

    // LLM config
    try {
      const cfg = await eel.get_llm_config()();
      updateLLMStatus(cfg);
    } catch(e) {}

    // Right-panel tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Enter to send, Shift+Enter for newline
    const input = document.getElementById('chatInput');
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
    });

    // Paste image
    document.addEventListener('paste', e => {
      const items = e.clipboardData && e.clipboardData.items;
      if (!items) return;
      for (let item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const blob = item.getAsFile();
          const reader = new FileReader();
          reader.onload = ev => { currentImage = ev.target.result; showImagePreview(currentImage); };
          reader.readAsDataURL(blob);
          break;
        }
      }
    });

    // 后端关键步骤（热键/托盘）就绪后，前端才把窗口从小窗展开成正式界面
    splashStatus('正在等待后台就绪…', 0.8);
    await waitForBackendBoot();
  } catch (err) {
    // 初始化失败也必须收掉启动界面，否则界面永远停在小窗加载页
    console.error('启动初始化失败:', err);
    splashStatus('启动遇到问题，已进入界面');
  } finally {
    hideSplash();
    watchBackendWarmup();   // 不 await：预热是后台的事，界面已经能用了
  }
});

