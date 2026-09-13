import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { endpoints } from "@/lib/api"
import { useAppStore } from "@/store/app"
import { Button } from "@/components/ui/button"

const PROVIDERS = [
  { id: "deepseek", name: "DeepSeek", base: "https://api.deepseek.com" },
  { id: "openai", name: "OpenAI", base: "https://api.openai.com/v1" },
  { id: "qwen", name: "通义千问", base: "https://dashscope.aliyuncs.com/compatible-mode/v1" },
  { id: "glm", name: "智谱 GLM", base: "https://open.bigmodel.cn/api/paas/v4" },
  { id: "moonshot", name: "Kimi", base: "https://api.moonshot.cn/v1" },
  { id: "siliconflow", name: "硅基流动", base: "https://api.siliconflow.cn/v1" },
  { id: "claude", name: "Claude", base: "https://api.anthropic.com" },
  { id: "gemini", name: "Gemini", base: "https://generativelanguage.googleapis.com/v1beta" },
  { id: "doubao", name: "豆包", base: "https://ark.cn-beijing.volces.com/api/v3" },
  { id: "minimax", name: "MiniMax", base: "https://api.minimax.chat/v1" },
]

type Tab = "ai" | "appearance" | "general" | "about"

const inputCls =
  "w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-primary focus:ring-2 focus:ring-primary/20"

export function SettingsDialog() {
  const open = useAppStore((s) => s.settingsOpen)
  const setOpen = useAppStore((s) => s.setSettingsOpen)
  const [tab, setTab] = useState<Tab>("ai")

  const [provider, setProvider] = useState("deepseek")
  const [apiKey, setApiKey] = useState("")
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [temperature, setTemperature] = useState(0.7)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState("")

  useEffect(() => {
    if (!open) return
    endpoints
      .getSettings()
      .then((s) => {
        setProvider(s.provider || "deepseek")
        setApiKey(s.api_key || "")
        setBaseUrl(s.base_url || "")
        setModel(s.model || "")
        setTemperature(s.temperature ?? 0.7)
      })
      .catch(() => {})
  }, [open])

  if (!open) return null

  function onProviderChange(p: string) {
    setProvider(p)
    const preset = PROVIDERS.find((x) => x.id === p)
    if (preset && !baseUrl) setBaseUrl(preset.base)
  }

  async function save() {
    await endpoints.saveSettings({ provider, api_key: apiKey, base_url: baseUrl, model, temperature })
    setOpen(false)
  }

  async function test() {
    setTesting(true)
    setTestResult("")
    const r = await endpoints.testLlm(provider, apiKey, baseUrl, model)
    setTesting(false)
    setTestResult(r.ok ? `连接成功 · ${r.latency}ms` : r.error || "连接失败")
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <div
        className="flex h-[540px] w-[800px] max-w-[90vw] overflow-hidden rounded-2xl border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <nav className="w-44 shrink-0 border-r bg-muted/40 p-3">
          <div className="px-2 pb-3 text-sm font-bold">设置</div>
          {(
            [
              { id: "ai", label: "AI 模型" },
              { id: "appearance", label: "外观" },
              { id: "general", label: "通用" },
              { id: "about", label: "关于" },
            ] as { id: Tab; label: string }[]
          ).map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "mb-0.5 block w-full rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                tab === t.id
                  ? "bg-primary font-semibold text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6">
            {tab === "ai" && (
              <div>
                <h3 className="text-lg font-bold">AI 模型配置</h3>
                <p className="mb-5 text-xs text-muted-foreground">选择 AI 服务商并配置 API 密钥</p>

                <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">服务商</label>
                <div className="mb-4 grid grid-cols-3 gap-2">
                  {PROVIDERS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => onProviderChange(p.id)}
                      className={cn(
                        "rounded-lg border px-3 py-2 text-xs font-medium transition-colors",
                        provider === p.id
                          ? "border-primary bg-accent text-primary"
                          : "border-border hover:border-primary/50",
                      )}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>

                <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">模型</label>
                <input
                  className={cn(inputCls, "mb-4")}
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="如 deepseek-chat"
                />

                <div className="mb-4 grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">API Key</label>
                    <input
                      type="password"
                      className={inputCls}
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="sk-..."
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">Base URL</label>
                    <input
                      className={inputCls}
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="自动填充"
                    />
                  </div>
                </div>

                <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">
                  生成温度 <span className="ml-1 rounded-full bg-primary px-1.5 py-0.5 text-[10px] text-primary-foreground">{temperature}</span>
                </label>
                <input
                  type="range"
                  min={0}
                  max={1.5}
                  step={0.05}
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  className="w-full accent-[#2565fe]"
                />

                <div className="mt-4 flex items-center gap-2">
                  <Button variant="outline" onClick={test} disabled={testing}>
                    {testing ? "测试中…" : "测试连接"}
                  </Button>
                  {testResult && <span className="text-xs text-muted-foreground">{testResult}</span>}
                </div>
              </div>
            )}

            {tab === "appearance" && (
              <div>
                <h3 className="text-lg font-bold">外观设置</h3>
                <p className="mb-4 text-xs text-muted-foreground">
                  当前为浅色主题，主色 <span className="font-semibold text-primary">#2565fe</span>
                </p>
                <div className="flex gap-2">
                  {["#2565fe", "#e5484d", "#e8871e", "#18a058", "#9b59b6", "#1abc9c"].map((c) => (
                    <button key={c} className="h-7 w-7 rounded-full border-2 border-transparent" style={{ background: c }} />
                  ))}
                </div>
              </div>
            )}

            {tab === "general" && (
              <div>
                <h3 className="text-lg font-bold">通用设置</h3>
                <p className="mb-4 text-xs text-muted-foreground">数据存储位置与本地数据</p>
                <Button
                  variant="outline"
                  className="text-destructive"
                  onClick={() => {
                    if (window.confirm("确定清除所有本地数据？")) endpoints.clearAllData()
                  }}
                >
                  清除所有本地数据
                </Button>
              </div>
            )}

            {tab === "about" && (
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-[#5b8def] text-lg font-extrabold text-white">
                  EDA
                </div>
                <h4 className="text-base font-bold">EDA AI 智能助手</h4>
                <div className="mt-1 text-xs text-primary">v1.0.0</div>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                  基于多智能体协同的 PCB 设计辅助工具
                  <br />
                  71 条设计规则 · 3 个自研 ML 模型 · 5 个专业审查 Agent
                </p>
              </div>
            )}
          </div>

          <div className="flex shrink-0 items-center justify-end gap-2 border-t p-4">
            <Button variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button onClick={save}>保存设置</Button>
          </div>
        </div>
      </div>
    </div>
  )
}
