# UI 重设计 — 进度整理

> 2026-08-26 · 承接 [UI_REDESIGN_PLAN.md](UI_REDESIGN_PLAN.md) 的实施记录
> 目标：浅色 Dribbble Dashboard 风格重构前端
> 改动文件：`web/css/style.css`（已动）、`web/js/app.js`（未动）、`web/index.html`（未动）

## 一、总览

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1 · 设计令牌 + 基础样式 | ✅ 完成 | `style.css` 变量层全部落地 |
| Phase 2 · 布局壳 | 🔶 部分完成 | 卡片化主体已完成；顶栏/右面板/折叠按钮未动 |
| Phase 3 · 主区 Dashboard 化 | ⬜ 未开始 | 需改 `app.js`（KPI/SVG 图标/空状态/消息流分离） |
| Phase 4 · 组件升级 | ⬜ 未开始 | BOM 表格/评分环/雷达图/markdown 修复/气泡 |
| Phase 5 · 弹窗与收尾 | ⬜ 未开始 | 设置弹窗溢出/确认弹窗/动画 |
| 验证 | ⬜ 未开始 | pytest 回归 + 截图对比 |

---

## 二、已完成 ✅

### Phase 1 — 设计令牌（`web/css/style.css`）

**1. 过渡动效令牌**（`:root`）
- `--transition` 由 `160ms ease` → `160ms cubic-bezier(.4,0,.2,1)`（标准 Material 缓动，更顺滑）
- 新增 `--ease-spring: cubic-bezier(.34,1.4,.44,1)`（备用弹簧缓动）

**2. 阴影体系升级**（浅色主题，4 档全部改双阴影）
```css
--shadow-sm: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.05);
--shadow:    0 2px 6px rgba(16,24,40,.05), 0 4px 12px rgba(16,24,40,.06);
--shadow-md: 0 4px 8px rgba(16,24,40,.05), 0 8px 24px rgba(16,24,40,.09);
--shadow-lg: 0 8px 16px rgba(16,24,40,.07), 0 16px 48px rgba(16,24,40,.14);
```
（原来 `--shadow-md/lg` 是单阴影，缺少"近锐远柔"的层次感）

**3. 语义色配套背景变量**（浅色 + 深色主题各加一组）
```css
--success-bg / --warning-bg / --error-bg / --info-bg   /* 10% 透明度软底 */
--accent-soft                                           /* 强调色软底 */
--bg-surface                                           /* 浅色 #f8f9fb / 深色 #232630 */
```
> 用途：Phase 4 的 badge、状态徽章、审查卡片底色直接引用，不再散落硬编码。

**4. 全局排版与细节**
- `body` 增加 `font-variant-numeric: tabular-nums`（表格/评分数字等宽对齐）
- 新增 `::selection { background: rgba(47,111,219,.2) }`
- 滚动条：宽度 `5px` → `6px`，并补 `height: 6px`（横向滚动条此前缺失，宽度只在纵向生效）

---

### Phase 2 — 布局壳（部分）

**1. 主区 + 右面板"悬浮卡片"化**（`#bodyRow`）
```css
#bodyRow { gap: 12px; padding: 12px; background: var(--bg-root); }
```
- 应用底 `#f5f6f8` 露出来，主区和右面板变成两块独立卡片，中间 12px 呼吸缝

**2. 主区卡片化**（`#chatArea`）
```css
border: 1px solid var(--border);
border-radius: var(--radius-lg);       /* 16px */
box-shadow: var(--shadow-sm);
overflow: hidden;
```

**3. 视图容器排版收紧**（`#viewContainer`）
- padding `36px 48px 12px` → `32px 44px 16px`
- **新增 `#viewContainer.hidden { display: none }`** —— 修复截图5 消息挤压卡片的根因（此前 JS 加 `hidden` 类但 CSS 无对应规则，导致两个 `flex:1` 容器 50/50 平分）
- 新增 `#viewContainer > * { max-width:1080px; margin:auto }` 让内容居中留白

---

## 三、未完成 ⬜（按依赖排序）

### Phase 2 剩余
- [ ] **顶栏毛玻璃**：`#topBar` 加 `backdrop-filter: blur` + 底部 1px 细分隔线
- [ ] **右面板卡片化**：`#rightPanel` 加 `border/radius/box-shadow/overflow:hidden`（同 `#chatArea` 处理）
- [ ] **折叠按钮重定位**：`.panel-toggle` 从内容区中央的 22×56 长条，改为面板左边缘 24px 圆钮，`right: calc(var(--panel-w) + 12px)`，折叠态 `rotate(180deg)`
- [ ] **panel-tabs 下边框**：加 `border-bottom: 1px solid var(--border-light)` 分隔标签与内容

### Phase 3 — 主区 Dashboard 化（需改 `app.js`）
- [ ] **KPI 卡片**：`renderViewHTML()` 中 `view-metrics` 加图标（淡蓝底圆角方块 + 大数字 + 副标题）
- [ ] **SVG 图标替换 emoji**：建 `ICONS` 映射（emoji → Lucide 风格线性 SVG），`renderViewHTML` 里 `it.icon` 走映射
- [ ] **空状态组件**：首屏无数据时居中 SVG 插画 + 引导文案 + 主 CTA（消除截图1 大空白）
- [ ] **消息流分离**：修复后需同步改 `switchView()`（见下"必须同步的 JS 修复"）

### Phase 4 — 组件升级
- [ ] **BOM 表格**（`#bomTable`，纯 CSS）：斑马纹、吸顶表头毛玻璃、行高 36px、位号列 monospace、封装列 badge、数量列右对齐
- [ ] **评分环**：`index.html` 审查区 A/94.6 → SVG 圆环进度 + 等级徽章配色（A绿/B蓝/C黄/D红）
- [ ] **雷达图配色**：`drawRadarChart()` 网格/标签/多边形改用主题色（读 `getComputedStyle` 取 `--accent`），去掉杂色 `d.color`
- [ ] **Markdown 渲染修复**：`renderReviewResult()` 共识区走 `renderMarkdown()`
- [ ] **聊天气泡**：用户气泡 accent 渐变白字、AI 消息白底卡片+阴影、快捷操作 chips 描边圆角
- [ ] **报告中心**：`report-card` 图标+标题+时间+摘要+展开

### Phase 5 — 弹窗与收尾
- [ ] **设置弹窗溢出**：`.settings-content` 改 `overflow:hidden`，各 `.settings-tab` 独立滚动，`settings-bottom-bar` `flex-shrink:0` 常驻可见
- [ ] **服务商卡片**：`.provider-cards` 5 列 → 3 列（`repeat(3,1fr)`），描述 1 行 ellipsis（修截图6 文字溢出）
- [ ] **弹窗动画**：`.modal`/`.confirm-modal` 加 fade+scale 入场动画
- [ ] 确认/新建助手弹窗圆角统一 14px

### 验证
- [ ] `python -m pytest tests/ -q` 回归
- [ ] `python main.py` 启动，对照 6 张截图复拍验证

---

## 四、⚠️ 必须同步的 JS 修复（发现的两个 bug）

> 这两个是排查中发现的实际缺陷，**Phase 3/4 动 app.js 时必须一起处理**，否则改完 CSS 会引入新问题。

**Bug 1 — 视图切换后主区可能永久空白**（`app.js:642 switchView`）
- 现状：`switchView` 只 `chatMessages.classList.add('hidden')`，**没有** `viewContainer.classList.remove('hidden')`
- 配合已新增的 `#viewContainer.hidden{display:none}`，一旦发过消息（viewContainer 被加 `hidden`）再点导航，视图将不可见
- 修法：在 `switchView` 里加一行 `document.getElementById('viewContainer').classList.remove('hidden')`

**Bug 2 — 审查共识 Markdown 未渲染**（`app.js:1724 renderReviewResult`）
- 现状：`ce.innerHTML = data.consensus || ''` 直接塞原文，`##` 标题裸显示（截图4）
- 修法：改为 `ce.innerHTML = renderMarkdown(data.consensus)`（复用 `app.js:1019` 已有的安全渲染函数）

---

## 五、下一步建议

1. 先补 Phase 2 剩余 4 项（纯 CSS，零风险）
2. 修 Bug 1（`switchView` 加 `remove('hidden')`）——与 Phase 3 空状态/消息流一起做
3. 修 Bug 2（`renderMarkdown`）——与 Phase 4 审查区一起做
4. 每完成一个 Phase 跑一次 `python main.py` 肉眼验证，最后统一 pytest + 截图
