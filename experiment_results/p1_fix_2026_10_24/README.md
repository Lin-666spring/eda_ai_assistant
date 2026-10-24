# P1 修复批（2026-10-24）

- **范围**: 验收报告第三节 P1 全部 25 条（编号 1-22、25、26、27；P1-23/24 已由 a9 批次先行落地，核实后排除）。
- **模式**: 子代理修复（`p1-fixer`，GLM-5.3-Flash + thoughtLevel max）+ 主代理逐条代码审查验收。按文件互不重叠分 5 批并行（账号并发上限 2，实际排队串行补发）。
- **修复前快照**: 本目录 `pre/`（23 个待触碰文件的批前副本）+ `pre_git_status.txt`（范围核对基线）。

## 批次与条目

| 批次 | 条目 | 触碰源文件 | 新增测试 |
|------|------|-----------|---------|
| A | P1-1~4（agent：工具异常/重试锁/NLU 评分表/MP 短词） | anthropic_client / nlu_engine / design_templates | test_p1a_batch_a.py（19） |
| B | P1-5~12,20（core：dispatch 参数/评分重复键/串扰真实几何/连接 close/TOCTOU/save_all upsert/trailing 防抖/CSV 注入） | tools / controller / design_scorer / electrical_check / persistence / file_watcher | test_p1b_batch_b.py（27） |
| C | P1-13~17（rules/pcb：EIA 记法/电容单位感知/跨格间距/底层镜像/电压轨 token） | base / bom_rules / layout_rules / epro2_parser | test_p1c_*.py（44） |
| D | P1-11,18,19,21（api/supply/rag：Eel 兜底/反 CSRF+TrustedHosts/BOM 健康降级并发/RAG 响亮失败+清旧 chunk） | main.py / api/{server,endpoints} / bom_health / rag/indexer | test_p1d_*.py（50） |
| E | P1-22,25,26,27（web/ml：前端竞态三连/LOOCV+特征修复/报告栈条件入栈/iframe sandbox） | web/js/{chat,stream,conversations,tools} / index.html / change_predictor | test_p1e_*.py（~14） |

P1-16 镜像轴按 78 板金样实测钉死：底层焊盘先 Y 镜像再旋转，与同网底层走线端点重合 4754/73 失配（不镜像 3050/7261 失配）。

## 主代理验收

1. **逐条代码审查**: 25/25 通过。重点复核：P1-18 去 `null` 不破坏 lceda 插件（面板实为 `/static/iframe/panel.html` 同源自挂，`dist/main.js:30`）；P1-21 内容寻址 chunk ID + 「记旧→写新→删差集」顺序；P1-3 分母锚定原始表防补充词稀释；P1-22 发起会话绑定 + 气泡身份比对全覆盖四条异步路径。
2. **客观验证**: `compileall` main.py+src 干净；全量 pytest **1487 通过 / 0 失败**（a9 批后基线 1336 → +151 新回归测试）。
3. **金样重定基**: 批次C 判据修正后重算，仅 **铜皮连接检查 29→28**（P1-16 底层焊盘坐标修正的边界影响），总触发数 1547→1546；P1-13/14/17 在金样语料零触发样本、零漂移。`_SNAPSHOT` 已同步（铜皮连接检查 28），`golden_new_counts.json` 存本目录。
4. **跨批次集成修复**（主代理执行）: 批次D 移除嵌入回退后 `tests/test_pcb.py` 6 条 RAG 测试直连外网 401 → 改离线确定性字符 bigram 词袋假嵌入（`_FakeBagEmbed`，autouse fixture），64 条全过，测试不再依赖外网/配额。
5. **范围核对**: 对 `pre_git_status.txt` 差分，新增改动 31 项全部落在批次授权清单内（含 `data/change_risk_model|report.json` 重训产物、`data/test_change_risk_report.json` 为测试运行再生成产物）。

## 遗留跟进（不阻塞验收）

1. P1-3 备注：纯关键词降级路径（无本地 BERT 且无 embedding 双兜底）「计算走线宽度」classify 置信度 0.332 仍低于 0.40 门限（意图已正确）；抬分需动 classify 中置信差距乘法，属共享行为未动。
2. P1-21 语义变化：未配置 SILICONFLOW_API_KEY 时索引为空（响亮失败，不再回退 MiniLM）——检索端点降级 ok=False，属有意设计。
3. P1-19 健康分语义：network_error 项每项 -2 分（查不出的物料不能按满分计）。
4. P1-25：闭环预检调用方（paper_experiments.py）尚未传 existing_violations，末两维信号待调用侧接入；n=73 下二分类处于基率水平，需更多闭环数据。
5. P1-10 备注：save_all 的 conversations 清空重写路径仍休眠未动。
6. 破坏性 REST 端点（/clear-all-data、/settings、/llm/config、DELETE /persist/*）现要求 `X-Requested-With: XMLHttpRequest` 头；经核实 web/js 与 lceda 插件均不调用这些端点，无前端破坏面。
