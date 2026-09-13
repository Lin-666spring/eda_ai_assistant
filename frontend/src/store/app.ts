import { create } from "zustand"
import type {
  BOMItem,
  ChatMessage,
  ReviewResult,
  Settings,
  ToolCall,
} from "@/lib/types"

export type ViewId = "bom" | "review" | "report" | "config"
export type PanelTab = "bom" | "report" | "review" | "html"

interface AppState {
  view: ViewId
  setView: (v: ViewId) => void
  showChat: boolean

  messages: ChatMessage[]
  isStreaming: boolean
  agentMode: boolean

  bomItems: BOMItem[]
  hasBom: boolean
  report: string
  review: ReviewResult | null

  settings: Settings | null
  settingsOpen: boolean
  panelOpen: boolean
  activePanelTab: PanelTab

  toggleAgentMode: () => void
  addMessage: (m: ChatMessage) => void
  startStreaming: () => void
  appendToken: (token: string) => void
  addToolCall: (name: string) => void
  finishStreaming: (fullText: string) => void
  failStreaming: (err: string) => void
  setBom: (items: BOMItem[]) => void
  setReport: (r: string) => void
  setReview: (r: ReviewResult | null) => void
  setSettings: (s: Settings) => void
  setSettingsOpen: (open: boolean) => void
  setPanelOpen: (open: boolean) => void
  setActivePanelTab: (t: PanelTab) => void
  clearMessages: () => void
}

function patchLast(messages: ChatMessage[], fn: (m: ChatMessage) => ChatMessage): ChatMessage[] {
  if (messages.length === 0) return messages
  const next = [...messages]
  next[messages.length - 1] = fn(next[messages.length - 1])
  return next
}

export const useAppStore = create<AppState>((set) => ({
  view: "bom",
  setView: (view) => set({ view, showChat: false }),
  showChat: false,

  messages: [],
  isStreaming: false,
  agentMode: false,

  bomItems: [],
  hasBom: false,
  report: "",
  review: null,

  settings: null,
  settingsOpen: false,
  panelOpen: true,
  activePanelTab: "bom",

  toggleAgentMode: () => set((s) => ({ agentMode: !s.agentMode })),

  addMessage: (m) => set((s) => ({ messages: [...s.messages, m], showChat: true })),

  startStreaming: () =>
    set((s) => ({
      isStreaming: true,
      showChat: true,
      messages: [
        ...s.messages,
        { id: crypto.randomUUID(), role: "ai", content: "", streaming: true, toolCalls: [] },
      ],
    })),

  appendToken: (token) =>
    set((s) => ({
      messages: patchLast(s.messages, (m) =>
        m.streaming ? { ...m, content: m.content + token } : m,
      ),
    })),

  addToolCall: (name) =>
    set((s) => ({
      messages: patchLast(s.messages, (m) => {
        if (!m.streaming) return m
        const toolCalls: ToolCall[] = [...(m.toolCalls ?? []), { name, args: {}, status: "running" }]
        return { ...m, toolCalls }
      }),
    })),

  finishStreaming: (fullText) =>
    set((s) => ({
      isStreaming: false,
      messages: patchLast(s.messages, (m) =>
        m.streaming
          ? {
              ...m,
              content: fullText,
              streaming: false,
              toolCalls: (m.toolCalls ?? []).map((t) => ({ ...t, status: "done" as const })),
            }
          : m,
      ),
    })),

  failStreaming: (err) =>
    set((s) => ({
      isStreaming: false,
      messages: patchLast(s.messages, (m) =>
        m.streaming ? { ...m, content: err || "请求失败", streaming: false } : m,
      ),
    })),

  setBom: (items) => set({ bomItems: items, hasBom: items.length > 0 }),
  setReport: (report) => set({ report }),
  setReview: (review) => set({ review }),
  setSettings: (settings) => set({ settings }),
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setPanelOpen: (panelOpen) => set({ panelOpen }),
  setActivePanelTab: (activePanelTab) => set({ activePanelTab }),
  clearMessages: () => set({ messages: [] }),
}))
