# 会话小结 — 2026-10-07（代码级缺陷清扫：双入口漂移 / 线程安全 / 静默失效）

主题：**延续 10-06 晚的 API 修复（SSE 竞态、settings 键名、/llm/test 漂移），
按同一口径继续排查**。6 个提交，全量 **1025 passed / 0 failed**（本机真跑，
非沙箱口径）。

## 方法

上一轮 5 个修复提交已暴露问题模式：**Eel(main.py)/FastAPI(src/api) 双实现漂移、
settings 键名不一致、线程池下共享状态竞态、读到启动时缓存不刷新**。
本轮逐文件对照 main.py ↔ src/api/endpoints.py ↔ controller，每个候选先
做数据流推演排除误报（学 10-06 教训：judge 会误判，改前必须自己复核）。

## 6 个提交

| 提交 | 修复 |
|---|---|
| `e3459be` | `/bom/generate-html` 用 `Path.cwd()` 反推 ibom.html 位置，controller 却写到项目根 output/ —— 换目录启动 path 恒空串。抽 `controller.default_output_dir()` 作唯一来源（controller 两处导出 + REST 端点共用） |
| `88dd4ab` | `reconfigure_llm` 只换 controller.agent，不回写 `config.llm`（导入时读一次 settings.json 的缓存）→ `get_llm_config`（Eel）/`GET /llm/config`（REST）永远显示启动时旧配置。现在镜像客户端实际生效值（空值按 resolve_provider 预设解析） |
| `9930f93` | `_write_temp` 文件名未消毒：`tmp / name` 直接拼，`..\..\x.csv` 可写到临时目录外。REST 侧 CORS `*`，浏览器任意页面可远程触发。`Path(name).name` 拍平，main.py/endpoints.py 两份同修 |
| `a13a51b` | `get_controller`/`_get_store` 惰性单例无锁 —— 同步端点跑 FastAPI 线程池，并发首请求建双实例、状态分裂。双检加锁（同 `_ensure_rag_indexed` 先例），12 线程带屏障回归 |
| `446a0db` | REST `POST /settings` 收 font_size 却从不落盘（Eel 走独立 save_font_size 所以没暴露） |
| `fc4f114` | spec datas 补 `tests/sample_*.csv` —— 打包版一键演示两个入口都必然 FileNotFoundError。**只校验 spec 语法，未跑完整 PyInstaller 构建** |

## 学到/踩到

1. **deepseek 预设默认模型是 `deepseek-flash`** 不是 deepseek-chat —— 新增测试
   断言先查 constants.py 别凭印象写。
2. `Path(name).name` 在 Windows 上同时吃掉 `/` 和 `\`，本项目（win32 打包）
   一行就够；别为理论上的 POSIX 部署加 ntpath 复杂度。
3. AnthropicClient 会把 base_url 补成 `.../v1/messages`，而 claude 预设本来就是
   该 URL —— 镜像客户端值回 config.llm 后两边恰好相等，回归测试把这条钉住。
4. 全量 1025 passed 是**本机不受限环境**的数字；沙箱里的
   "10 failed / 76 errors" 全是 PermissionError 噪音，对比时注意口径。
5. 复核排除的候选（未改，避免误修）：
   - streaming.py 对 `agent_loop(text, on_token, 5, on_tool_call)` 的位置参数
     与签名一致，不是 bug；
   - `import_bom_from_lceda` 临时文件不清理 —— `context.bom_file` 还指向它，
     虽然目前只用 stem，动它收益小风险大；
   - `verify_suggestion`/`health/electrical` 异常直接 500 —— 与 Eel 侧行为
     一致（promise rejection），不算漂移。

## 遗留

- spec 打包版未实测（含 pynput/pystray 隐式导入是否被静态分析捕获）。
- `controller.agent` 仍是共享单客户端：Eel + REST 并发 `agent_loop` 会互相
  覆盖 `tool_executor`、混写 history —— 架构级，需要会话级客户端池才能解。
- audit-findings.md 里 10-06 第二轮抽查的 30 条判据问题仍是主体
  （阻抗 295 条待重新抽查判读、存在性/子串 → 网表那一类）。
