import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Database,
  Eye,
  FileText,
  Flame,
  FolderOpen,
  Globe,
  Link2,
  Map,
  Monitor,
  Palette,
  PencilRuler,
  Receipt,
  Route,
  Search,
  Settings,
  Timer,
  Users,
  type LucideIcon,
} from "lucide-react"

export interface ViewMetric {
  num: string
  label: string
  icon: LucideIcon
}

export interface ViewAction {
  label: string
  sub?: string
  primary?: boolean
  action: string
}

export interface ViewItem {
  icon: LucideIcon
  title: string
  desc: string
  action: string
}

export interface ViewConfig {
  title: string
  subtitle: string
  metrics: ViewMetric[]
  actions: ViewAction[]
  items: ViewItem[]
}

function metricIcon(label: string): LucideIcon {
  if (/规则/.test(label)) return PencilRuler
  if (/ML/.test(label)) return Brain
  if (/检出/.test(label)) return CheckCircle2
  if (/Agent/.test(label)) return Users
  if (/耗时/.test(label)) return Timer
  if (/版本/.test(label)) return Cpu
  if (/格式/.test(label)) return FileText
  return BarChart3
}

export const VIEWS: Record<string, ViewConfig> = {
  bom: {
    title: "BOM 分析",
    subtitle: "物料清单的导入、校验、合并与供应链健康检查 — 确保每一颗元件可用、对、省。",
    metrics: [
      { num: "71", label: "设计规则", icon: metricIcon("设计规则") },
      { num: "3", label: "自研 ML 模型", icon: metricIcon("自研 ML 模型") },
      { num: "98%", label: "缺陷检出率", icon: metricIcon("缺陷检出率") },
      { num: "5", label: "审查 Agent", icon: metricIcon("审查 Agent") },
    ],
    actions: [
      { label: "一键演示", sub: "加载示例缺陷 MCU 板", primary: true, action: "demo" },
      { label: "导入 BOM 文件", sub: "CSV / Excel", primary: false, action: "import-bom" },
    ],
    items: [
      { icon: Activity, title: "BOM 体检", desc: "库存 · 生命周期 · 替代料 · 成本", action: "cmd:BOM健康" },
      { icon: PencilRuler, title: "封装校验", desc: "标准封装库匹配与纠错", action: "cmd:校验封装" },
      { icon: Search, title: "查重", desc: "重复位号与冗余元件检测", action: "cmd:查重" },
      { icon: Link2, title: "合并 BOM", desc: "多份 BOM 规则化合并", action: "cmd:合并 BOM" },
      { icon: Bot, title: "AI 智能合并", desc: "LLM 语义匹配去重", action: "cmd:AI智能合并" },
      { icon: ClipboardList, title: "BOM 摘要", desc: "统计概览与风险摘要", action: "cmd:__summary" },
    ],
  },
  review: {
    title: "设计审查",
    subtitle: "71 条 PCB 设计规则全量扫描 · 多智能体协同评审 · 违规密度可视化定位。",
    metrics: [
      { num: "71", label: "DRC 规则", icon: metricIcon("DRC 规则") },
      { num: "5", label: "审查 Agent", icon: metricIcon("审查 Agent") },
      { num: "18s", label: "平均耗时", icon: metricIcon("平均耗时") },
      { num: "V2.8", label: "模型版本", icon: metricIcon("模型版本") },
    ],
    actions: [
      { label: "启动多智能体审查", sub: "5 个专业 Agent 并行评审", primary: true, action: "review" },
      { label: "加载 DRC 热力图", sub: "违规密度可视化", primary: false, action: "heatmap" },
    ],
    items: [
      { icon: PencilRuler, title: "设计规则检查", desc: "71 条 DRC 规则全量扫描", action: "cmd:设计规则" },
      { icon: Route, title: "走线检查", desc: "信号走线质量与拓扑", action: "cmd:检查走线" },
      { icon: Monitor, title: "PCB 分析", desc: "网表 · 过孔 · 层结构", action: "cmd:分析PCB" },
      { icon: Flame, title: "DRC 热力图", desc: "违规密度空间定位", action: "heatmap" },
      { icon: Users, title: "多智能体审查", desc: "5 个专业 Agent 评审", action: "review" },
      { icon: CheckCircle2, title: "建议验证", desc: "闭环验证修改建议", action: "cmd:__verify" },
    ],
  },
  report: {
    title: "报告中心",
    subtitle: "生成交互式 HTML BOM · 查看历史报告栈 · 导出审查结果。",
    metrics: [
      { num: "HTML", label: "报告格式", icon: metricIcon("报告格式") },
      { num: "交互", label: "可点击位号", icon: Eye },
      { num: "历史", label: "报告栈", icon: Database },
      { num: "一键", label: "导出", icon: CheckCircle2 },
    ],
    actions: [
      { label: "生成 HTML BOM", sub: "交互式物料表", primary: true, action: "generate-html" },
      { label: "打开任务面板", sub: "查看报告与审查结果", primary: false, action: "panel" },
    ],
    items: [
      { icon: Globe, title: "生成 HTML BOM", desc: "交互式可点击物料表", action: "cmd:生成 HTML" },
      { icon: FileText, title: "报告栈", desc: "操作历史报告归档", action: "tab:report" },
      { icon: BarChart3, title: "审查结果", desc: "多智能体评审卡片", action: "tab:review" },
      { icon: Map, title: "DRC 热力图", desc: "违规空间分布", action: "tab:review" },
      { icon: Receipt, title: "BOM 表格", desc: "当前物料明细", action: "tab:bom" },
      { icon: Eye, title: "HTML 预览", desc: "生成的 BOM 预览", action: "tab:html" },
    ],
  },
  config: {
    title: "配置管理",
    subtitle: "AI 模型 · 外观主题 · 通用设置 · 助手实例管理 — 一切可调项集中于此。",
    metrics: [
      { num: "5+", label: "LLM 服务商", icon: metricIcon("LLM 服务商") },
      { num: "4", label: "助手类型", icon: Users },
      { num: "本地", label: "ML 离线", icon: Brain },
      { num: "SQLite", label: "持久化", icon: Database },
    ],
    actions: [
      { label: "AI 模型配置", sub: "API Key · 模型 · 温度", primary: true, action: "settings" },
      { label: "新建助手", sub: "多实例助手模型", primary: false, action: "new-assistant" },
    ],
    items: [
      { icon: Bot, title: "AI 模型", desc: "服务商 · API Key · 模型选择", action: "settings" },
      { icon: Palette, title: "外观主题", desc: "深浅色 · 强调色 · 字号", action: "settings" },
      { icon: Settings, title: "通用设置", desc: "自动保存 · 文件监听 · 确认", action: "settings" },
      { icon: Database, title: "数据存储", desc: "路径与清除本地数据", action: "settings" },
      { icon: Brain, title: "助手管理", desc: "多实例助手创建与切换", action: "assistants" },
      { icon: FolderOpen, title: "导入数据", desc: "导入 PCB 或坐标文件", action: "import-data" },
    ],
  },
}
