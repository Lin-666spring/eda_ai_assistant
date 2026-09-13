import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeSanitize from "rehype-sanitize"
import { cn } from "@/lib/utils"
import { useAppStore, type PanelTab } from "@/store/app"
import { loadHeatmapData, runReview } from "@/lib/actions"
import { useEffect, useState } from "react"
import type { DRCHeatmapData } from "@/lib/types"
import ReactECharts from "echarts-for-react"

const TABS: { id: PanelTab; label: string }[] = [
  { id: "bom", label: "BOM 表格" },
  { id: "report", label: "报告" },
  { id: "review", label: "审查" },
  { id: "html", label: "HTML 预览" },
]

function gradeColor(score: number) {
  if (score >= 88) return "#18a058"
  if (score >= 70) return "#2565fe"
  if (score >= 55) return "#e8871e"
  return "#e5484d"
}

function ScoreRing({ score, grade }: { score: number; grade?: string }) {
  const c = 2 * Math.PI * 52
  const offset = c * (1 - score / 100)
  const color = gradeColor(score)
  return (
    <div className="relative h-28 w-28">
      <svg viewBox="0 0 120 120" className="h-28 w-28 -rotate-90">
        <circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" strokeWidth="9" />
        <circle
          cx="60"
          cy="60"
          r="52"
          fill="none"
          stroke={color}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-extrabold leading-none" style={{ color }}>
          {grade ?? "—"}
        </span>
        <span className="mt-0.5 text-base font-bold">{score.toFixed(1)}</span>
      </div>
    </div>
  )
}

function BomTab() {
  const items = useAppStore((s) => s.bomItems)
  const hasBom = useAppStore((s) => s.hasBom)
  if (!hasBom) {
    return <div className="py-12 text-center text-xs text-muted-foreground">尚未导入 BOM — 在 BOM 分析页导入</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="py-2 pr-2 font-medium">#</th>
            <th className="py-2 pr-2 font-medium">位号</th>
            <th className="py-2 pr-2 font-medium">值</th>
            <th className="py-2 pr-2 font-medium">封装</th>
            <th className="py-2 pr-2 font-medium">型号</th>
            <th className="py-2 font-medium">数量</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-muted/50">
              <td className="py-1.5 pr-2 font-mono text-primary">{i + 1}</td>
              <td className="py-1.5 pr-2 font-mono">{it.reference}</td>
              <td className="py-1.5 pr-2">{it.value}</td>
              <td className="py-1.5 pr-2">{it.package}</td>
              <td className="max-w-[120px] truncate py-1.5 pr-2">{it.part_number || "—"}</td>
              <td className="py-1.5">{it.quantity}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ReportTab() {
  const report = useAppStore((s) => s.report)
  if (!report) {
    return <div className="py-12 text-center text-xs text-muted-foreground">执行操作后报告显示于此</div>
  }
  return (
    <div className="prose prose-sm max-w-none prose-pre:bg-muted prose-code:text-primary">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {report}
      </ReactMarkdown>
    </div>
  )
}

function ReviewTab() {
  const review = useAppStore((s) => s.review)
  if (!review) {
    return (
      <button
        onClick={() => runReview()}
        className="mx-auto mt-8 flex flex-col items-center gap-1 rounded-xl bg-gradient-to-br from-primary to-[#5b8def] px-8 py-5 text-white shadow-lg shadow-primary/20 transition-transform hover:-translate-y-0.5"
      >
        <span className="text-lg font-semibold">启动多智能体协同审查</span>
        <span className="text-xs opacity-75">5 个专业 AI Agent 并行评审</span>
      </button>
    )
  }

  const score = review.overall_score ?? 0
  const grade = review.grade
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-center gap-6 py-2">
        <ScoreRing score={score} grade={grade} />
        <div className="text-sm text-muted-foreground">综合评分</div>
      </div>

      {review.consensus && (
        <div className="rounded-lg bg-muted p-3 text-xs leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
            {review.consensus}
          </ReactMarkdown>
        </div>
      )}

      {(review.agents ?? []).map((a, i) => (
        <div
          key={i}
          className={cn(
            "rounded-lg border-l-[3px] bg-muted/50 p-3",
            (a as { level?: string }).level === "critical"
              ? "border-l-destructive"
              : (a as { level?: string }).level === "major"
                ? "border-l-[#e8871e]"
                : "border-l-[#18a058]",
          )}
        >
          <div className="flex items-center gap-2 text-xs font-semibold">
            <span>{a.name}</span>
            <span className="ml-auto text-muted-foreground">{a.score}</span>
          </div>
          {a.summary && <div className="mt-1 text-xs leading-relaxed">{a.summary}</div>}
          {(a.findings ?? []).map((f, j) => (
            <div key={j} className="mt-1 pl-3 text-[11px] text-muted-foreground">
              • {f.text}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

function HeatmapChart() {
  const [data, setData] = useState<DRCHeatmapData | null>(null)
  useEffect(() => {
    loadHeatmapData().then(setData)
  }, [])
  if (!data || !data.ok || data.data.length === 0) {
    return <div className="py-8 text-center text-xs text-muted-foreground">无位置数据 — 请导入 PCB 后运行规则检查</div>
  }
  const xs = [...new Set(data.data.map((d) => d[0]))].sort((a, b) => a - b)
  const ys = [...new Set(data.data.map((d) => d[1]))].sort((a, b) => a - b)
  const option = {
    tooltip: { position: "top" },
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: xs, splitArea: { show: true } },
    yAxis: { type: "category", data: ys, splitArea: { show: true } },
    visualMap: {
      min: 0,
      max: Math.max(1, ...data.data.map((d) => d[2])),
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: 0,
      inRange: { color: ["#e8f0ff", "#2565fe", "#f48730", "#e5484d"] },
    },
    series: [
      {
        type: "heatmap",
        data: data.data,
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.25)" } },
      },
    ],
  }
  return <ReactECharts option={option} style={{ height: 260 }} />
}

export function RightPanel() {
  const panelOpen = useAppStore((s) => s.panelOpen)
  const activeTab = useAppStore((s) => s.activePanelTab)
  const setActiveTab = useAppStore((s) => s.setActivePanelTab)

  if (!panelOpen) return null

  return (
    <aside className="flex w-[360px] shrink-0 flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="flex shrink-0 items-center border-b px-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={cn(
              "border-b-2 px-3 py-2.5 text-xs font-medium transition-colors",
              activeTab === t.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {activeTab === "bom" && <BomTab />}
        {activeTab === "report" && <ReportTab />}
        {activeTab === "review" && (
          <div>
            <ReviewTab />
            <div className="mt-4 border-t pt-3">
              <div className="mb-2 text-sm font-semibold">DRC 违规热力图</div>
              <HeatmapChart />
            </div>
          </div>
        )}
        {activeTab === "html" && (
          <div className="py-12 text-center text-xs text-muted-foreground">HTML BOM 预览将在生成后显示</div>
        )}
      </div>
    </aside>
  )
}
