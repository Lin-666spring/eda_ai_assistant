/**
 * API client for the EDA AI Assistant local HTTP server.
 *
 * All calls go to http://127.0.0.1:8710/api/v1/*.
 * The server runs alongside LCEDA as a separate process.
 */
const API_BASE = 'http://127.0.0.1:8710/api/v1';
// ── API Client ───────────────────────────────────────────────
export class ApiClient {
    /** Server discovery — returns true if the API server is reachable. */
    static async healthCheck() {
        try {
            const resp = await fetch(`${this.baseUrl}/health`, {
                signal: AbortSignal.timeout(2000),
            });
            return resp.ok;
        }
        catch {
            return false;
        }
    }
    /** Import BOM components directly (no file export needed). */
    static async importBomFromLCEDA(components) {
        const resp = await fetch(`${this.baseUrl}/bom/import-from-lceda`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ components }),
        });
        return resp.json();
    }
    /** Run rule-based BOM merge. */
    static async mergeBom() {
        const resp = await fetch(`${this.baseUrl}/bom/merge`, { method: 'POST' });
        return resp.json();
    }
    /** Run AI-assisted BOM merge. */
    static async aiMergeBom() {
        const resp = await fetch(`${this.baseUrl}/bom/ai-merge`, { method: 'POST' });
        return resp.json();
    }
    /** Run DRC rule check. */
    static async checkRules() {
        const resp = await fetch(`${this.baseUrl}/rules/check`, { method: 'POST' });
        return resp.json();
    }
    /** Run BOM health check (LCSC API). */
    static async checkBomHealth() {
        const resp = await fetch(`${this.baseUrl}/health/check`, { method: 'POST' });
        return resp.json();
    }
    /** Run multi-agent design review. */
    static async multiAgentReview() {
        const resp = await fetch(`${this.baseUrl}/review/multi-agent`, {
            method: 'POST',
        });
        return resp.json();
    }
    /** Get design suggestions (intent recognition). */
    static async getDesignSuggestions() {
        const resp = await fetch(`${this.baseUrl}/design-suggestions`);
        return resp.json();
    }
    /** Non-streaming chat. */
    static async sendChat(text) {
        const resp = await fetch(`${this.baseUrl}/chat/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        return resp.json();
    }
    /** Get current server status. */
    static async getStatus() {
        const resp = await fetch(`${this.baseUrl}/status`);
        return resp.json();
    }
    /** Get settings. */
    static async getSettings() {
        const resp = await fetch(`${this.baseUrl}/settings`);
        return resp.json();
    }
    /** Streaming chat via SSE. Returns an EventSource. */
    static chatStream(text, agentMode, onToken, onDone, onError) {
        const params = new URLSearchParams({ text, agent_mode: String(agentMode) });
        const url = `${this.baseUrl}/chat/stream?${params.toString()}`;
        const es = new EventSource(url);
        es.addEventListener('token', (e) => {
            onToken(e.data);
        });
        es.addEventListener('done', (e) => {
            onDone(e.data);
            es.close();
        });
        es.addEventListener('error', () => {
            onError('SSE connection error');
            es.close();
        });
        return es;
    }
}
ApiClient.baseUrl = API_BASE;
//# sourceMappingURL=api_client.js.map