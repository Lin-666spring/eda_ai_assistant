# 违规噪声清扫金样对比（2026-10-09）

## 背景

用户反馈「实际材料跑出来的违规有点多、不符合实际」。对 78 板金样
（`test_data/_incoming_epro2/78/`，与 substring_criteria 同口径）逐规则核对，
确认约 1/3 是可证实误报、约 1/10 是过度建议（error 仅 287 条 / 9%）。

## 口径

`DesignRuleChecker.check_all` 全量输出快照：改动前 `before.json`（=3202 条，
与 substring_criteria_2026-10-09/after.json 一致）/ 改动后 `after.json`，
按 `(rule, severity, desc, loc)` 四元组比对。零 LLM、零网络。脚手架与
p2_small_fixes 同口径（**必须 `check_all(..., pcb_data=pcb)`**），
一次性脚本 `snapshot.py`/`calibrate_acute.py` 用完即删。

## 结果

总违规 **3202 → 2048（−1154）**，均值 41.1 → 26.3 条/板，
双侧 rule_errors = 0，**非目标规则逐字节不变**（error 层 287 条原样保留）。
全量 pytest **1122 passed**（基线 1100 + 新增 `tests/test_violation_noise_2026_10_09.py` 22 例）
+ ui_smoke 84/84。

| 规则 | before → after | 判据变化 |
|---|---|---|
| 走线锐角检查 | 439 → 9 | 四族伪影逐一豁免（见下） |
| 位号连续性检查 | 189 → 61 | 跳号是正常实践（预留/删除/功能分区），合并每板至多 1 条 + 移入 ADVISE_RULES |
| 时钟信号包地检查 | 249 → 134 | 调试/RTC 网排除 + 15mm 长度门 |
| 丝印焊盘间距检查 | 78 → 0 | `metadata['silk_elements']` 守卫：解析器无丝印几何，落地后自动启用 |
| 丝印可读性检查 | 78 → 0 | 同上 |
| 地平面连续性检查 | 78 → 2 | copper_pours 有 GND 族铺铜 → 静默（残 2 板=真无铺铜） |
| 走线直角检查 | 158 → 88 | 同函数同口径豁免（闭合环/过孔结合点/覆铜区/短腿） |
| 封装一致性检查 | 150 → 96 | `_norm_fp` 单字母前缀归一（C0603/R0402/L3216 → 0603/0402/3216），55 条前缀假差异清零 |
| 信号线宽度检查 | 129 → 6 | 删 60% 主流线宽相对条款（颈口是标准做法）；≥4 层下限 0.09 → 0.088mm |
| 光学定位点检查 | 78 → 76 | 封装名找 MARK-POINT/FIDUCIAL：找到静默，找不到改「未检测到」（可证伪） |
| PDN 目标阻抗分析 | 78 → 78 | 板面积 5000 硬编码 → board_outline 实测（无板框静默）+「估算」标注 |

## 锐角四族伪影（校准证据）

439 条里 369 条报「最尖 45.0°」。45° 折线布线的真拐角内角只会是 135°/90°，
内角 45.0° 全部来自伪影/结合几何。min_leg=0.25 过滤后剩余 341 个拐角实测：

- **110 个顶点与过孔圆心精确重合** → 两条路径经同一过孔相接的结合点 →
  `TRACE_CORNER_VIA_SNAP_MM=0.3` 豁免；
- **199 个为 45.0°±0.3° 栅格楔形**（无过孔）→ 端点相接/蛇形折返 →
  `TRACE_CORNER_GRID_EPS_DEG=0.3` 豁免；
- **18 个 82.4° 模板角**（RK3576 GND/Top、DDR 电源 Top）→ 覆铜 thermal/void
  弦线 → (net,layer) 注册覆铜区整组跳过；
- 覆铜网格弦线短桩（0.016~0.07mm 腿）→ `TRACE_CORNER_MIN_LEG_MM` 0.05 → 0.25 +
  闭合环豁免（`Corner.is_closed`）+ <1° 链跳下限。

残留 9 条抽样：RA6E2 的 7.6° 真针尖、42.3°/38.9° 自由角度楔形等，可辩护。
残 6 条线宽 = 万兆软路由 3.5mil(0.0889) 整板设计暴露出的下限舍入误差已修，
剩余为真 <3.5mil/4mil 网络。

## 复跑方式

```bash
# before 需在改动前 checkout 后跑；脚手架口径：
#   Epro2Parser().parse(f) -> bom_rows_to_items(pcb.bom_items)
#   checker.check_all(bom, pcb.component_positions, {}, pcb_data=pcb)
# 输出 {"violations":[{board,rule,sev,desc,loc}], "rule_errors":[]}
python snapshot.py before.json
python snapshot.py after.json
```
