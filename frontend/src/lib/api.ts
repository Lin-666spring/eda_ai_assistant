const BASE = "/api/v1"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
}

// ── 具体接口 ──

export interface ImportResult {
  ok: boolean
  count?: number
  msg?: string
  items?: import("./types").BOMItem[]
}

export const endpoints = {
  // 状态
  status: () => api.get<{ ok: boolean; has_bom: boolean; has_pcb: boolean }>("/status"),
  // BOM
  importBom: (filename: string, content_base64: string) =>
    api.post<ImportResult>("/bom/import", { filename, content_base64 }),
  importPos: (filename: string, content_base64: string) =>
    api.post<{ ok: boolean; msg?: string }>("/pos/import", { filename, content_base64 }),
  importPcb: (filename: string, content_base64: string) =>
    api.post<{ ok: boolean; msg?: string }>("/pcb/import", { filename, content_base64 }),
  bomSummary: () => api.post<{ ok: boolean; summary: unknown }>("/bom/summary"),
  generateHtmlBom: () =>
    api.post<{ ok: boolean; report: string; path: string }>("/bom/generate-html"),
  // 规则 / 审查
  checkRules: () => api.post<{ ok: boolean; report: string }>("/rules/check"),
  checkHealth: () => api.post<{ ok: boolean; report: string }>("/health/check"),
  reviewMultiAgent: () => api.post<{ ok: boolean; report: string }>("/review/multi-agent"),
  verifySuggestion: (suggestion: string) =>
    api.post<{ ok: boolean }>("/verify/suggestion", { suggestion }),
  getDrcHeatmap: () => api.get<import("./types").DRCHeatmapData>("/drc/heatmap"),
  getDesignSuggestions: () =>
    api.get<{ ok: boolean; result: string }>("/design-suggestions"),
  // 聊天
  sendMessage: (text: string) => api.post<{ ok: boolean; result: string }>("/chat/send", { text }),
  analyzeImage: (text: string, image_base64: string) =>
    api.post<{ ok: boolean; result: string }>("/image/analyze", { text, image_base64 }),
  clearChat: () => api.post<{ ok: boolean }>("/chat/clear"),
  // 知识库
  queryKnowledge: (query: string) =>
    api.post<{ ok: boolean; result: string }>("/knowledge/query", { query }),
  // LLM 配置
  getLlmConfig: () => api.get<import("./types").LLMConfig>("/llm/config"),
  testLlm: (provider: string, api_key: string, base_url: string, model: string) =>
    api.post<{ ok: boolean; latency?: number; error?: string }>("/llm/test", {
      provider,
      api_key,
      base_url,
      model,
    }),
  // 设置
  getSettings: () => api.get<import("./types").Settings>("/settings"),
  saveSettings: (settings: Partial<import("./types").Settings>) =>
    api.post<{ ok: boolean }>("/settings", settings),
  clearAllData: () => api.post<{ ok: boolean }>("/clear-all-data"),
  // 持久化
  persistLoadAll: () => api.get<{ ok: boolean; data: import("./types").PersistData }>("/persist/load-all"),
  persistSaveAssistant: (instance_id: string, type_id: string, name: string) =>
    api.post<{ ok: boolean }>("/persist/assistant", { instance_id, type_id, name }),
  persistDeleteAssistant: (instance_id: string) =>
    api.del<{ ok: boolean }>(`/persist/assistant/${encodeURIComponent(instance_id)}`),
  persistSaveConversation: (conv_id: string, instance_id: string, title: string) =>
    api.post<{ ok: boolean }>("/persist/conversation", { conv_id, instance_id, title }),
  persistDeleteConversation: (conv_id: string) =>
    api.del<{ ok: boolean }>(`/persist/conversation/${encodeURIComponent(conv_id)}`),
  persistSaveMessage: (conv_id: string, role: string, content: string, image?: string) =>
    api.post<{ ok: boolean }>("/persist/message", { conv_id, role, content, image }),
  persistLoadMessages: (conv_id: string) =>
    api.get<{ ok: boolean; messages: { role: string; content: string; image: string }[] }>(
      `/persist/messages/${encodeURIComponent(conv_id)}`,
    ),
  persistSaveActiveState: (active_assistant: string, active_conv: string) =>
    api.post<{ ok: boolean }>("/persist/active-state", { active_assistant, active_conv }),
  // 演示
  loadDemo: () =>
    api.post<{ ok: boolean; count: number; pos_count: number; msg: string; items: import("./types").BOMItem[] }>(
      "/demo/load",
    ),
}
