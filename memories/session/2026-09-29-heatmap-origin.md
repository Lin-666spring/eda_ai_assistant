# 2026-09-29 会话小结：DRC 热力图的数据来源修复

> 起因：用户问「热力图是怎么形成的，并没有上传原理图或者 PCB，是怎么得到的」。
> 查清原理后发现一个真缺口（一键演示 / 只导坐标文件时热力图恒为空），修掉并加了回归。

## 1. 热力图到底是什么（先纠正认知）

**它是一张「违规计数网格」，全程不解析原理图 / 位图。** 四步：

1. 从 `violation.location` 抠位号：`re.findall(r'[A-Z]+\d+', v.location.upper())`
2. 查「位号 → 坐标」表（mm）
3. 按 `grid_size_mm` 分桶：`bx = int((x - x_min)/g)`，`x_min = min(xs) - g`（包围盒各留一格边距）
4. 交给 ECharts heatmap：`[[bx, by, count], ...]`，颜色 = 该格落了几条违规

推论（回答用户时要讲清的诚实边界）：

- **没上传任何东西时热力图必须是空的** —— 这是正确行为，不是 bug；
- 坐标轴上 `#4`、`#7` 是**网格序号**，不是 mm；
- 一条违规点名两个位号会在两个格子各 +1 → **计数合计可以大于违规条数**；
- 原理图（`.epro2` 的 SCH）从未被解析；PCB 也只用到「元件坐标 + 走线/过孔/层」的几何量。

## 2. 查出来的真缺口

`get_heatmap_data()` 只读 `pcb_data.component_positions`，而坐标文件（Pick & Place）
加载进来放在 `ctx.positions` —— 同一份 ref→(x,y) 数据两个字段，热力图只认其中一个。
后果：**一键演示（`sample_bom_bad.csv` + `sample_positions.csv`）恒返回 `[]`**。

实测（修复前）：

| 场景 | 输入 | 违规 | 坐标 | 热力图 |
|---|---|---|---|---|
| A 一键演示 | BOM + POS，无 PCB | 8 条（4 条带位号） | 23 个位号 | **`[]`** |
| B 导入 `.epro2` | ESP32 大杂烩工程 | 22 条 | 134 个元件坐标 | 6 格，最密 8 条 |

## 3. 修复（本次提交）

- `src/rules/checker.py`
  - 新增 `build_heatmap(violations, grid_size_mm, positions)` → `{data, grid_size_mm, source, x_min, y_min, violation_count, mapped}`；
  - `_resolve_positions()`：**PCB `component_positions` > 坐标文件**（PCB 那份与网络/走线同源，优先）；
  - `check_all()` 记住 `positions`，`get_heatmap_data()` 退化成兼容壳；
  - `_normalize_grid_size()`：非法/非正回落 5mm，夹到 [0.5, 200]（防除零）；
  - `_extract_xy()`：坐标缺 x/y、非数值的位号直接跳过（原来 `pos.get("x", 0)` 会把它算到原点）。
- `src/core/controller.py`：新增 `get_drc_heatmap()` 唯一入口，返回 `reason` =
  `no_data` / `no_positions` / `no_violations` / `unmapped`（前端据此给不同文案）。
- `main.py` + `src/api/endpoints.py`：删掉两份重复实现，都委托 controller。
- 前端：网格边长下拉（2/5/10/20mm，onchange 重新统计）、描述写明「位置来源 + N 处计数 / M 条违规」、
  tooltip 把网格序号换算成真实 mm 区间、空状态按 reason 给文案。

修复后场景 A：`source=positions`，3 格 / 6 处计数 / 8 条违规（实机 UI 验证同值）。

## 4. 回归

- `tests/test_heatmap.py`（新，17 例）：坐标文件回落、PCB 优先（看 `x_min` 而非格子序号，
  否则两种来源会给出相同格子而测不出优先级）、`check_all` 记忆 positions、网格归一化、四种 reason。
- `tests/ui_smoke.py`：新增 **P15**（5 项）——真实后端出格 + 描述含来源/计数、网格边长透传（拦截
  `eel.get_drc_heatmap` 收参数）、空状态三种文案；跑 **74/74**。
  - 注意 P14 里那次真实 `import_bom_file('_smoke_bom.csv')` 会把上下文换成单行 BOM，
    所以 P15 开头要重新 `await eel.load_demo_data()()` 才能测「演示数据出图」。
  - 顺手修了冒烟自身的误判：`Failed to load resource` 这类控制台错误 `m.text` 里**没有 URL**，
    离线时 CDN 断连会被算成"本地 JS 错误"。现在用 `m.location.url` 判定并转 warn。

## 5. 顺带记下（未做）

- `index.html` 的 ECharts 走 `cdn.jsdelivr.net`，离线时图表不渲染（只出数据/文案）。要彻底离线可用得把
  ECharts 落到本地 `web/vendor/`。
- 网格边长写死在 `get_drc_heatmap(grid_size_mm=5.0)` 默认值上，现在前端可选，但**后端没有按板子尺寸自适应**。
