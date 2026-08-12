# 迭代收敛引擎 — 实现计划 (Iteration Convergence Plan)

> 2026-08-12 制定
> 目标：将 `VerificationEngine` 的隐式 for-loop 升级为**策略驱动的收敛状态机**，
> 具备可观测、可判定、可解释的收敛语义，为论文 4.3 节「迭代收敛分析」提供代码支撑。
> 注：实验数据样本暂不在本计划范围（用户要求），仅做代码架构。

---

## 一、现状与问题

当前实现 `src/core/verifier.py::VerificationEngine.verify()`（L215-264）：

```
for round in 1..MAX_ROUNDS(=3):
    check → analyze → blocking? 
        no  → PASSED, break
        yes → llm_callback 修正 → 下一轮
```

### 架构缺陷

| # | 缺陷 | 后果 |
|---|------|------|
| 1 | 终止条件只有两种（无违规 / 到上限），无**停滞检测** | LLM 返回相同建议 → 白耗 LLM 调用与轮次 |
| 2 | 无**震荡检测**（A→B→A 修正循环） | 永远到不了 PASSED，浪费满 3 轮 |
| 3 | 无**发散检测**（修正后违规更多） | 越修越差仍继续迭代 |
| 4 | 无逐轮指标记录（问题数变化、延迟、指纹） | 论文无法产出收敛曲线数据 |
| 5 | 无**问题级身份标识** | 无法追踪"第 1 轮的问题 X 在第 3 轮是否被解决" |
| 6 | `MAX_ROUNDS` 硬编码类常量，不可按调用配置 | 实验调参需改源码 |
| 7 | 循环控制流为散落的 `break`，非显式状态机 | 难扩展、难测试、难证明终止性 |
| 8 | 收敛结果不进入 `VerificationReport.to_dict()` | 前端/实验脚本拿不到收敛语义 |

---

## 二、总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    VerificationEngine (verifier.py)           │
│  · 对外接口不变: verify() / verify_design_change() /          │
│    verify_rule() → VerificationReport                         │
│  · 职责: IO 编排 (DRC callback / LLM callback / 异常兜底)      │
└──────────────────────────┬──────────────────────────────────┘
                           │ 每轮: check 结果 + 修正建议
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              ConvergenceMonitor (convergence.py)              │
│  · 纯逻辑, 零 IO, 无 LLM/DRC 依赖 → 可单测、可证明终止性        │
│  · 持有 RoundSnapshot 历史 (不可变, append-only)               │
│  · 每轮追加快照 → 依序评估 TerminationPolicy 链                │
│  · 产出 ConvergenceResult (状态 + 指标 + 完整轨迹)              │
└──────────────────────────┬──────────────────────────────────┘
                           │ policy 链
              ┌────────────┼──────────────────────┐
              ▼            ▼                      ▼
     BlockingIssues    Stagnation           Oscillation
     Policy            Policy               Policy
     (0违规→收敛)      (指纹重复→停滞)       (周期2循环→震荡)
              │            │                      │
              ▼            ▼                      ▼
          Divergence     MaxRounds             (可扩展...)
          Policy         Policy
          (违规递增→发散) (轮次上限)
```

**关键设计决策**

1. **纯逻辑与 IO 分离**：`convergence.py` 不含任何 LLM/DRC 调用，全部依赖注入的轮次数据。
   这保证：(a) 策略可单元测试；(b) 终止性可静态论证；(c) 未来可换 LLM/规则引擎而收敛逻辑不动。
2. **策略链插件化**：`TerminationPolicy` 为 Protocol，新增收敛条件只需加一个策略类，不改状态机。
3. **问题级身份**：每轮为每个违规生成稳定签名，支持跨轮追踪「新增/解决/遗留」。
4. **向后兼容**：`verify()` 签名与返回 `VerificationReport` 不变，只**增量**添加
   `convergence` 字段与 `to_dict()` 新块。现有 77 处测试引用不受影响。

---

## 三、模块设计

### 3.1 新模块 `src/core/convergence.py`（纯逻辑，~350 行）

```
枚举
├─ ConvergenceStatus: CONVERGED | DIVERGED | STAGNATED
│                      | OSCILLATING | MAX_ROUNDS | ABORTED
│   (ABORTED = check/llm 回调异常导致提前终止)

数据模型
├─ RoundSnapshot        # 单轮不可变快照
│   round, suggestion, fingerprint,
│   blocking_count, total_issue_count,
│   issue_signatures: frozenset[str],
│   new_issues, resolved_issues: int,
│   drc_latency_ms, llm_latency_ms,
│   status: VerificationStatus
├─ ConvergenceResult    # 最终收敛结果
│   status, snapshot_history,
│   指标: converged_round, correction_efficiency,
│         issue_reduction_curve, total_llm_calls,
│   to_dict() → JSON 可序列化（供论文实验导出）

策略 (Protocol + 实现)
├─ TerminationPolicy    # evaluate(history) -> ConvergenceStatus | None
├─ BlockingIssuesPolicy # 0 阻断违规 → CONVERGED
├─ StagnationPolicy     # 本轮指纹 ∈ 历史指纹集合 → STAGNATED
├─ OscillationPolicy    # 最近指纹与上上轮相同(周期2) → OSCILLATING
├─ DivergencePolicy     # 阻断数连续≥2轮单调递增, 或 > 第1轮×K → DIVERGED
├─ MaxRoundsPolicy      # len(history) >= max_rounds → MAX_ROUNDS
└─ (默认链按上述顺序评估, 首中即停)

引擎
└─ ConvergenceMonitor
    record_round(snapshot) -> ConvergenceStatus | None   # 追加+评估, 纯函数
    finalize() -> ConvergenceResult

工具函数
├─ fingerprint_text(text) -> str      # 归一化(去空白/标点/小写) 后取 sha1 前 12 位
└─ issue_signature(rule, severity, location) -> str
```

**配置**（按仓库惯例进 `src/constants.py` 的 `ConvergenceConfig` 冻结 dataclass）：

| 常量 | 默认 | 说明 |
|------|------|------|
| `DEFAULT_MAX_ROUNDS` | 3 | 与现状一致 |
| `DIVERGENCE_FACTOR` | 1.5 | 本轮阻断数 > 首轮 × 该系数 → 发散 |
| `DIVERGENCE_STREAK` | 2 | 连续递增轮数阈值 |
| `OSCILLATION_PERIOD` | 2 | 震荡检测周期 |

### 3.2 重构 `src/core/verifier.py`（行为保持）

- `VerificationEngine.__init__(..., max_rounds=ConvergenceConfig.DEFAULT_MAX_ROUNDS)` —
  `MAX_ROUNDS` 类常量退役，改实例可配置。
- `verify()` 主体改为每轮：

```
snapshot = monitor.record_round(round_data)      # 1. 记录本轮
status = monitor.evaluate()                       # 2. 策略链判定
if status is CONVERGED:   → PASSED, break
if status in {DIVERGED, STAGNATED, OSCILLATING, MAX_ROUNDS, ABORTED}: break
else:                    → 取阻断违规 → llm_callback 修正 → 下一轮
```

- 回调节点保持不变（check_callback / llm_callback），异常捕获逻辑保持不变
  （异常 → ABORTED，与原 UNCERTAIN 语义对齐并标记）。
- `VerificationReport` 增加字段 `convergence: ConvergenceResult | None`：
  - `to_dict()` 追加 `"convergence": {...}` 块（旧键原样保留 → 前端/实验脚本兼容）
  - `to_markdown()` 追加「收敛分析」小节：状态、收敛轮次、问题缩减曲线、每轮指纹
- `_analyze_violations` 增强：除与 baseline 差分外，与**上一轮**差分，产出
  `new_issues` / `resolved_issues` 计数与逐问题签名。

### 3.3 状态机定义（每轮语义）

```
        ┌─────────────┐
START → │ CHECK (DRC) │──异常──→ ABORTED
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │  ANALYZE    │ 与 baseline 差分 + 与上一轮差分 → 快照
        └──────┬──────┘
               ▼
        ┌──────────────────────┐
        │ POLICY CHAIN (有序)  │
        │ 0阻断 → CONVERGED    │
        │ 指纹重复 → STAGNATED │
        │ 周期2 → OSCILLATING  │
        │ 递增 → DIVERGED      │
        │ 达上限 → MAX_ROUNDS  │
        └──────┬───────────────┘
               │ 未命中任何策略
               ▼
        ┌─────────────┐
        │ CORRECT(LLM)│──异常──→ ABORTED
        └──────┬──────┘
               ▼
              回到 CHECK
```

**终止性论证**：每轮要么命中策略终止，要么消耗 1 轮预算；`MaxRoundsPolicy`
保证 ≤ max_rounds 轮必然终止（写进 docstring 与测试注释，供论文 Method 引用）。

---

## 四、接口与兼容性清单

| 接口 | 变化 | 兼容性 |
|------|------|--------|
| `VerificationEngine.verify(suggestion, category, baseline_violations)` | 签名不变；新增可选 `max_rounds` | ✅ 向后兼容 |
| `VerificationReport.to_dict()` | 追加 `convergence` 块 | ✅ 旧键保留 |
| `VerificationReport.to_markdown()` | 追加收敛小节 | ✅ 纯增量 |
| `VerificationReport.convergence` | 新属性，可为 None（未启用时） | ✅ 新字段 |
| `controller.verify_suggestion()` / `api/endpoints.py` | **不改动** | ✅ 零改动 |
| `create_verifier_from_controller()` | 透传 max_rounds 配置 | ✅ 默认行为不变 |

---

## 五、测试策略

### 5.1 新增 `tests/test_convergence.py`（纯逻辑，无需 LLM/DRC）

- **每个策略单测**：构造受控快照历史，断言返回状态（含 None 分支）
- **策略优先级**：多策略同时命中时按链顺序取第一个
- **终止性**：任意 callback 序列下 `monitor` 在 ≤ max_rounds 轮内产出最终状态
- **指纹函数**：空白/标点/大小写归一化等价性；不同文本指纹不同
- **问题签名**：同规则同位置同严重度 → 同签名；跨轮 resolved/new 计数正确
- **ConvergenceResult.to_dict()** JSON 可序列化（round-trip）

### 5.2 状态机集成测试（脚本化回调）

- 首轮即过 → CONVERGED, 1 轮
- 修正后仍违规、且 LLM 返回**完全相同文本** → STAGNATED（不再浪费第 3 轮）
- A→B→A 修正循环 → OSCILLATING
- 每轮违规数递增 → DIVERGED
- check 异常 → ABORTED（原 UNCERTAIN 语义保持）
- 报告 `to_dict()` 同时含旧键与 `convergence` 块

### 5.3 回归测试（零修改通过）

- `tests/test_verifier.py`（54 行处引擎行为）
- `tests/test_verifier_integration.py`（控制器管线 + ToolRegistry）
- `tests/test_verification_map.py`
- `tests/paper_experiments.py` 导入路径

---

## 六、实施阶段

| 阶段 | 内容 | 产出 | 验证 |
|------|------|------|------|
| **P1** | `src/core/convergence.py` 纯逻辑模块 + 常量进 `constants.py` | 数据模型/策略/监视器 | `pytest tests/test_convergence.py` |
| **P2** | 重构 `verifier.py` 循环挂到 Monitor（行为保持，MAX_ROUNDS 可配置） | 状态机化 verify() | 全部 verifier 回归测试通过 |
| **P3** | `VerificationReport` 挂载 `ConvergenceResult` + to_dict/to_markdown 增量 | 收敛语义对外可见 | 格式化测试 + 前端字段兼容 |
| **P4** | （数据样本就绪后，另行计划）实验导出器：`convergence.to_dict()` → 收敛曲线/图表 | 论文 4.3 节数据 | — |

> P4 依赖实验数据样本，按用户要求**暂不展开**。

---

## 七、风险与对策

| 风险 | 对策 |
|------|------|
| 重构破坏现有 77 处引用 | 增量字段 + 回归测试先行；P2 用行为保持重构，逐提交跑全量测试 |
| 指纹哈希碰撞导致误判停滞 | sha1 前 12 位 + 文本归一化双重检查；碰撞概率可忽略但测试覆盖归一化等价性 |
| 发散判定过于激进（正常修正波动被误杀） | `DIVERGENCE_STREAK=2` + `DIVERGENCE_FACTOR=1.5` 双阈值，常量可配置便于实验调参 |
| LLM 修正串行调用时延 | 收敛引擎与 IO 分离，P4 阶段可评估并行修正（不影响本架构） |
| 论文表述需要 | 收敛状态/终止性论证写进 docstring 与报告 markdown，Method 章节直接引用 |

---

## 八、与论文的对应关系

| 论文位置 | 代码支撑 |
|---------|---------|
| §3.2 验证引擎核心算法（伪代码） | 第三节状态机图可直接转伪代码 |
| §3.4 LLM 修正反馈机制 | Stagnation/Oscillation 检测证明反馈闭环的**负面路径**也被处理 |
| §4.3 迭代收敛分析 | `ConvergenceResult` 的收敛轮次/缩减曲线/修正效率指标 |
| 目标指标「迭代收敛轮次 ≤ 2.0」 | `converged_round` 即该指标的直接度量 |
