# 记忆索引 (Memory Index)

> 由 context-memory 技能维护 | 最近更新 2026-10-07
> DSH 不会自动加载本目录，`CLAUDE.md` 里有指针。

| 文件 | 内容 |
|---|---|
| [session/2026-10-09-substring-criteria.md](session/2026-10-09-substring-criteria.md) | 会话小结：**子串/存在性判据主体收口（§4B）**——差分对两半不判串扰、差分间距高速门控+重叠前置、BOM 五规则改位号前缀、ESD/EMI/反接入口号表化、裸 rf/op/SW 词边界+家族料号前缀；金样 3301→3202、无关规则零变化；磁珠/EMI/I2C「变多」判读=识别变对暴露新触发集；1100 passed |
| [session/2026-10-07-frozen-build-and-session-pool.md](session/2026-10-07-frozen-build-and-session-pool.md) | 会话小结：**打包版实测 + 会话级客户端池**——frozen 写盘路径三处缺陷（导出/日志/RAG 落 _MEIPASS 退出即丢）、构建入口统一到 spec、`_llm_session()` 租借（并发 agent_loop 不再互相覆盖/审查轮次不进对话史）、ui_smoke 失败标记不可见的教训；2 提交 1038 passed 85/85 |
| [session/2026-10-07-client-sweep.md](session/2026-10-07-client-sweep.md) | 会话小结：**客户端缺陷清扫**——Agent 工具标签漂移/审查渲染注入/流式错误不落库等 8 处、generate_html_bom 目录归一、load_all 补 message_count；3 提交 1026 passed、UI 冒烟 85/85 |
| [session/2026-10-07-code-review-fixes.md](session/2026-10-07-code-review-fixes.md) | 会话小结：**代码级缺陷清扫**——双入口漂移/config.llm 缓存/路径穿越/单例竞态，6 提交 1025 passed |
| [epro2-format.md](epro2-format.md) | 立创EDA V3 `.epro2` 格式、解析器实现与 78 工程实测（含四个实现坑） |
| [experiment-status.md](experiment-status.md) | 真实 PCB 数据集实验结果、指标、复现命令 |
| [audit-findings.md](audit-findings.md) | 项目"不符合预期"清单与修复状态 |
| [session/2026-10-06-spotcheck-round2.md](session/2026-10-06-spotcheck-round2.md) | 会话小结：**提交积压 + 覆盖率复测 + 抽查第二轮**——3 个提交（hunk 级拆分）、违规 3293→3241、**精确率 7.7%→6.5%（无提升）**、30 条判据缺陷清单、4 个代码 bug |
| [session/2026-10-03-two-stage-boot.md](session/2026-10-03-two-stage-boot.md) | 会话小结：**两段式启动**——480×340 小窗先出、重活丢后台线程、`BootSequencer` 状态机、`resizeTo` 被拒走兜底；eel 的 `size=` 其实是 `resizeTo`、`hidden` 挡不住 `display:block` 两个坑；UI 冒烟 74→85 |
| [session/2026-10-02-batch-a.md](session/2026-10-02-batch-a.md) | 会话小结：**口径统一 + 门禁修复**——netlist 契约(dict，从 pcb_data.nets 反推)、check_all 记 rule_errors、EDA_AI_HOME/SessionStore 父目录、endpoints 惰性开库；965 collected、910 passed/0 failed |
| [session/2026-09-29-heatmap-origin.md](session/2026-09-29-heatmap-origin.md) | 会话小结：**热力图来源修复**——它是违规计数网格（非图像）、位置来源 PCB>坐标文件回落、四种 reason、UI 冒烟 69→74 |
| [session/2026-09-29-ui-loading.md](session/2026-09-29-ui-loading.md) | 会话小结：**前端加载动效**——setStatus 落地（原来是空实现）、思考气泡三点+计时、审查骨架屏，UI 冒烟 57→68 项 |
| [session/2026-09-29-summary.md](session/2026-09-29-summary.md) | 会话小结：**按抽查报告把判据修完**——11 处修复 + 判定类口径 B′，违规 4944→3293、耗时 347s→58s |
| [session/2026-09-18-summary.md](session/2026-09-18-summary.md) | 会话小结：激活走线锐角/直角规则 + 拐角校准 |
| [session/2026-09-18-rule-spotcheck.md](session/2026-09-18-rule-spotcheck.md) | 会话小结：**规则抽查**——150 条分层抽样，走线类精确率 11.1%、非走线类 5.5%，确认 15 条判据 bug |
| [session/2026-09-15-summary.md](session/2026-09-15-summary.md) | .epro2 接入、规则覆盖率、阈值校准、前端改版 |
| [session/2026-09-13-summary.md](session/2026-09-13-summary.md) | 上次会话小结（.epro2 调研 + thing_designs 实验） |
