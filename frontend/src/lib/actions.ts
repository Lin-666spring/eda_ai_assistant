import { useAppStore } from "@/store/app"
import { endpoints } from "./api"
import { streamChat } from "./stream"
import type { ReviewResult } from "./types"

function parseReview(raw: string): ReviewResult {
  try {
    return JSON.parse(raw) as ReviewResult
  } catch {
    return {}
  }
}

// ── 聊天 ──

export async function sendChatText(text: string) {
  const store = useAppStore.getState()
  const agentMode = store.agentMode
  store.addMessage({ id: crypto.randomUUID(), role: "user", content: text })
  store.startStreaming()

  let full = ""
  try {
    for await (const ev of streamChat(text, agentMode)) {
      if (ev.event === "token") {
        store.appendToken(ev.data)
      } else if (ev.event === "tool_call") {
        try {
          const { name } = JSON.parse(ev.data)
          store.addToolCall(name)
        } catch {
          /* ignore malformed tool_call */
        }
      } else if (ev.event === "done") {
        full = ev.data
      } else if (ev.event === "error") {
        store.failStreaming(ev.data)
        return
      }
    }
    store.finishStreaming(full)
  } catch (e) {
    store.failStreaming(e instanceof Error ? e.message : String(e))
  }
}

export async function sendImage(text: string, imageBase64: string) {
  const store = useAppStore.getState()
  store.addMessage({ id: crypto.randomUUID(), role: "user", content: text, image: imageBase64 })
  store.startStreaming()
  try {
    const resp = await endpoints.analyzeImage(text, imageBase64)
    if (resp.ok) {
      store.finishStreaming(resp.result)
    } else {
      store.failStreaming(resp.result)
    }
  } catch (e) {
    store.failStreaming(e instanceof Error ? e.message : String(e))
  }
}

// ── 功能 ──

export async function loadDemo() {
  const store = useAppStore.getState()
  try {
    const resp = await endpoints.loadDemo()
    if (resp.ok && resp.items) {
      store.setBom(resp.items)
      const rules = await endpoints.checkRules()
      if (rules.ok) store.setReport(rules.report)
      store.setActivePanelTab("report")
      store.setPanelOpen(true)
    }
  } catch (e) {
    console.error(e)
  }
}

export async function runReview() {
  const store = useAppStore.getState()
  store.setActivePanelTab("review")
  store.setPanelOpen(true)
  try {
    const resp = await endpoints.reviewMultiAgent()
    if (resp.ok) {
      store.setReview(parseReview(resp.report))
    }
  } catch (e) {
    console.error(e)
  }
}

export async function generateHtml() {
  const store = useAppStore.getState()
  try {
    const resp = await endpoints.generateHtmlBom()
    if (resp.ok) {
      store.setReport(resp.report)
      store.setActivePanelTab("report")
      store.setPanelOpen(true)
    }
  } catch (e) {
    console.error(e)
  }
}

export async function loadHeatmapData() {
  try {
    return await endpoints.getDrcHeatmap()
  } catch (e) {
    console.error(e)
    return { ok: false, data: [] }
  }
}

// ── 命令别名（对齐 app.js quickCmd） ──

const COMMAND_ALIASES: Record<string, string> = {
  __summary: "BOM摘要",
  __verify: "验证建议",
}

export async function dispatchAction(action: string) {
  const store = useAppStore.getState()

  if (action === "demo") return loadDemo()
  if (action === "review") return runReview()
  if (action === "generate-html") return generateHtml()
  if (action === "panel") {
    store.setPanelOpen(true)
    return
  }
  if (action === "settings") {
    store.setSettingsOpen(true)
    return
  }
  if (action === "heatmap") {
    store.setActivePanelTab("review")
    store.setPanelOpen(true)
    return
  }
  if (action.startsWith("tab:")) {
    store.setActivePanelTab(action.slice(4) as "bom" | "report" | "review" | "html")
    store.setPanelOpen(true)
    return
  }
  if (action.startsWith("cmd:")) {
    const cmd = action.slice(4)
    return sendChatText(COMMAND_ALIASES[cmd] ?? cmd)
  }
  if (action === "import-bom" || action === "import-data") {
    window.dispatchEvent(new CustomEvent("eda:import", { detail: action }))
    return
  }
  // 新建助手 / 助手管理 暂未接入（需要持久化助手实例 UI）
}
