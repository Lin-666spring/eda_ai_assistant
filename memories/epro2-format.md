# 立创EDA V3 `.epro2` 格式与解析要点

> 2026-09-14 实测于真实文件 ProPrj_立创·泰山派3M（RK3576)开发板_2026-09-14.epro2
> 官方规范已下载到工作区 `.specs/`（已 gitignore）：V3 md/pdf + V2.2 pdf + V3 样例

## 格式结论

- `.epro` = V2 客户端格式；`.epro2` = V3 客户端格式（全新、日志式 key-value，与 V2 完全不同）
- 现有 src/pcb/parser.py 的 LCEDAProParser 只针对 V2（找 `.epcb`），解析不了 `.epro2`
- `.epro2` 本质是 ZIP：project2.json（元信息）+ <工程名>.epru（工程日志 JSON Lines）+ IMAGE/*.webp

## .epru 行格式

每行：`{meta}||{原子对象}|`
- meta 含 type / ticket / id
- 解析：split("||", 1) 后必须 rstrip("|") 再 json.loads
- DOCHEAD 行标记文档类型：PCB / BOARD / SCH / SCH_PAGE / SYMBOL / DEVICE / FOOTPRINT / CONFIG / FONT / BLOB

## 实测数据（3M RK3576 板）

| 项 | 数量 |
|---|---|
| PCB 文档 / 网络 NET | 1 / 669 |
| 走线 LINE（带 netName） | 24121 |
| 过孔 VIA | 2052 |
| 覆铜 POUR | 51 |
| 元件 COMPONENT | 947（Designator 947 / Device 947 / Footprint 942） |
| 焊盘 PAD / PAD_NET | 3261 / 3800 |
| 层 LAYER | 16+，层 id 是字符串 ["LAYER",1] |

走线样例：netName=RESETN, layerId=1, startX/endX/width=4.6

## 三个实现坑

1. PCB 文档里没有 PAD：焊盘定义在嵌入的 FOOTPRINT 文档，PCB 通过 COMPONENT.partId 引用 → 必须做 component → footprint → pads 组装
2. 网络归属走 PAD_NET（pad 与 net 关联）；NET 元素本身只存 differentialName / equalLengthGroupName（差分对/等长规则用）
3. BOM 字段在 SYMBOL 文档的 PART 元素里（不是实例 ATTR）：如 Supplier Part=C2150、Manufacturer Part=SS8050；实例只有 Designator/Device/Footprint，需联表 + 按类型聚合

## 与四种导出的关系（已字段级比对）

四种导出全部可从 .epro2 得到，且 .epro2 额外含走线/过孔/覆铜（导出里完全没有）：

| 导出 | .epro2 对应 |
|---|---|
| PickAndPlace（947 行） | PCB COMPONENT 947，完全一致 |
| Netlist（843 网） | 原理图 NET 1839 属性 + PCB NET 669 + PAD_NET（两套口径） |
| FlyingProbeTesting | PAD + PAD_NET + 坐标/层/netName |
| BOM（193 行聚合） | 实例 Designator + SYMBOL/PART 库属性，需自行聚合 |

结论：拿到 .epro2 就不需要四种导出，也不需要 Gerber。

## 下一步（未开始）

- [ ] 写 src/pcb/epro2_parser.py（Epro2Parser），先在真实样例上跑通 nets/traces/vias + BOM 重建
- [ ] create_parser() 加 .epro2；src/pcb/__init__.py 导出；eda_adapter.get_pcb_data 路由
- [ ] controller.load_pcb 支持 .epro2（建议加 load_project）
- [ ] tests/real_pcb_experiment.py / paper_experiments.py 接 pcb_data + netlist
- [ ] 批量导出 91 个设计的 .epro2 到 test_data/epro2/
