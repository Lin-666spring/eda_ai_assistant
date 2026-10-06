# 规则抽查判读须知 · 第二轮（2026-10-06，修复后）

> 与 2026-09-18 第一轮**逐字相同的四分类口径**，便于两轮直接对比。
> 第一轮结果：总体精确率 7.7%（95% CI 3.8~15.0%），走线类 11.1%，非走线类 5.5%。

## 1. 你手上是什么

分层抽样的违规样本：**每条规则抽 5 条（走线类）/ 2 条（其它）**，所以样本里各规则
条数不代表违规率，**不要**据此推断某规则「报得多」。

每条样本字段：

| 字段 | 含义 |
|---|---|
| `id` | 样本 id（判读结果必须用它做键，逐字一致） |
| `design.file` / `design.title` | 来自哪个真实工程（`test_data/_incoming_epro2/`） |
| `design.ctx` | 该板概况：元件/网络/走线/过孔数、层数、板框尺寸、线宽分布 top3 |
| `rule_func` / `rule_name` | 规则函数名 / 中文规则名 |
| `severity` | 该条违规的告警级别 |
| `description` / `location` / `suggestion` | 规则给出的描述、位置、建议（**可能不准，必须核实**） |
| `evidence` | dump 脚本为该规则专门补的证据（走线类基本都有；部分规则为空） |

## 2. 四分类（每条只能选一个）

- **TP** 违规成立：证据支持判据，且这是这块板上**真该改**的问题；
- **FP** 误报：判据/几何/数据用错，或该处根本不是问题；
- **GEN** 通用提示：不是对这块板的判定（任何板都会响、无法证伪）——既不算对也不算错；
- **UNC** 无法定性：需要规则之外的信息（信号速率、叠层、BOM 真值）才能判。

精确率 = TP/(TP+FP)，Gen/UNC 单列，另报「UNC 全算误报」的保守下界。所以：

- 「判据本身没错，但这条落点不是问题」→ **FP**（不是 GEN）；
- 「这条规则的结构注定在任何板上都报」→ **GEN**；
- 拿不准且缺信息 → **UNC**。**不要为了凑 TP 而猜**，也不要把明显误报洗成 GEN。

另填 `s`：`"yes"` 告警级别合适 / `"no"` 严重度偏高（例如 INFO 级的事报成 WARNING/ERROR）。

## 3. 怎么核实（不要只看 description）

1. `evidence` 里通常已经有关键几何（角度、腿长、间距、线宽、层、位号、距离）。
2. 不够时自己解析原始数据（零 API、零网络）：

```powershell
$env:PYTHONIOENCODING='utf-8'; python -X utf8 -c "import sys; sys.path.insert(0,'.'); from src.pcb.epro2_parser import Epro2Parser, bom_rows_to_items; from scripts.epro2_rule_coverage import build_inputs; pcb=Epro2Parser().parse('test_data/_incoming_epro2/<文件>.epro2'); bom,pos,netlist,_=build_inputs(pcb); print(len(pcb.traces), len(pcb.vias), len(pcb.nets))"
```

   常用：`pcb.traces`（走线折线：net/layer/width/points）、`pcb.vias`、`pcb.nets`（网络→引脚）、
   `pcb.component_positions`（位号→x/y/层/封装）、`pcb.bom_items`、`pcb.copper_pours`、`pcb.board_outline`。
3. 规则实现：`src/rules/checker.py` 里搜 `rule_func` 的名字（`_check_xxx`），看判据、门限、守卫。
4. 计算类：`src/pcb/calculator.py`（IPC-2221 载流/线宽、微带线阻抗）、`src/pcb/geometry.py`（拐角串联）。

## 4. 第一轮已确认的量则（**沿用，不要重新发明**）

- **差分对长度**：接口对偏斜不敏感（音频功放、直流输入、USB2 且偏差 <2% 位周期）→ FP；
  组内极差 ≥2mm 或 ≥10% 走线长度（与设计者显式声明的等长/差分约束明显矛盾）→ TP。
- **差分对间距**：3.0~4.5W 属阈值边界 → FP；≥4.5W 明显松耦合 → TP；**靠名字猜出来的配对一律 FP**。
- **串扰**：线对里主要是电源/地、或全是低速网络（按键、蜂鸣器、32kHz、GPIO）→ FP；
  线对性质无法判定（`$1N*` 无名网络、开关节点混排）→ UNC。
- **拐角**：**逐条看该违规对应的那一个拐角**（不是看网络汇总）——腿长 <0.5mm 且离焊盘/过孔 <1mm
  判为焊盘入口几何 → FP；直角规则只输出 INFO 且规则自述「低速线可接受」→ GEN。
- **提示类规则**（`checker.ADVISE_RULES` 里的 14 条，如丝印可读性、丝印焊盘间距、地平面连续性、
  光学 Mark 点、测试点覆盖）：结构上就是「每板必响」，若无具体位置证据 → GEN。

## 5. 本轮背景（判读时注意）

- 本轮数据是 **2026-09-29 判据修复 + 2026-10-02 netlist 契约修复之后**的（违规总数 5769 → 3241）。
  第一轮报出的那些误报模式（电源载流按内层降额、E24 表 10× bug、裸子串命中器件类型、
  去耦配对数当电容数、未连接引脚恒报 …）**应当已经修掉**；
  若你仍看到同类问题，如实判 FP 并在理由里点名。
- 所以**不要**照抄第一轮结论：一条条看你自己的证据。

## 6. 产出

写到 `experiment_results/rule_spotcheck_2026-10-06/verdicts_<你的批次名>.json`：

```json
{
  "49d3ac69809d-trace_acute_angles-4": {"v": "FP", "s": "no", "r": "该拐角腿长 0.516mm…距 C65 焊盘 0.5mm，属焊盘入口几何"},
  "...": {"v": "TP", "s": "yes", "r": "…"}
}
```

- **id 必须与样本文件逐字一致**（拼错 = 该样本静默丢失）；
- 每条都要有 `v`；`s`/`r` 尽量填全（`r` 引用具体数值，便于复核）。
