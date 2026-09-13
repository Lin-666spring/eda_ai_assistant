import { PanelRight, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import { useAppStore, type ViewId } from "@/store/app"

const NAV: { id: ViewId; label: string }[] = [
  { id: "bom", label: "BOM 分析" },
  { id: "review", label: "设计审查" },
  { id: "report", label: "报告中心" },
  { id: "config", label: "配置管理" },
]

export function TopBar() {
  const view = useAppStore((s) => s.view)
  const setView = useAppStore((s) => s.setView)
  const agentMode = useAppStore((s) => s.agentMode)
  const toggleAgentMode = useAppStore((s) => s.toggleAgentMode)
  const panelOpen = useAppStore((s) => s.panelOpen)
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen)
  const setPanelOpen = useAppStore((s) => s.setPanelOpen)

  return (
    <header className="flex h-14 shrink-0 items-center gap-6 border-b bg-background px-5">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[#5b8def] text-xs font-extrabold text-white shadow-sm">
          EDA
        </div>
        <span className="whitespace-nowrap text-sm font-bold tracking-tight">
          EDA AI 智能助手
        </span>
      </div>

      <nav className="flex items-center gap-1">
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => setView(n.id)}
            className={cn(
              "rounded-md px-3.5 py-1.5 text-sm font-medium transition-colors",
              view === n.id
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {n.label}
          </button>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-1.5">
        <button
          onClick={toggleAgentMode}
          title="Agent 模式 — LLM 自主规划调用工具"
          className={cn(
            "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
            agentMode
              ? "border-primary bg-accent text-primary"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
        >
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              agentMode ? "bg-primary" : "bg-muted-foreground",
            )}
          />
          Agent
        </button>

        <button
          onClick={() => setSettingsOpen(true)}
          title="设置"
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Settings className="h-4 w-4" />
        </button>
        <button
          onClick={() => setPanelOpen(!panelOpen)}
          title="展开/折叠任务面板"
          className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <PanelRight className="h-4 w-4" />
        </button>
      </div>
    </header>
  )
}
