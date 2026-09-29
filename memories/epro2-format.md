# 立创EDA V3 `.epro2` 格式与解析要点

> 2026-09-15 更新：解析器已实现并**在 78 个真实工程上验证通过**
> 解析器：`src/pcb/epro2_parser.py`（`Epro2Parser`）
> 官方规范：`.specs/v3/lceda-pro-file-format-v3_2025.10.21.md`（已 gitignore）

## 格式结论

- `.epro` = V2 客户端格式；`.epro2` = V3 客户端格式（全新、日志式 key-value，与 V2 完全不同）
- `.epro2` 本质是 ZIP：`project2.json`（元信息）+ `<工程名>.epru`（工程日志 JSON Lines）+ `IMAGE/*.webp`
- **一个 `.epro2` = BOM + 网表 + 坐标 + 走线/过孔/覆铜**，是四种下游导出的超集，不需要 Gerber

## `.epru` 行格式

每行：`{meta}||{原子对象}|`

- meta 形如 `{"type":"LINE","ticket":706,"id":"e61"}`；`type` 恒为首键，
  可用正则 `^\{"type":"([A-Za-z0-9_]+)"` 快速取，避免逐行 json.loads
- 解析：`split("||", 1)` 后必须 `rstrip("|")` 再 `json.loads`
- **文档边界靠 `DOCHEAD` 元素**（含 `docType` / `uuid`），元素按出现顺序归属最近 DOCHEAD。
  DOCHEAD 的 meta **没有 id**，身份在 atom 的 `uuid` 里
- docType：PCB / BOARD / SCH / SCH_PAGE / SYMBOL / DEVICE / FOOTPRINT / CONFIG / FONT / BLOB / PANEL

## 四个实现坑（都已解决，别再踩）

### 1. 几何数值单位是 **mil**，`CANVAS.unit` 不可信

`CANVAS` 里写的 `"unit":"mm"` 只是**界面显示偏好**：实测 46 个工程写 `mm`、32 个写 `mil`，
但数值一律是 mil。判据：立创默认过孔 `holeDiameter=11.811 / viaDiameter=19.685`
→ 0.3mm / 0.5mm（若按 mm 解释是 11.8mm 钻孔，物理上不可能）。

**铁证（外部验证）**：泰山派 3M 的 947 个位号坐标 ×0.0254 后与官方 PickAndPlace
逐点比对，中位误差 **0.0003mm**，947/947 在 0.05mm 内，旋转 947/947 一致。
换任何其它系数都做不到这个精度。

解析器只做一次 sanity check：过孔钻孔中位数 <2 视为本来就是 mm，不换算。

### 2. PCB 文档里没有 PAD —— 焊盘在 FOOTPRINT 文档

- PCB 的 `COMPONENT`（meta id 如 `e1`）本身只有位置/角度/层；
  **位号与封装靠它的子 `ATTR`**：`parentId=e1`，`key="Designator"/"Device"/"Footprint"`
- `ATTR.Footprint` 的值是 **FOOTPRINT 文档的 uuid**
- FOOTPRINT 文档的 `META.title` 才是真正的封装名（如 `C0201_2`、`QFN-68_L7.0-W7.0-P0.35-BL-EP5.5`），
  比 DEVICE 里的 `Supplier Footprint`（`0201`，JLCPCB 口径）更有用

### 3. 网络归属走 `PAD_NET`，且焊盘号要二次解析

`PAD_NET` 的 meta id = `["PAD_NET", <元件id>, <焊盘号>, <焊盘元素id>]`，atom 的 `padNet` 是网络名。
`NET` 元素本身只存 `differentialName` / `equalLengthGroupName`（差分对/等长规则）。

**坑**：BGA/字母焊盘（A1/B2/N9…）时，第 3 段会**退化成元素 id**（如 `"e220"`）。
必须用 `(封装 uuid, 焊盘元素id)` 查 FOOTPRINT 文档里的 `PAD.num` 还原真实焊盘号，
否则泰山派 3M 会出现 1215 个假引脚名。

**孤儿记录**：还有极少数 PAD_NET 的焊盘元素在**所引用封装里根本不存在**（实测 3M 有
13 条指向 U10 的 LPDDR5 封装，却挂在 U2 名下）。立创自己的网表导出也丢弃它们 ——
解析器同样丢弃，并在 `metadata["orphan_pad_nets"]` 计数。

### 4. BOM 字段在 `DEVICE` 文档的 `META.attributes`

不是实例 ATTR。关键字段：`Supplier Part`(C1523) / `Manufacturer Part` / `Manufacturer` /
`Value` / `Supplier Footprint` / `LCSC Part Name` / `Add into BOM`(=no 要排除)。
BOM 以「同一器件」为一行、位号合并；官方 BOM 的 `Footprint` 列 = FOOTPRINT 文档 title。

### 5. BOM 的「加入 BOM」开关写在**实例**属性上，不是库属性

`PCB COMPONENT` 原子的 `attrs` 里有用户逐件设置的状态（`Add into BOM: "no"` 等），
而 DEVICE 库属性里同名键始终是 `"yes"`。**只看库属性会多算**：
实测泰山派 3M 多算 62 个位号（947 vs 官方 885）。

按「实例优先、库属性兜底」过滤后：BOM 覆盖位号 **885 = 885**，
器件组位号集合 **154/154 完全一致**，封装名 151/154 有交集。

解析器把逐件状态也写进了 `component_positions[ref]["in_bom"]`。

## 多边形 path 格式（BOARD_OUTLINE 等）

规范（`R` 与 `CIRCLE` 是**独立模式**，不兼容其它）：

| 形式 | 含义 |
|---|---|
| `X0 Y0 L X Y X Y ...` | 点列，可混 `ARC`/`C` |
| `ARC angle endX endY` | **顺序是 angle 在前**（规范正文与真实数据一致，规范里的示例是错的） |
| `C x2 y2 x3 y3 x4 y4` | 三阶贝塞尔，末点为终点 |
| `R X Y width height rot round` | 矩形，绕 (X,Y) 旋转 |
| `CIRCLE cx cy r isCCW` | 圆 |

**坑**：`R` 矩形的落点在工程间不一致 —— 泰山派 3M 的 `R` 装不下自己的铜
（Y 偏了一个板高）。解析器做了包含性校验：板框必须装下全部铜，否则退回铜包围盒，
并在 `board_outline["source"]` 标 `outline`/`copper`。

## 实测数据（78 个工程，2026-09-15）

`experiment_results/epro2_dataset/`（`manifest.json` / `manifest.csv` / `summary.txt`）

| 项 | 合计 |
|---|---|
| 工程 | 78（解析成功 78，失败 0） |
| 唯一设计（指纹去重） | 76（PowerPico、承载我所有幻想的键盘 各有 (1) 重复） |
| 网络 / 有引脚网络 | 10273 / 9870 |
| 引脚 | 44047 |
| 走线折线 / LINE 元素 | 14811 / 172244 |
| 过孔 | 37807 |
| 覆铜 | 1317 |
| 元件 / BOM 行 / BOM 位号 | 11437 / 4180 / 12890 |
| 解析耗时 | 12.4s（平均 0.16s/工程） |

3M RK3576 板：947 元件、668 网络、1320 折线（24122 LINE）、2052 过孔、51 覆铜、
板框 84.0×56.2mm。

## 解析器产出（PCBData）

`src/pcb/models.py` 的 `PCBData` 新增 `bom_items` / `metadata` 两个字段。

- `format = "lceda_epro2"`
- `nets`：网络 → 引脚 `位号.焊盘号`（来自 PAD_NET），含 `trace_count` / `total_length_mm`
- `traces`：**按 (网络, 层) 聚合成折线**（不是一段一个对象！否则 3W 串扰规则是 O(n²)：
  泰山派 24122 段会跑到 2.9 亿次比较直接卡死），坐标 **mm**
- `vias`：pos(mm) / drill_mm / pad_mm / 层 / 网络
- `copper_pours`、`layers`（只保留实际用到的层）、`board_outline`、`differential_pairs`
- `component_positions`：位号 → x/y(mm)/rotation/层/side('T'/'B')/device/footprint/footprint_name/value/part_number
- `bom_items`：BOM 行（dict），`bom_rows_to_items()` 转 `BOMItem`
- `metadata`：title/editor_version/unit/scale_to_mm/元素计数/orphan_pad_nets…

## 接入点

- `create_parser()` 认 `.epro2` → `Epro2Parser`（延迟导入）；`PCB.SUPPORTED_PCB_FORMATS` 已加 `.epro2`
- `eda_adapter.get_pcb_data` → 自动走通（`load_pcb` 已支持 .epro2）
- `AppController.load_project()`：一次解析同时填 `bom_items` + `pcb_data`
- `main.py` 新增 `@eel.expose import_project_file`；前端 `pcbFileInput` accept 加 `.epro2`，
  `.epro2` 走 `import_project_file`（同时渲染 BOM 表）

## 验证手段（可复现）

```bash
# 全量解析 + 数据集清单
python scripts/build_epro2_dataset.py test_data/_incoming_epro2

# 与官方四种导出交叉验证（需同工程的导出目录）
python scripts/validate_epro2_vs_exports.py \
  --epro2 "test_data/_incoming_epro2/78/ProPrj_立创·泰山派3M（RK3576)开发板_2026-09-14.epro2" \
  --exports "test_data/thing_designs/立创·泰山派3M(RK3576)开发板V1.4"

# 解析器单测
python -m pytest tests/test_epro2_parser.py -q
```

泰山派 3M 交叉验证结论（`experiment_results/epro2_validation/3M_V14.txt`）：

- 元件：947/947 位号、层全对、坐标中位误差 0.0003mm、旋转全对
- 网络：667 个同名网络，**667/667 引脚集合完全一致（100%）**，Jaccard 中位数 1.000
- BOM：位号 **885 = 885**，器件组 **154/154** 位号集合完全一致（修掉实例属性坑之后）

## 规则覆盖率（零 LLM 实验）

`scripts/epro2_rule_coverage.py` → `experiment_results/epro2_rule_coverage/`

方法：用 AST 抽出每条 `_check_*` 开头的「数据不足就 return []」守卫条件，再用真实输入求值，
精确判断规则**是否真的做出了判断**（而不是靠猜）。

| 配置 | 口径 A 可判定 | 口径 B 有输出 | 违规总数 |
|---|---|---|---|
| C1 旧口径（四种导出：BOM+坐标） | 50/71 = 70.4% | 39/71 = 54.9% | 2215 |
| C2 +PCB 元件/网络（无铜） | 56/71 = 78.9% | 45/71 = 63.4% | 2621 |
| C3 全量 `.epro2` | **71/71 = 100%** | **61/71 = 85.9%** | 5769 |

> 2026-09-15 走线类阈值校准后：口径 A 仍 71/71、口径 B 仍 60/71，但违规总数 **8394 → 4000**。
> 对比表：`experiment_results/trace_threshold_calibration/coverage_before_after.txt`
>
> 2026-09-18 激活 `_check_trace_acute_angles` 后：口径 B **60/71 → 61/71 = 85.9%**，
> 违规总数 4000 → **5769**（多出的 1769 条全部来自新启用的走线锐角 WARNING / 走线直角 INFO）。

- **21 条规则被 `.epro2` 新解锁**（6 条只要有 pcb_data 即可，15 条要真实走线/过孔/覆铜）
- 全量下**没有任何规则因数据不足被拦下**
- 旧记忆里的「30/71」是**口径 B（有输出）**在 thing_designs 上的值；换到 `.epro2` 数据是
  39→60，口径 A 是 50→71。引用时务必写明口径。

### 顺带挖出两个规则 bug

1. **`_check_impedance_matching` 从未生效**：用了 `math.sqrt` 却没 `import math`，
   一旦要报违规就 NameError，且被 `check_all` 的 try/except 静默吞掉 → 已修。
   教训：覆盖率实验必须单独统计「规则执行异常」，否则死规则看起来像「这块板很干净」。
2. **`_check_trace_acute_angles` 是死代码**（判据 `t.has_sharp_angle` 无人设置）→ **2026-09-18 已修**。
   激活方式：新增 `src/pcb/geometry.py` 做**规则侧端点串联**（空间哈希 + 并查集 → 按图论度数切折线
   → 内角），不动解析器的 `segments` 模型。注意两个坑：同一 (网络,层) 的 LINE 线段不按路径顺序记录
   （实测相邻线段端点相接比例仅 7%~48%），且**存在重复线段**（1331 段里 77 段重复），不去重会串出假 0° 折返。

## 走线类阈值校准（2026-09-15，已完成）

`scripts/calibrate_trace_thresholds.py`（零 LLM/零网络，28s）统计 76 个设计的原始度量，
阈值集中在 `src/constants.py: PCBConstants`。

| 规则 | 阈值 before | 阈值 after | 命中 before → after（C3，76 设计） |
|---|---|---|---|
| 信号线宽度检查 | 0.2mm 固定 | **0.1mm 工艺下限 或 本板主流线宽×0.6（两级）** | 4005 → **268** |
| 过孔密度检查 | 所有网络 ≥5 个 | **仅高速网络 ≥5 个** | 646 → **27** |
| 走线板边间距检查 | 0.5mm + 拿绝对坐标当板边（bug） | **0.3mm + 真实板框包围盒** | 47 → **1** |
| 差分对间距检查 | 只报「识别到 N 对」 | **对内最小间距 >3W** | 52 → **15** |
| 差分对等长检查 | 5mil，名字猜配对 | **0.5mm，工程 NET 规则分组** | 58 → **135** |
| 3W 串扰间距检查 | 首点距离 + 每层 >3 对 | **线段距离 + 平行重叠 ≥5mm** | 61 → **192** |
| 时钟包地检查 | 每 (网络,层) 都报 | **按网络去重** | 401 → **238** |
| 合计（C3 全量） | — | — | **8394 → 4000（-52%）** |

口径 A 可判定 71/71、口径 B 有输出 60/71 均**不变**。

关键实测（`experiment_results/trace_threshold_calibration/report.txt`）：

- 每网络最小线宽（信号）p5=0.1016 / p25=0.1422 / p50=0.2mm；实测设计大量用 4mil(0.1016)
- **本板信号线宽众数**（76 块板）p25=0.1524 / p50=0.2032 / p75=0.254mm —— 多数板有意用 6~10mil，
  所以「固定 0.127mm」会把整板用 4.8mil 的专业板（立创泰山派3M）一次报 501 条。
  改为「细于 0.1mm **或** 细于本板众数×0.6」两级判据后，该板不再被整体误报，
  命中降到 268 网络 / 8 设计
- 每网络过孔数 p50=2 / p90=6 / p99=128，最大 1131（GND 缝合孔）→ 原规则对全部网络生效是主嫌
- 40 个有真实板框的设计：走线到板框最小 0.292mm，<0.3mm 仅 2 条折线
- 工程 NET 规则里 ground truth 差分对 576 组（49 个设计有），对内间距/线宽 p50=2.10W、p95=3.0W
- 只用最短距离判 3W：74/74 个设计全中（交叉处必然接近）；要求平行重叠 ≥5mm 后降到 34 个设计

## 下一步

- [ ] 用 `.epro2` 数据集跑真实实验（DRC 覆盖率、缺陷注入），替换/扩展现有 thing_designs 实验
- [ ] 解析器加端点串联（激活 `_check_trace_acute_angles`，并让 `segments` 真正有序）
- [x] 走线类规则用真实数据校准阈值（见上；下一步可校准闭环收敛 / ML 置信度阈值）
