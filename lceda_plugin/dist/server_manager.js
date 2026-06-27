/**
 * Manages the lifecycle of the Python API server process.
 *
 * The plugin probes http://127.0.0.1:8710/api/v1/health on startup.
 * If the server is not running, it launches the Python subprocess.
 * The server is stopped when the plugin is deactivated.
 */
import { ApiClient } from './api_client';
/**
 * Find Python executable by trying common paths.
 * Returns the first one that works, or null.
 */
async function findPython() {
    const candidates = ['python', 'python3', 'py'];
    // In the actual LCEDA context we can't run subprocesses directly,
    // so we rely on the user having Python installed.  We just return
    // 'python' and let the spawn attempt succeed or fail.
    return 'python';
}
/**
 * Server lifecycle manager.
 *
 * NOTE: LCEDA extensions run in a browser sandbox and cannot spawn
 * subprocesses directly.  In production, the user starts the API
 * server manually (or via a startup script).  This class provides
 * the health-check / status interface for the iframe.
 */
export class ServerManager {
    /** Check if the API server is running. */
    static async isRunning() {
        return ApiClient.healthCheck();
    }
    /**
     * Attempt to start the server.  Returns true if it is now reachable.
     *
     * Since LCEDA sandboxes prevent subprocess creation, this shows
     * the user instructions for manual startup if the server isn't found.
     */
    static async ensureServerRunning() {
        if (await ApiClient.healthCheck()) {
            return true;
        }
        // Show toast with startup instructions.
        eda.sys_ToastMessage.show('请在终端中启动 API 服务器: cd eda_ai_assistant && python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8710', 8000);
        // Wait up to 15 seconds for the user to start the server.
        for (let i = 0; i < 30; i++) {
            await delay(500);
            if (await ApiClient.healthCheck()) {
                eda.sys_ToastMessage.show('EDA AI 助手已连接', 3000);
                return true;
            }
        }
        eda.sys_ToastMessage.show('EDA AI 助手: 无法连接到本地服务 (127.0.0.1:8710)', 5000);
        return false;
    }
}
function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
//# sourceMappingURL=server_manager.js.map