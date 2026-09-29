# 会话小结 — 2026-09-29（前端加载动效）

主题：**给"生成过程"补上加载动效** —— 在此之前，除工具直跑外几乎没有等待反馈。

## 起因：三个真实的"静默等待"缺口

1. `setStatus()` 是**空实现**（`/* simplified — no status bar in new UI */`），
   而全项目有 17 处调用它 —— 相当于所有状态提示都写进了黑洞；
2. `createStreamingBubble()` 建出来是**空气泡**：从按下发送到 LLM 吐出第一个 token
   之间（Agent 模式下还要先跑工具，常见十几秒）用户只看到一个空白框；
3. 多智能体审查、DRC 热力图统计、文件导入这些秒级～十秒级任务，
   界面上只有"按钮变灰"，没有进行中的视觉。

## 做了什么

### 1. 全局：顶栏状态胶囊 + 顶部进度条

- `web/index.html`：`#statusPill`（`.topbar-right` 内）+ `#topProgress`（`#topBar` 底部滑条）。
- `setStatus(msg)` 落地：运行态 → 胶囊（spinner + 文案）+ 进度条滑动；
  终态（就绪 / 已… / …失败，前缀表 `_DONE_PREFIXES`）→ 转绿色 ✓，1.5s 后自动淡出。
  用 `_statusToken` 防止"旧任务的定时器把新任务的状态收掉"。
- `withBusy(label, fn)`：可嵌套的忙碌包装（`_busyDepth`）。
- **`eel.*` 白名单统一包装**：`_BUSY_LABELS` 列出 14 个慢调用
  （规则扫描 / 多智能体审查 / 生成 HTML / 四种导入 / 知识库 / 热力图 / 演示数据 /
  图片分析 / 测试连接 / 拉模型列表 / 设计意图），调用时自动 `withBusy`。
  ⚠️ **`poll_toggle`（500ms 轮询）绝不能进白名单**，否则进度条一直闪。

### 2. 对话流：思考中动效（`_mountThinking`）

三点脉冲 + 每 2.5s 轮换文案（理解问题 → 读取设计数据 → 组织回答 → 马上就好）+
秒表计时（>15s 变橙色、>25s 换成"仍在处理"）。

- `createStreamingBubble()` 一建出来就是思考态；**首个 token 到达立即让位**给正文
  （首 token 不等节流，直接渲染）；
- `bubble.think(text)`：Agent 调工具时把文案改成「正在调用「设计规则检查」」；
- 工具卡 `.tool-call-card` 增加计时器：执行中显示秒数，完成时定格为 `已完成 · 1.2s`
  （`_finishToolCard()` 统一收尾，原先在 `onStreamDone` 里重复了一遍）。
- 图片分析（非流式接口）也改成走同一个气泡，不再"点了没反应"。

### 3. 面板：骨架屏与占位

- 多智能体审查：`_showReviewLoading()` 铺 **5 张骨架卡 + 三点脉冲标题**
  （文案轮换：解析数据 → 5 位专家并行评审 → 汇总共识 → 生成路线图），
  启动按钮让位、结束后 `_hideReviewLoading()` 撤掉；
- DRC 热力图：`#drcHeatmapLoading` 面板占位 + 按钮转「统计中」；
- 按钮统一 `_btnLoading(btn, label)` / `_btnLoaded(btn)`（内联 spinner + 文案替换 + 可还原），
  `_btnFromEvent()` 让 inline `onclick` 里能同步拿到按钮（`开始演示` / `生成 HTML` / `选择目录`）。

### 4. 无障碍

`prefers-reduced-motion` 下不是"关掉动效"而是"降级为静态仍可见"：
进度条变常亮细线、三点变实心点、骨架停成纯色块、发送键不闪。

## 踩到的坑（值得记住）

### `eel.*` 不能在 app.js 解析时就替换

第一版白名单包装写成「app.js 顶层遍历 `eel[name]` 逐个换成包一层」，
测试里 14 个慢调用**一个都没生效**。原因在 `eel/eel.js`：

```js
eel._websocket.onopen = function () {          // ← Python 函数到这一步才挂上去
    for (...) eel._import_py_function(py_function);
};
```

`eel.import_bom_file` 是 **websocket 连上之后**才被赋值的，而 app.js 在
`DOMContentLoaded` 之前就跑完了 —— 那时 `eel[name]` 还是 `undefined`，
`typeof orig !== 'function'` 把每个条目都静默跳过了（`typeof eel` 本身是 object，
所以连"eel 不存在"的兜底也没触发）。

**正确做法：钩住安装动作本身** —— 覆盖 `eel._import_py_function`，
每装一个就按白名单包一层；再补一次立即执行，兼容热重载时 websocket 已连上的情况。
用 `fn.__busyWrapped` 防止重连时二次包装。

排查手段：在页面里 `eel.someFn.toString()` —— 包装成功会打印包装函数的源码。

### 其它

- UI 冒烟现在把第三方 CDN（`cdn.jsdelivr.net` 的 Inter 字体 / ECharts）不通
  降级为"只报告不失败"：离线跑本来就该降级（图表空、字体回落），
  但**本地资源必须全绿**，所以检查名改成「无 JS 控制台错误（本地资源）」。

## 验证（`tests/ui_smoke.py` 新增 `check_loading_states`，P14 共 12 项）

```
69/69 通过（原 57 项 + P14 12 项），无 JS 报错、无未捕获异常、无失败请求
```

覆盖：思考动效存在性与计时器跳动、首个 token 让位、胶囊/进度条点亮与自动淡出、
审查骨架屏在**同步段**就出现（不等后端）、结束后撤掉、按钮 loading 可还原、
热力图占位挂上与撤掉、**导入类调用被包装后仍正常返回且期间点亮忙碌态**
（这条专门守 `eel.*` 包装层，就是它抓出了上面那个"一个都没包上"的 bug）。

截图存档：`output/ui_smoke/loading_thinking.png`（思考气泡）、
`loading_review.png`（5 张骨架卡）、`loading_heatmap.png`。

## 环境备注（踩过一次）

Playwright 需要给自己的驱动子进程开管道 stdio，在受限沙箱下直接
`PermissionError: [WinError 5] CreateFile ... asyncio/windows_utils.py` ——
**这是沙箱边界，不是代码问题**。跑 UI 冒烟要有能正常 spawn 子进程的权限。

## 改动文件

- `web/index.html`（3 处新 DOM：胶囊 / 进度条 / 审查骨架容器 / 热力图占位）
- `web/css/style.css`（新增 "Loading 动效" 一节 ≈150 行；删掉被 `.think` 取代的 `.stream-status`）
- `web/js/app.js`（`setStatus`/`withBusy`/eel 白名单包装/`_mountThinking`/骨架屏/按钮态/工具卡计时）
- `tests/ui_smoke.py`（`check_loading_states` + 注册 + 文档头补 P14）
- `CLAUDE.md`（前端约定新增"生成/加载过程必须有动效"三条入口说明）
