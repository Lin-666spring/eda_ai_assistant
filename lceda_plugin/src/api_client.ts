/**
 * API client for the EDA AI Assistant local HTTP server.
 *
 * All calls go to http://127.0.0.1:8710/api/v1/*.
 * The server runs alongside LCEDA as a separate process.
 */

const API_BASE = 'http://127.0.0.1:8710/api/v1';

// ── Types ────────────────────────────────────────────────────

export interface BOMComponent {
  reference: string;
  value: string;
  package: string;
  part_number: string;
  description: string;
  quantity: number;
  manufacturer: string;
}

export interface BOMImportResult {
  ok: boolean;
  count: number;
  msg: string;
  items: BOMComponent[];
}

export interface ReportResult {
  ok: boolean;
  report: string;
}

export interface ChatResult {
  ok: boolean;
  result: string;
}

export interface StatusResult {
  ok: boolean;
  has_bom: boolean;
  has_pcb: boolean;
  pcb_info: Record<string, unknown> | null;
}

export interface SettingsResult {
  ok: boolean;
  provider: string;
  api_key: string;
  base_url: string;
  model: string;
  temperature: number;
  theme: string;
  accent: string;
  font_size: number;
  data_dir: string;
}

// ── API Client ───────────────────────────────────────────────

export class ApiClient {
  private static baseUrl = API_BASE;

  /** Server discovery — returns true if the API server is reachable. */
  static async healthCheck(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.baseUrl}/health`, {
        signal: AbortSignal.timeout(2000),
      });
      return resp.ok;
    } catch {
      return false;
    }
  }

  /** Import BOM components directly (no file export needed). */
  static async importBomFromLCEDA(
    components: BOMComponent[]
  ): Promise<BOMImportResult> {
    const resp = await fetch(`${this.baseUrl}/bom/import-from-lceda`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ components }),
    });
    return resp.json() as Promise<BOMImportResult>;
  }

  /** Run rule-based BOM merge. */
  static async mergeBom(): Promise<ReportResult> {
    const resp = await fetch(`${this.baseUrl}/bom/merge`, { method: 'POST' });
    return resp.json() as Promise<ReportResult>;
  }

  /** Run AI-assisted BOM merge. */
  static async aiMergeBom(): Promise<ReportResult> {
    const resp = await fetch(`${this.baseUrl}/bom/ai-merge`, { method: 'POST' });
    return resp.json() as Promise<ReportResult>;
  }

  /** Run DRC rule check. */
  static async checkRules(): Promise<ReportResult> {
    const resp = await fetch(`${this.baseUrl}/rules/check`, { method: 'POST' });
    return resp.json() as Promise<ReportResult>;
  }

  /** Run BOM health check (LCSC API). */
  static async checkBomHealth(): Promise<ReportResult> {
    const resp = await fetch(`${this.baseUrl}/health/check`, { method: 'POST' });
    return resp.json() as Promise<ReportResult>;
  }

  /** Run multi-agent design review. */
  static async multiAgentReview(): Promise<ReportResult> {
    const resp = await fetch(`${this.baseUrl}/review/multi-agent`, {
      method: 'POST',
    });
    return resp.json() as Promise<ReportResult>;
  }

  /** Get design suggestions (intent recognition). */
  static async getDesignSuggestions(): Promise<ChatResult> {
    const resp = await fetch(`${this.baseUrl}/design-suggestions`);
    return resp.json() as Promise<ChatResult>;
  }

  /** Non-streaming chat. */
  static async sendChat(text: string): Promise<ChatResult> {
    const resp = await fetch(`${this.baseUrl}/chat/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    return resp.json() as Promise<ChatResult>;
  }

  /** Get current server status. */
  static async getStatus(): Promise<StatusResult> {
    const resp = await fetch(`${this.baseUrl}/status`);
    return resp.json() as Promise<StatusResult>;
  }

  /** Get settings. */
  static async getSettings(): Promise<SettingsResult> {
    const resp = await fetch(`${this.baseUrl}/settings`);
    return resp.json() as Promise<SettingsResult>;
  }

  /** Streaming chat via SSE. Returns an EventSource. */
  static chatStream(
    text: string,
    agentMode: boolean,
    onToken: (token: string) => void,
    onDone: (fullText: string) => void,
    onError: (error: string) => void
  ): EventSource {
    const params = new URLSearchParams({ text, agent_mode: String(agentMode) });
    const url = `${this.baseUrl}/chat/stream?${params.toString()}`;
    const es = new EventSource(url);

    es.addEventListener('token', (e: MessageEvent) => {
      onToken(e.data as string);
    });
    es.addEventListener('done', (e: MessageEvent) => {
      onDone(e.data as string);
      es.close();
    });
    es.addEventListener('error', () => {
      onError('SSE connection error');
      es.close();
    });

    return es;
  }
}
