# 会话小结 — 2026-10-07（客户端缺陷清扫：web/js/app.js 为主）

主题：**延续同日 API 修复的口径，把「双入口漂移 / 前端手抄 SSOT / 静默失效」
的排查搬到客户端（Eel 前端 + 它直接依赖的两个后端端点）**。
3 个提交，全量 **1026 passed / 0 failed**，UI 冒烟 **85/85**（Playwright 真跑）。

## 方法

通读 `web/js/app.js` 全文（3277 行），每个候选先对照 main.py / controller /
persistence 的真实返回形状做数据流推演再动手（10-06 教训：judge 会误判）。
排除的候选同样记录在案。

## 3 个提交

| 提交 | 修复 |
|---|---|
| `b3251d9` | app.js 八处：工具卡片标签漂移（TOOL_LABELS 9/14 键名对不上 ToolRegistry，`rag_query` 写成 `query_knowledge_base` 等，Agent 模式一直显示英文原始名）→ 改 `get_tools_catalog()` 下发优先；`_renderAgentCards`/`_renderRoadmap` 把 LLM 输出裸拼 innerHTML（与聊天气泡剥 HTML 的口径不一致）→ 统一转义、severity 白名单化；首跑分支漏 `renderQuickActions()`；`onStreamError` 不落库（重启后错误回复消失）；`clearAllData`/`runMultiAgentReview` 漏网的原生 `confirm()/alert()`；审查可经 Ctrl+R 重入；base64 逐字节拼接 O(n²) 卡大文件导入；热力图 resize 监听随重绘堆积 |
| `a37e7a0` | main.py `generate_html_bom` 还在 `Path(__file__).parent` 自行反推 ibom.html —— e3459be 之后双入口反推的最后一处，归一 `default_output_dir()`（当前靠 _MEIPASS 布局巧合一致，实属漂移预备役） |
| `58fa90b` | `load_all()` 会话行补 `message_count`（相关子查询，附加字段）：消息按需加载的设计下，前端所有历史会话徽标恒显 0；前端 `messages.length` 优先、`message_count` 兜底 |

## 学到/踩到

1. **前端手抄映射是漂移高发区**：TOOL_LABELS 的键是按「想象的函数名」写的，
   与 ToolRegistry 差了整整一轮改名。凡是「前端 name→中文」的表，一律让后端
   目录下发 label，前端只留原始名兜底。
2. **fire-and-forget 的代价**：`onStreamDone` 落库而 `onStreamError` 不落，
   这种「同链路两个出口口径不一」靠 review 单个函数看不出来，要成对看。
3. 排除的候选（复核后未改，避免误修）：
   - `save_all_settings` 不带 font_size —— 后端 load→mutate→save，不丢键，
     与 REST 侧 446a0db 那个 bug 不同构；
   - `showDesignSuggestions` 用 `marked.parse` 不剥 HTML —— 内容是
     DesignTemplateEngine 模板生成，无用户/LLM 注入面；
   - 切会话时流未断会不会串话 —— `clearChatMessages()` 先置空
     `_activeStreamBubble`，`onStreamToken/onStreamDone` 的空值守卫已挡住；
   - `main.py` 与 `default_output_dir()` 在 dev/打包两种布局下目前恰好同值，
     但「恰好一致」正是要消灭的状态。
4. `getActiveConversation()` 在空 activeConvId 时会隐式 `newConversation()`，
   依赖这一点做「首条消息自动建会话」—— 动它之前先看 startDemo 的注释。

## 遗留

- `lceda_plugin/`（立创 EDA 插件端，TS）本轮未扫 —— 它是另一个客户端，
  api_client.ts / server_manager.ts 值得按同口径过一遍。
- `frontend/`（Vite/React 模板）疑似废弃实验，与 web/ 无引用关系，可考虑删除。
- spec 打包版仍未实测（10-07 上轮遗留）。
