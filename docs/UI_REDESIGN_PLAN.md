# UI 重设计计划 — 浅色 Dribbble Dashboard 风格

> 2026-08-26 基于 6 张实际运行截图的诊断与改造方案。
> 范围：`web/index.html`、`web/css/style.css`、`web/js/app.js`。不动后端与 Eel 接口。

## 一、现状诊断（截图确认的 10 个问题)

| # | 问题 | 证据 |
|---|------|------|
| 1 | 首屏巨大空白，无任何引导 | 截图1：顶栏+输入框之间全空 |
| 2 | **审查共识 markdown 未渲染**，`##` 原文显示 | 截图4；`app.js:1724` 直接 `innerHTML = data.consensus` |
| 3 | 视觉层次平：卡片全白底+细边框，无阴影分层、无 hover 反馈 | 截图2/3 |
| 4 | 统计条空洞：4 个数字一排，无图标、无上下文 | 截图2/3/4 |
| 5 | 功能卡片用 emoji 图标，与顶栏 SVG 图标风格打架 | 截图2 |
| 6 | BOM 表格：无斑马纹、表头不吸顶、数字/文本对齐混乱、无状态徽章 | 截图3 |
| 7 | 雷达图 ECharts 默认彩色标签，与蓝色主色调脱节 | 截图4 |
| 8 | 聊天消息与视图卡片混排互相挤压，卡片被切一半 | 截图5 |
| 9 | 设置弹窗内容溢出被裁（底部保存栏不可见）；服务商卡片描述文字截断 | 截图6 |
| 10 | 浮动面板切换按钮悬在内容区正中间，位置尴尬 | 截图1/3/4 |

## 二、设计方向

浅色 SaaS Dashboard（Linear / Vercel / Stripe 一挂），数据密集型界面适配：

- **背景分层**：应用底 `#F5F6F8` → 卡片纯白 → 弹层带阴影。层级靠阴影而非边框
- **阴影三档**：`resting`(0 1 2/0 4 12 低透明) / `hover`(0 4 16) / `overlay`(0 12 40)
- **圆角体系**：卡片 12px、按钮/输入 8px、badge/头像 999px
- **强调色**：沿用 `--accent` 蓝（#2F6FDB 系），语义色 success/warning/danger/info 各配 10% 透明度底色
- **数字排版**：全局 `font-variant-numeric: tabular-nums`（表格/评分对齐）
- **图标统一**：全部换内联 SVG 线性图标（1.5px stroke, Lucide 风格），弃用 emoji
- **微交互**：150–200ms `cubic-bezier(.4,0,.2,1)`；卡片 hover `translateY(-1px)` + 阴影升档；按钮 active `scale(.98)`
- 深色主题不做新设计，靠 CSS 变量自动跟随，仅保证不破版

## 三、实施计划（5 个阶段，按依赖排序）

### Phase 1 — 设计令牌（只动 style.css 顶部）
- 扩展 `:root` 变量：`--shadow-1/2/3`、`--radius-sm/md/lg`、`--success/--warning/--danger` + 各自 `-bg`、`--border`、`--accent-soft`
- 全局：字体栈、`tabular-nums`、滚动条美化、selection 颜色
- 按钮/输入框/badge 基础类重构

### Phase 2 — 布局壳（index.html 微调 + style.css）
- 顶栏：`backdrop-filter: blur` 毛玻璃 + 底部 1px 分隔线，nav pill 选中态加底色+加粗
- 右面板：整体卡片化（圆角+阴影，与主区间距 12px），tab 改下划线指示器滑动动画
- 浮动折叠按钮从内容区中央移到面板左边缘中线，缩小为 24px 圆钮
- 主区内容最大宽度 1080px 居中，左右留白

### Phase 3 — 主区 Dashboard 化（app.js `renderViewHTML` + style.css）
- 视图头部收紧：标题 20px/600 + 描述 13px muted，一行排完
- 统计条 → **KPI 卡片**：图标（淡蓝底圆角方块）+ 大数字 + 副标题，hover 微浮
- 功能卡片：emoji → SVG 图标 map（`app.js` 内置 ICONS 对象），图标放 8px 圆角淡色底块；hover 阴影+上移；卡片右侧加 `›` 箭头暗示可点
- **空状态组件**：主区无数据时显示居中 SVG 插画 + 一句引导 + 主 CTA（导入 BOM / 一键演示），消除截图1的大空白
- 修复截图5问题：发消息时 `viewContainer` 折叠为紧凑横幅（或隐藏），消息流独占主区

### Phase 4 — 核心组件升级
- **BOM 表格**：斑马纹、sticky 表头（毛玻璃底）、行高 36px、位号列 monospace、封装列改 badge 样式、数量列右对齐 tabular-nums；表头加分组标题行（"共 N 项 · M 种封装"）
- **审查面板**：
  - `app.js:1724` 修复：consensus 走 `marked.parse()`（一行修复 bug #2）
  - 评分区：A/94.6 改为 SVG 圆环进度（dasharray 动画）+ 等级徽章配色（A 绿/B 蓝/C 黄/D 红）
  - 雷达图：ECharts option 注入 accent 配色（单色蓝渐变填充，标签统一 muted 色）
  - Agent 卡片：状态图标（✓/⚠/✕ SVG）+ 分数 badge + 左边框改 3px 圆角色条
- **聊天消息**：用户气泡 accent 渐变、AI 消息白底卡片+阴影；markdown 内容代码块/表格样式补齐；快捷操作 chips 改小圆角描边样式
- **报告中心**：报告条目卡片化（图标+标题+时间+摘要+展开）

### Phase 5 — 弹窗与收尾
- 设置弹窗：内容区独立滚动（修复截图9溢出），底部保存栏 sticky；服务商卡片描述 `text-overflow: ellipsis` 两行截断
- 确认/新建助手弹窗：统一圆角 14px + overlay 阴影 + 入场动画（fade+scale）
- Toast 通知（如有）统一样式
- 全量回归：`python -m pytest tests/ -q` + `python main.py` 截图对比 6 个状态

## 四、改动量估计

| 文件 | 改动 |
|------|------|
| `web/css/style.css` | 重写 ~60%（+400/-350 行） |
| `web/js/app.js` | `renderViewHTML` 卡片模板、ICONS map、consensus 渲染修复、KPI 模板（~±120 行） |
| `web/index.html` | 结构微调 ~20 行（空状态容器、面板按钮位置、审查评分环容器） |

## 五、验收标准（对照 6 张截图逐一复拍）

1. 首屏有空状态引导，无大空白
2. BOM 分析页 KPI 卡片 + 图标统一 + hover 反馈
3. BOM 表格斑马纹 + 吸顶表头 + 数字对齐
4. 审查页共识 markdown 正确渲染、评分环动画、雷达图配色统一
5. 聊天消息不再挤压视图卡片
6. 设置弹窗完整可见底部保存栏
