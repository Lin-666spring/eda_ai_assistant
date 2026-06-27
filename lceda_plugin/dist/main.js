/**
 * EDA AI Assistant — LCEDA Professional Edition Plugin Entry Point
 *
 * Provides:
 *  - A floating iframe chat panel (SYS_IFrame)
 *  - Menu commands for BOM analysis, DRC checks, and multi-agent review
 *  - Automatic BOM import from the active schematic
 *
 * Architecture:
 *   LCEDA Plugin (this)  →  HTTP (localhost:8710)  →  Python API Server  →  AppController
 */
import { ApiClient } from './api_client';
import { ServerManager } from './server_manager';
import { listenFromIframe } from './iframe_comm';
// ── State ────────────────────────────────────────────────────
let iframePanel = null;
const PANEL_ID = 'eda-ai-panel';
const PANEL_WIDTH = 420;
const PANEL_HEIGHT = 600;
// ═════════════════════════════════════════════════════════════
//  Command Handlers (registered in extension.json commands)
// ═════════════════════════════════════════════════════════════
export function openPanel() {
    if (iframePanel) {
        eda.sys_IFrame.closeIFrame(PANEL_ID);
        iframePanel = null;
    }
    // The iframe HTML is served by the API server (or bundled).
    // For development, we serve from the local API server.
    const iframeUrl = 'http://127.0.0.1:8710/static/iframe/panel.html';
    // Fallback: try file if server isn't serving static
    iframePanel = eda.sys_IFrame.openIFrame(iframeUrl, PANEL_WIDTH, PANEL_HEIGHT, PANEL_ID, {
        title: 'EDA AI 助手',
        resizable: true,
    });
    // Set up iframe message listener
    setupIframeListener();
}
export async function analyzeBom() {
    eda.sys_ToastMessage.show('正在读取 BOM 数据...');
    try {
        // 1. Read BOM from current schematic via LCEDA API
        const schDoc = await eda.sch_Document.getCurrent();
        const bomFile = await eda.sch_ManufactureData.getBomFile(schDoc);
        // 2. Parse BOM data (LCEDA returns CSV/Excel File object)
        const text = await bomFile.text();
        const components = parseBomCSV(text);
        if (components.length === 0) {
            eda.sys_ToastMessage.show('未找到 BOM 数据，请确认原理图已打开');
            return;
        }
        // 3. Send to API server
        const result = await ApiClient.importBomFromLCEDA(components);
        if (!result.ok) {
            eda.sys_ToastMessage.show('BOM 导入失败: ' + result.msg);
            return;
        }
        // 4. Auto-run merge
        const mergeResult = await ApiClient.mergeBom();
        eda.sys_ToastMessage.show(`BOM 分析完成: ${result.count} 种元件, ${components.length} 行`);
        // 5. Open panel to show results
        openPanel();
    }
    catch (err) {
        eda.sys_ToastMessage.show('BOM 分析出错: ' + String(err));
    }
}
export async function bomHealth() {
    eda.sys_ToastMessage.show('正在检查 BOM 健康状态...');
    try {
        const result = await ApiClient.checkBomHealth();
        openPanel();
    }
    catch (err) {
        eda.sys_ToastMessage.show('健康检查出错: ' + String(err));
    }
}
export async function drcCheck() {
    eda.sys_ToastMessage.show('正在运行 DRC 检查...');
    try {
        const result = await ApiClient.checkRules();
        openPanel();
    }
    catch (err) {
        eda.sys_ToastMessage.show('DRC 检查出错: ' + String(err));
    }
}
export async function multiAgentReview() {
    eda.sys_ToastMessage.show('正在运行多智能体审查...');
    try {
        const result = await ApiClient.multiAgentReview();
        openPanel();
    }
    catch (err) {
        eda.sys_ToastMessage.show('审查出错: ' + String(err));
    }
}
export function showAbout() {
    eda.sys_ToastMessage.show('EDA AI 助手 v1.0 | 69条设计规则 | 10家LLM厂商 | 5 Agent审查', 6000);
}
// ═════════════════════════════════════════════════════════════
//  Plugin Lifecycle (called by LCEDA runtime)
// ═════════════════════════════════════════════════════════════
export function activate() {
    console.log('[EDA AI] Plugin activated');
    // Probe the API server on startup.
    ServerManager.ensureServerRunning().then((running) => {
        if (running) {
            console.log('[EDA AI] API server connected');
        }
    });
}
export function deactivate() {
    console.log('[EDA AI] Plugin deactivated');
    if (iframePanel) {
        eda.sys_IFrame.closeIFrame(PANEL_ID);
        iframePanel = null;
    }
}
// ═════════════════════════════════════════════════════════════
//  Internal Helpers
// ═════════════════════════════════════════════════════════════
function setupIframeListener() {
    listenFromIframe(async (msg) => {
        switch (msg.command) {
            case 'analyze-bom':
                await analyzeBom();
                break;
            case 'drc-check':
                await drcCheck();
                break;
            case 'bom-health':
                await bomHealth();
                break;
            case 'multi-agent-review':
                await multiAgentReview();
                break;
            case 'import-current-bom':
                await analyzeBom();
                break;
            default:
                console.log('[EDA AI] Unknown iframe command:', msg.command);
        }
    });
}
/**
 * Parse LCEDA BOM CSV text into BOMComponent[].
 * Handles the standard LCEDA BOM export format.
 */
function parseBomCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length < 2)
        return [];
    // Detect delimiter: comma or tab
    const sep = lines[0].includes('\t') ? '\t' : ',';
    const headers = lines[0].split(sep).map((h) => h.trim());
    // Column index lookup (case-insensitive, fuzzy)
    const idx = (keys) => {
        for (const key of keys) {
            const i = headers.findIndex((h) => h.toLowerCase().replace(/\s/g, '') === key.toLowerCase().replace(/\s/g, ''));
            if (i >= 0)
                return i;
        }
        return -1;
    };
    const refIdx = idx(['位号', 'designator', 'reference', 'ref']);
    const valIdx = idx(['参数', 'value', '规格']);
    const pkgIdx = idx(['封装', 'package', 'footprint']);
    const pnIdx = idx(['产品编号', 'partnumber', 'lcscpart#', '型号', 'mpn']);
    const descIdx = idx(['描述', 'description']);
    const mfrIdx = idx(['制造商', 'manufacturer', '品牌']);
    const components = [];
    for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(sep).map((c) => c.trim().replace(/^"|"$/g, ''));
        if (cols.length < 2)
            continue;
        components.push({
            reference: refIdx >= 0 ? cols[refIdx] : '',
            value: valIdx >= 0 ? cols[valIdx] : '',
            package: pkgIdx >= 0 ? cols[pkgIdx] : '',
            part_number: pnIdx >= 0 ? cols[pnIdx] : '',
            description: descIdx >= 0 ? cols[descIdx] : '',
            quantity: 1,
            manufacturer: mfrIdx >= 0 ? cols[mfrIdx] : '',
        });
    }
    return components;
}
//# sourceMappingURL=main.js.map