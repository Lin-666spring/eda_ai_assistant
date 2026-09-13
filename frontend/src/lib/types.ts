// 与后端 src/api/endpoints.py 返回形状对齐的类型定义

export interface BOMItem {
  reference: string
  value: string
  package: string
  part_number: string
  description: string
  quantity: number
  manufacturer: string
}

export interface Settings {
  provider: string
  api_key: string
  base_url: string
  model: string
  temperature: number
  theme: string
  accent: string
  font_size: number
  data_dir: string
}

export interface LLMConfig {
  provider: string
  model: string
  is_configured: boolean
  provider_label: string
}

export interface ToolCall {
  name: string
  args: unknown
  status: "running" | "done"
}

export interface ChatMessage {
  id: string
  role: "user" | "ai" | "system"
  content: string
  image?: string
  toolCalls?: ToolCall[]
  streaming?: boolean
}

export interface RadarItem {
  label: string
  score: number
}

export interface AgentFinding {
  severity: "critical" | "major" | "minor"
  text: string
}

export interface AgentReport {
  name: string
  score: number
  summary: string
  findings: AgentFinding[]
  [key: string]: unknown
}

export interface ReviewResult {
  overall_score?: number
  grade?: string
  radar_data?: RadarItem[]
  consensus?: string
  agents?: AgentReport[]
  roadmap?: string[]
  [key: string]: unknown
}

export interface PersistAssistant {
  instance_id: string
  type_id: string
  name: string
  sort_order: number
}

export interface PersistConversation {
  conv_id: string
  title: string
  sort_order: number
}

export interface PersistData {
  assistants: PersistAssistant[]
  conversations: Record<string, PersistConversation[]>
  active_assistant: string | null
  active_conv: string | null
}

export interface DRCHeatmapData {
  ok: boolean
  data: [number, number, number][]
}
