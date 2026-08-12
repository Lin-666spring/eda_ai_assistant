"""Tests for the convergence module (pure logic, no LLM/DRC IO)."""

from src.core.convergence import (
    BlockingIssuesPolicy,
    ConvergenceMonitor,
    ConvergenceResult,
    ConvergenceStatus,
    DivergencePolicy,
    MaxRoundsPolicy,
    OscillationPolicy,
    RoundSnapshot,
    StagnationPolicy,
    TerminationPolicy,
    diff_issue_sets,
    fingerprint_text,
    issue_signature,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _snap(round, suggestion, blocking, total=None, sigs=None,
          new_issues=0, resolved_issues=0):
    """Convenience snapshot builder mirroring ConvergenceMonitor.build_snapshot."""
    return ConvergenceMonitor.build_snapshot(
        round_num=round,
        suggestion=suggestion,
        blocking_count=blocking,
        total_issue_count=blocking if total is None else total,
        issue_signatures=sigs or frozenset(),
        new_issues=new_issues,
        resolved_issues=resolved_issues,
    )


def _history(*snapshots):
    return list(snapshots)


# ═══════════════════════════════════════════════════════════════
# tool functions
# ═══════════════════════════════════════════════════════════════


class TestFingerprintText:
    def test_empty_returns_empty(self):
        assert fingerprint_text("") == ""

    def test_whitespace_invariant(self):
        assert fingerprint_text("add  cap") == fingerprint_text("add  cap")
        assert fingerprint_text("add cap") == fingerprint_text("  add   cap  ")

    def test_punctuation_invariant(self):
        assert fingerprint_text("add, cap!") == fingerprint_text("add cap")
        assert fingerprint_text("添加电容。") == fingerprint_text("添加电容")

    def test_case_invariant(self):
        assert fingerprint_text("Add Cap") == fingerprint_text("add cap")

    def test_different_text_different_fp(self):
        assert fingerprint_text("add cap") != fingerprint_text("add resistor")


class TestIssueSignature:
    def test_stable_for_same_triple(self):
        assert issue_signature("X", "error", "U1") == issue_signature("X", "error", "U1")

    def test_severity_case_insensitive(self):
        assert issue_signature("X", "ERROR") == issue_signature("X", "error")

    def test_location_change_changes_signature(self):
        assert issue_signature("X", "error", "U1") != issue_signature("X", "error", "U2")

    def test_missing_fields_safe(self):
        assert issue_signature("", "", "") == "##"


class TestDiffIssueSets:
    def test_no_overlap(self):
        new, resolved = diff_issue_sets(frozenset({"a", "b"}), frozenset({"c"}))
        assert new == 2
        assert resolved == 1

    def test_identical(self):
        new, resolved = diff_issue_sets(frozenset({"a"}), frozenset({"a"}))
        assert new == 0
        assert resolved == 0

    def test_subset(self):
        new, resolved = diff_issue_sets(frozenset({"a"}), frozenset({"a", "b"}))
        assert new == 0
        assert resolved == 1


# ═══════════════════════════════════════════════════════════════
# data models
# ═══════════════════════════════════════════════════════════════


class TestRoundSnapshot:
    def test_frozen(self):
        s = _snap(1, "x", 0)
        try:
            s.blocking_count = 5  # type: ignore[misc]
            assert False, "should be frozen"
        except Exception:
            pass

    def test_converged_when_no_blocking(self):
        assert _snap(1, "x", 0).converged is True

    def test_not_converged_when_blocking(self):
        assert _snap(1, "x", 2).converged is False


# ═══════════════════════════════════════════════════════════════
# policies
# ═══════════════════════════════════════════════════════════════


class TestBlockingIssuesPolicy:
    def test_empty_history_none(self):
        assert BlockingIssuesPolicy().evaluate([]) is None

    def test_converged(self):
        h = _history(_snap(1, "s", 0))
        assert BlockingIssuesPolicy().evaluate(h) == ConvergenceStatus.CONVERGED

    def test_blocking_none(self):
        h = _history(_snap(1, "s", 3))
        assert BlockingIssuesPolicy().evaluate(h) is None


class TestStagnationPolicy:
    def test_single_round_none(self):
        assert StagnationPolicy().evaluate(_history(_snap(1, "s", 3))) is None

    def test_same_suggestion_stagnated(self):
        h = _history(_snap(1, "same", 3), _snap(2, "same", 3))
        assert StagnationPolicy().evaluate(h) == ConvergenceStatus.STAGNATED

    def test_different_suggestion_none(self):
        h = _history(_snap(1, "a", 3), _snap(2, "b", 3))
        assert StagnationPolicy().evaluate(h) is None

    def test_only_punctuation_diff_treated_as_stagnated(self):
        h = _history(_snap(1, "add cap!", 3), _snap(2, "Add,Cap", 3))
        assert StagnationPolicy().evaluate(h) == ConvergenceStatus.STAGNATED


class TestOscillationPolicy:
    def test_below_threshold_none(self):
        p = OscillationPolicy(period=2)
        # only 2 snapshots — insufficient
        assert p.evaluate(_history(_snap(1, "a", 1), _snap(2, "b", 1))) is None

    def test_period2_cycle_detected(self):
        p = OscillationPolicy(period=2)
        # A -> B -> A
        h = _history(_snap(1, "a", 1), _snap(2, "b", 1), _snap(3, "a", 1))
        assert p.evaluate(h) == ConvergenceStatus.OSCILLATING

    def test_strict_progression_none(self):
        p = OscillationPolicy(period=2)
        # A -> B -> C
        h = _history(_snap(1, "a", 1), _snap(2, "b", 1), _snap(3, "c", 1))
        assert p.evaluate(h) is None

    def test_stagnation_after_b_is_not_oscillation(self):
        p = OscillationPolicy(period=2)
        # A -> B -> B (last == prev, so not oscillation)
        h = _history(_snap(1, "a", 1), _snap(2, "b", 1), _snap(3, "b", 1))
        assert p.evaluate(h) is None

    def test_invalid_period_raises(self):
        try:
            OscillationPolicy(period=0)
            assert False
        except ValueError:
            pass


class TestDivergencePolicy:
    def test_single_round_none(self):
        p = DivergencePolicy()
        assert p.evaluate(_history(_snap(1, "a", 2))) is None

    def test_factor_trigger(self):
        p = DivergencePolicy(factor=1.5)
        h = _history(_snap(1, "a", 2), _snap(2, "b", 4))  # 4 > 2*1.5
        assert p.evaluate(h) == ConvergenceStatus.DIVERGED

    def test_below_factor_none(self):
        p = DivergencePolicy(factor=1.5)
        h = _history(_snap(1, "a", 2), _snap(2, "b", 3))  # 3 < 3.0 -> equal not greater
        assert p.evaluate(h) is None

    def test_streak_trigger(self):
        p = DivergencePolicy(streak=2)
        # strictly increasing 1 < 2 < 3
        h = _history(_snap(1, "a", 1), _snap(2, "b", 2), _snap(3, "c", 3))
        assert p.evaluate(h) == ConvergenceStatus.DIVERGED

    def test_monotonic_decreasing_none(self):
        p = DivergencePolicy(streak=2)
        h = _history(_snap(1, "a", 5), _snap(2, "b", 4), _snap(3, "c", 3))
        assert p.evaluate(h) is None

    def test_first_round_zero_skips_factor(self):
        # first round 0 blocking would have converged already; factor guard avoids div issues
        p = DivergencePolicy(factor=1.5)
        h = _history(_snap(1, "a", 0), _snap(2, "b", 1))
        assert p.evaluate(h) is None

    def test_invalid_factor_raises(self):
        try:
            DivergencePolicy(factor=1.0)
            assert False
        except ValueError:
            pass
        try:
            DivergencePolicy(streak=0)
            assert False
        except ValueError:
            pass


class TestMaxRoundsPolicy:
    def test_below_max_none(self):
        p = MaxRoundsPolicy(max_rounds=3)
        assert p.evaluate(_history(_snap(1, "a", 1))) is None

    def test_at_max_triggers(self):
        p = MaxRoundsPolicy(max_rounds=3)
        h = _history(_snap(1, "a", 1), _snap(2, "b", 1), _snap(3, "c", 1))
        assert p.evaluate(h) == ConvergenceStatus.MAX_ROUNDS

    def test_invalid_max_raises(self):
        try:
            MaxRoundsPolicy(max_rounds=0)
            assert False
        except ValueError:
            pass


# ═══════════════════════════════════════════════════════════════
# monitor state machine
# ═══════════════════════════════════════════════════════════════


class TestConvergenceMonitor:

    def test_passes_immediately(self):
        m = ConvergenceMonitor(max_rounds=3)
        s1 = _snap(1, "safe", 0)
        status = m.record_round(s1)
        assert status == ConvergenceStatus.CONVERGED
        result = m.finalize()
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.converged_round == 1
        assert result.issue_reduction_curve == (0,)
        assert result.total_llm_calls == 0

    def test_progressing_returns_none(self):
        m = ConvergenceMonitor(max_rounds=3)
        s1 = _snap(1, "bad", 2)
        # only one failing round — neither converged nor max nor divergence yet
        assert m.record_round(s1) is None
        m.note_correction()
        s2 = _snap(2, "better", 1)
        assert m.record_round(s2) is None
        assert m.last_status is None

    def test_max_rounds_terminal(self):
        m = ConvergenceMonitor(max_rounds=3)
        for r in (1, 2, 3):
            status = m.record_round(_snap(r, f"s{r}", 1))
            if r < 3:
                assert status is None
        # at round 3 the default chain hits MaxRounds
        assert m.last_status == ConvergenceStatus.MAX_ROUNDS
        result = m.finalize()
        assert result.status == ConvergenceStatus.MAX_ROUNDS
        assert result.converged_round is None
        assert result.snapshot_count == 3

    def test_stagnation_breaks_early(self):
        m = ConvergenceMonitor(max_rounds=5)
        m.record_round(_snap(1, "same", 2))
        m.note_correction()
        status = m.record_round(_snap(2, "same", 2))
        assert status == ConvergenceStatus.STAGNATED
        # must NOT continue to max rounds
        assert m.snapshot_count == 2
        assert m.finalize().status == ConvergenceStatus.STAGNATED

    def test_oscillation_breaks_early(self):
        m = ConvergenceMonitor(max_rounds=6)
        m.record_round(_snap(1, "a", 2))
        m.note_correction()
        m.record_round(_snap(2, "b", 2))
        m.note_correction()
        status = m.record_round(_snap(3, "a", 2))
        assert status == ConvergenceStatus.OSCILLATING
        assert m.snapshot_count == 3

    def test_divergence_breaks_early(self):
        m = ConvergenceMonitor(max_rounds=5)
        m.record_round(_snap(1, "a", 2))
        m.note_correction()
        status = m.record_round(_snap(2, "b", 4))  # 4 > 2*1.5
        assert status == ConvergenceStatus.DIVERGED

    def test_abort_short_circuits(self):
        m = ConvergenceMonitor(max_rounds=3)
        m.abort()
        status = m.record_round(_snap(1, "x", 0))
        assert status == ConvergenceStatus.ABORTED
        # aborted monitor does not append history
        assert m.snapshot_count == 0
        assert m.finalize().status == ConvergenceStatus.ABORTED

    def test_abort_after_rounds(self):
        m = ConvergenceMonitor(max_rounds=3)
        m.record_round(_snap(1, "a", 2))
        m.abort()  # e.g. LLM call raised
        assert m.aborted is True
        result = m.finalize()
        assert result.status == ConvergenceStatus.ABORTED
        # snapshot from round 1 retained for trace
        assert result.snapshot_count == 1

    def test_correction_efficiency_full_resolution(self):
        m = ConvergenceMonitor(max_rounds=3)
        m.record_round(_snap(1, "a", 2))
        m.note_correction()
        m.record_round(_snap(2, "b", 0))
        result = m.finalize()
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.correction_efficiency == 1.0
        assert result.issue_reduction_curve == (2, 0)

    def test_correction_efficiency_partial(self):
        m = ConvergenceMonitor(max_rounds=3)
        m.record_round(_snap(1, "a", 4))
        m.note_correction()
        m.record_round(_snap(2, "b", 2))
        m.note_correction()
        m.record_round(_snap(3, "c", 0))
        result = m.finalize()
        assert result.correction_efficiency == 1.0  # fully resolved by final
        assert result.total_llm_calls == 2

    def test_correction_efficiency_insufficient_rounds(self):
        m = ConvergenceMonitor(max_rounds=3)
        m.record_round(_snap(1, "a", 0))
        result = m.finalize()
        assert result.correction_efficiency is None

    def test_to_dict_serializable(self):
        m = ConvergenceMonitor(max_rounds=3)
        m.record_round(_snap(1, "a", 2))
        m.note_correction()
        m.record_round(_snap(2, "b", 0))
        d = m.finalize().to_dict()
        assert d["status"] == "converged"
        assert d["converged_round"] == 2
        assert d["total_llm_calls"] == 1
        assert d["issue_reduction_curve"] == [2, 0]
        assert len(d["rounds"]) == 2
        assert d["rounds"][0]["blocking_count"] == 2
        # JSON-serializable types only
        import json
        json.dumps(d)

    def test_invalid_max_rounds_raises(self):
        try:
            ConvergenceMonitor(max_rounds=0)
            assert False
        except ValueError:
            pass

    def test_custom_policy_chain_overrides_default(self):
        # a single policy that always returns None → Monitor never terminates until abort
        class NeverPolicy(TerminationPolicy):
            def evaluate(self, history):
                return None

        m = ConvergenceMonitor(max_rounds=3, policies=[NeverPolicy()])
        # default MaxRounds gone → without abort we would loop forever,
        # so the harness here only verifies record_round keeps returning None
        for r in (1, 2, 3):
            assert m.record_round(_snap(r, f"s{r}", 1)) is None
        # force termination via abort to obtain a result
        m.abort()
        assert m.finalize().status == ConvergenceStatus.ABORTED

    def test_termination_within_budget(self):
        # Invariant: any round sequence terminates in <= max_rounds recorded snapshots
        for max_r in (1, 2, 3, 5):
            m = ConvergenceMonitor(max_rounds=max_r)
            for r in range(1, max_r + 1):
                st = m.record_round(_snap(r, f"s{r}", 1))
                if st is not None:
                    break
            assert m.snapshot_count <= max_r
            assert m.last_status is not None