"""
迭代收敛引擎 — 闭环验证的纯逻辑收敛判定模块

将 VerificationEngine 的隐式迭代循环抽象为：
  - 不可变的逐轮快照 (RoundSnapshot) → 完整轨迹可追溯
  - 策略链 (TerminationPolicy) → 可插拔的收敛/发散/停滞/震荡判定
  - ConvergenceMonitor → 状态机编排，可证明终止性

设计原则：
  - 零 IO 依赖（不调用 LLM/DRC），所有数据由调用方注入 → 可单测、可证明终止
  - frozen dataclass 保证快照不可变 → 历史是 append-only 真值源
  - 策略链有序评估，首中即停 → 新增收敛条件只需加一个策略类

Reference: ITERATION_CONVERGENCE_PLAN.md (P1: 收敛模块)
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from src.constants import CONVERGENCE

logger = logging.getLogger(__name__)

__all__ = [
    "ConvergenceStatus",
    "RoundSnapshot",
    "ConvergenceResult",
    "TerminationPolicy",
    "BlockingIssuesPolicy",
    "StagnationPolicy",
    "OscillationPolicy",
    "DivergencePolicy",
    "MaxRoundsPolicy",
    "ConvergenceMonitor",
    "fingerprint_text",
    "issue_signature",
    "diff_issue_sets",
]


# ═══════════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════════


class ConvergenceStatus(Enum):
    """收敛状态 — 覆盖所有可观测的迭代终止情形。

    CONVERGED   无阻断违规，建议安全采纳
    DIVERGED    修正后违规数超过基线/单调递增 → 越修越差
    STAGNATED   LLM 修正与上一轮建议同指（无进展）
    OSCILLATING 修正在两个建议间来回摆动（周期 2 振荡）
    MAX_ROUNDS  达到轮次上限仍未收敛
    ABORTED     回调异常提前终止（DRC/LLM 失败）
    """

    CONVERGED = "converged"
    DIVERGED = "diverged"
    STAGNATED = "stagnated"
    OSCILLATING = "oscillating"
    MAX_ROUNDS = "max_rounds"
    ABORTED = "aborted"

    @property
    def terminal(self) -> bool:
        """所有收敛状态均为终态（Monitor 不会继续迭代）。"""
        return True


# ═══════════════════════════════════════════════════════════════
# 工具函数（纯函数）
# ═══════════════════════════════════════════════════════════════

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[，。！？,.!?;:；：、\"'`（）()\[\]【】]")


def fingerprint_text(text: str) -> str:
    """对建议文本生成归一化指纹。

    归一化：去空白/标点/大小写差异后取 sha1 前缀。
    等价文本（仅空白/标点/大小写不同）生成相同指纹 → 停滞/震荡判定稳定。
    空文本返回空串（使策略判定显式处理而非产生伪指纹）。
    """
    if not text:
        return ""
    # 标点替换为空格再合并空白，使 "add,cap" 与 "add cap"、"Add cap." 等价
    norm = _PUNCT_RE.sub(" ", text.strip())
    norm = _WS_RE.sub(" ", norm).strip().lower()
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()
    return digest[: CONVERGENCE.FINGERPRINT_HASH_LEN]


def issue_signature(rule_name: str, severity: str, location: str = "") -> str:
    """违规问题签名 — 用于跨轮追踪同一问题的「新增/解决/遗留」。

    以 rule_name + severity + location 三元组构成稳定标识，
    规避 description 抖动导致的签名漂移。
    """
    return f"{rule_name or ''}#{(severity or '').lower()}#{location or ''}"


def diff_issue_sets(
    current: frozenset[str],
    previous: frozenset[str],
) -> tuple[int, int]:
    """计算两轮问题签名的差分。

    Returns:
        (new_count, resolved_count)
        new_count     本轮新增签名数（current - previous）
        resolved_count 上轮独有签名数（previous - current）
    """
    new_count = len(current - previous)
    resolved_count = len(previous - current)
    return new_count, resolved_count


# ═══════════════════════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RoundSnapshot:
    """单轮验证的不可变快照 — 收敛判定的唯一输入。

    快照只承载判定所需信息，不持有原始 LLM/DRC 对象 → 序列化与回放可靠。
    """

    round: int
    suggestion: str
    fingerprint: str
    blocking_count: int
    total_issue_count: int
    issue_signatures: frozenset[str]
    new_issues: int = 0          # 相对上一轮的新增违规数（可改进指标）
    resolved_issues: int = 0     # 相对上一轮的解决违规数
    drc_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0

    @property
    def converged(self) -> bool:
        """无阻断违规即视为该轮收敛。"""
        return self.blocking_count == 0


@dataclass
class ConvergenceResult:
    """最终收敛结果 — 含状态、指标与完整轨迹（供论文 4.3 节导出）。

    指标全部由快照历史派生，无外部依赖，便于离线复算与对账。
    """

    status: ConvergenceStatus
    max_rounds: int
    snapshot_history: tuple[RoundSnapshot, ...]
    total_llm_calls: int

    @property
    def converged_round(self) -> Optional[int]:
        """收敛所在轮次编号；仅 status==CONVERGED 时有效，否则 None。"""
        if self.status != ConvergenceStatus.CONVERGED:
            return None
        if not self.snapshot_history:
            return None
        return self.snapshot_history[-1].round

    @property
    def snapshot_count(self) -> int:
        """已记录的轮次数。"""
        return len(self.snapshot_history)

    @property
    def issue_reduction_curve(self) -> tuple[int, ...]:
        """每轮阻断违规数序列 — 直接可绘制的收敛曲线。"""
        return tuple(s.blocking_count for s in self.snapshot_history)

    @property
    def correction_efficiency(self) -> Optional[float]:
        """修正效率 = (首轮阻断 - 末轮阻断) / 首轮阻断。

        首轮阻断为 0（已收敛）或不足两轮时返回 None。
        值域：1.0=完全消除，0.0=无改善，<0=负向递归时由 Divergence 状态承载。
        """
        if len(self.snapshot_history) < 2:
            return None
        initial = self.snapshot_history[0].blocking_count
        final = self.snapshot_history[-1].blocking_count
        if initial == 0:
            return None
        return (initial - final) / initial

    def to_dict(self) -> dict:
        """JSON 可序列化（供实验脚本与前端消费）。"""
        return {
            "status": self.status.value,
            "max_rounds": self.max_rounds,
            "converged_round": self.converged_round,
            "total_llm_calls": self.total_llm_calls,
            "correction_efficiency": self.correction_efficiency,
            "issue_reduction_curve": list(self.issue_reduction_curve),
            "snapshot_count": len(self.snapshot_history),
            "rounds": [
                {
                    "round": s.round,
                    "fingerprint": s.fingerprint,
                    "blocking_count": s.blocking_count,
                    "total_issue_count": s.total_issue_count,
                    "new_issues": s.new_issues,
                    "resolved_issues": s.resolved_issues,
                    "converged": s.converged,
                    "drc_latency_ms": s.drc_latency_ms,
                    "llm_latency_ms": s.llm_latency_ms,
                }
                for s in self.snapshot_history
            ],
        }


# ═══════════════════════════════════════════════════════════════
# 终止策略
# ═══════════════════════════════════════════════════════════════


class TerminationPolicy:
    """策略基类 — 评估快照历史，命中返回终止状态，否则返回 None。

    策略为纯函数式对象，仅读取历史不修改状态；
    新增收敛条件只需实现 evaluate 并插入策略链，无需改动状态机。
    """

    def evaluate(self, history: Sequence[RoundSnapshot]) -> Optional[ConvergenceStatus]:
        raise NotImplementedError


class BlockingIssuesPolicy(TerminationPolicy):
    """本轮无阻断违规 → CONVERGED。必须置于链首（最高优先级）。"""

    def evaluate(self, history: Sequence[RoundSnapshot]) -> Optional[ConvergenceStatus]:
        if not history:
            return None
        if history[-1].converged:
            return ConvergenceStatus.CONVERGED
        return None


class StagnationPolicy(TerminationPolicy):
    """LLM 修正与上一轮建议同指（无进展）→ STAGNATED。

    仅比较相邻两轮，避免与 OscillationPolicy（周期 2 重叠）语义打架。
    """

    def evaluate(self, history: Sequence[RoundSnapshot]) -> Optional[ConvergenceStatus]:
        if len(history) < 2:
            return None
        cur, prev = history[-1], history[-2]
        if cur.fingerprint and cur.fingerprint == prev.fingerprint:
            return ConvergenceStatus.STAGNATED
        return None


class OscillationPolicy(TerminationPolicy):
    """修正呈周期 2 振荡（fp_k == fp_{k-period} 且 fp_k != fp_{k-1}）→ OSCILLATING。"""

    def __init__(self, period: int = CONVERGENCE.OSCILLATION_PERIOD) -> None:
        if period < 1:
            raise ValueError(f"oscillation period must be >= 1, got {period}")
        self._period = period

    def evaluate(self, history: Sequence[RoundSnapshot]) -> Optional[ConvergenceStatus]:
        # A→B→(回到A) 模式至少需要 period+1 个快照才能被识别
        if len(history) < self._period + 1:
            return None
        cur = history[-1]
        prev = history[-2]
        earlier = history[-1 - self._period]
        if cur.fingerprint == earlier.fingerprint and cur.fingerprint != prev.fingerprint:
            return ConvergenceStatus.OSCILLATING
        return None


class DivergencePolicy(TerminationPolicy):
    """修正导致阻断违规背离收敛 → DIVERGED。

    双触发（任一命中即发散）：
      (a) 因子法：本轮阻断数 > 首轮阻断数 × factor（远超基线）
      (b) 连续递增法：最近 streak+1 轮阻断数严格单调递增
    """

    def __init__(
        self,
        factor: float = CONVERGENCE.DIVERGENCE_FACTOR,
        streak: int = CONVERGENCE.DIVERGENCE_STREAK,
    ) -> None:
        if factor <= 1.0:
            raise ValueError(f"divergence factor must be > 1.0, got {factor}")
        if streak < 1:
            raise ValueError(f"divergence streak must be >= 1, got {streak}")
        self._factor = factor
        self._streak = streak

    def evaluate(self, history: Sequence[RoundSnapshot]) -> Optional[ConvergenceStatus]:
        if len(history) < 2:
            return None
        first_count = history[0].blocking_count
        last_count = history[-1].blocking_count

        # (a) 因子法：首轮为正值基线时才比较，避免首轮已收敛的退化情形
        if first_count > 0 and last_count > first_count * self._factor:
            return ConvergenceStatus.DIVERGED

        # (b) 连续递增法：取尾部 streak+1 个快照验证严格递增
        if len(history) >= self._streak + 1:
            tail = list(history[-(self._streak + 1):])
            strictly_increasing = all(
                tail[i].blocking_count < tail[i + 1].blocking_count
                for i in range(self._streak)
            )
            if strictly_increasing:
                return ConvergenceStatus.DIVERGED
        return None


class MaxRoundsPolicy(TerminationPolicy):
    """达到轮次上限 → MAX_ROUNDS。置于链尾作为兜底终止保证。"""

    def __init__(self, max_rounds: int) -> None:
        if max_rounds < 1:
            raise ValueError(f"max_rounds must be >= 1, got {max_rounds}")
        self._max_rounds = max_rounds

    def evaluate(self, history: Sequence[RoundSnapshot]) -> Optional[ConvergenceStatus]:
        if len(history) >= self._max_rounds:
            return ConvergenceStatus.MAX_ROUNDS
        return None


# ═══════════════════════════════════════════════════════════════
# 收敛监视器（状态机编排）
# ═══════════════════════════════════════════════════════════════


class ConvergenceMonitor:
    """收敛状态机编排器 — 追加快照、有序评估策略链、产出最终结果。

    终止性保证：MaxRoundsPolicy 在链尾，每轮至多追加一个快照，
    故至多 max_rounds 轮必然返回终态（无死循环），可直接写进论文 Method 章节论证。
    """

    def __init__(
        self,
        max_rounds: int = CONVERGENCE.DEFAULT_MAX_ROUNDS,
        policies: Optional[Sequence[TerminationPolicy]] = None,
    ) -> None:
        if max_rounds < 1:
            raise ValueError(f"max_rounds must be >= 1, got {max_rounds}")
        self._max_rounds = max_rounds
        self._policies: tuple[TerminationPolicy, ...] = (
            tuple(policies) if policies is not None else self._default_policies()
        )
        self._snapshots: list[RoundSnapshot] = []
        self._llm_call_count: int = 0
        self._aborted: bool = False
        self._last_status: Optional[ConvergenceStatus] = None

    def _default_policies(self) -> tuple[TerminationPolicy, ...]:
        # 顺序即优先级：收敛判定优先于异常形态判定优先于兜底终止
        return (
            BlockingIssuesPolicy(),
            StagnationPolicy(),
            OscillationPolicy(),
            DivergencePolicy(),
            MaxRoundsPolicy(self._max_rounds),
        )

    # ── 状态推进 ──

    def record_round(self, snapshot: RoundSnapshot) -> Optional[ConvergenceStatus]:
        """追加速度快照并评估策略链。

        Returns:
            命中策略的终态；None 表示仍在迭代中（尚未终止）。
            若已 abort，后续 record 一律返回 ABORTED 且不再追加历史。
        """
        if self._aborted:
            self._last_status = ConvergenceStatus.ABORTED
            return self._last_status
        self._snapshots.append(snapshot)
        status = self._evaluate()
        self._last_status = status
        return status

    def note_correction(self) -> None:
        """记录一次 LLM 修正调用（供指标统计，不改变状态）。"""
        self._llm_call_count += 1

    def abort(self) -> None:
        """标记回调异常终止；终态固定为 ABORTED。"""
        self._aborted = True
        self._last_status = ConvergenceStatus.ABORTED

    def _evaluate(self) -> Optional[ConvergenceStatus]:
        for policy in self._policies:
            status = policy.evaluate(self._snapshots)
            if status is not None:
                return status
        return None

    # ── 查询 ──

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def last_status(self) -> Optional[ConvergenceStatus]:
        return self._last_status

    def finalize(self) -> ConvergenceResult:
        """产出最终收敛结果。未推进即被终结时安全兜底为 ABORTED。"""
        if self._last_status is None:
            self._last_status = ConvergenceStatus.ABORTED
        return ConvergenceResult(
            status=self._last_status,
            max_rounds=self._max_rounds,
            snapshot_history=tuple(self._snapshots),
            total_llm_calls=self._llm_call_count,
        )

    # ── 便利构造 ──

    @staticmethod
    def build_snapshot(
        round_num: int,
        suggestion: str,
        blocking_count: int,
        total_issue_count: int,
        issue_signatures: "frozenset[str] | set[str] | Sequence[str]",
        *,
        new_issues: int = 0,
        resolved_issues: int = 0,
        drc_latency_ms: float = 0.0,
        llm_latency_ms: float = 0.0,
    ) -> RoundSnapshot:
        """快照便利构造器：自动计算指纹并统一签名集合为 frozenset。"""
        return RoundSnapshot(
            round=round_num,
            suggestion=suggestion,
            fingerprint=fingerprint_text(suggestion),
            blocking_count=blocking_count,
            total_issue_count=total_issue_count,
            issue_signatures=frozenset(issue_signatures),
            new_issues=new_issues,
            resolved_issues=resolved_issues,
            drc_latency_ms=drc_latency_ms,
            llm_latency_ms=llm_latency_ms,
        )