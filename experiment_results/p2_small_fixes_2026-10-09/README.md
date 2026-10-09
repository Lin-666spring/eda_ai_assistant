# P2 小项批次金样对比（2026-10-09）

## 口径

78 个唯一 `.epro2` 设计（`test_data/_incoming_epro2`，rglob）全量
`DesignRuleChecker.check_all` 输出快照，改动前 `before.json` / 改动后
`after.json`，逐条违规按 `(rule_name, severity, description, location)`
四元组集合比对。零 LLM、零网络，约 40s/轮。

脚手架核心（一次性脚本已删，按惯例留思路）：

```python
pcb = Epro2Parser().parse(str(f))
bom_items = bom_rows_to_items(pcb.bom_items)
positions = {ref: {...} for ref, v in pcb.component_positions.items()}
netlist = {name: list(net.pins) for name, net in pcb.nets.items() if net.pins}
violations = checker.check_all(bom_items, positions, netlist, pcb_data=pcb)
```

**坑位（本轮踩过）**：`check_all` 首行无条件 `self._pcb_data = pcb_data`。
只给 `checker._pcb_data` 赋值而不传 `pcb_data=` 参数，会让全部走线/板框类
规则静默跳过——第一版快照只出 1312 条违规（正确值 3519），两条板边规则
恰好因此"看起来"清零。对比数字对不上阶段B 金样时，先查脚手架。

## 结果

- 总违规 **3519 → 3455（−64）**，双侧 rule_errors = 0
- **56 条无关规则逐字节不变**（含走线锐角 432 / 直角 154 / 串扰 120 /
  载流 79 / 特征阻抗 297 等）——死代码删除与 `_xy` helper 重构零行为变化
- 板边间距检查 **62 → 24**：减板框原点 + 四边判定后，原点偏移噪声消失，
  保留的 24 条含负边距/0.7mm 级真实近边元件
- 连接器边沿布局检查 **57 → 31**：旧口径 `x>10 and y>10` 在原点偏移板上
  全部误报；新口径按真实边距，且新增「距最近板边 Nmm」文本
- 元件间距检查 13 条纯描述改写（「按导入顺序抽样、非空间最近邻」）
- 41/78 板板框 source=outline，37 板退回铜包围盒（两规则对其跳过，
  与走线板边规则同一守卫）
