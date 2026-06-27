"""Tests for PCB circuit calculator — real engineering math, not LLM wrapping."""

import math
import pytest
from src.pcb.calculator import (
    microstrip_impedance,
    stripline_impedance,
    trace_width_for_impedance,
    differential_impedance,
    decoupling_impedance,
    capacitor_self_resonant_freq,
    analyze_decoupling_capacitor,
    decoupling_impedance_sweep,
    pdn_target_impedance,
    plane_capacitance,
    analyze_pdn,
    ipc2221_current_capacity,
    ipc2221_trace_width,
    analyze_current_capacity,
    estimate_junction_temp,
    estimate_power_from_voltage_current,
    estimate_power_from_voltage_drop,
    crosstalk_3w_rule_check,
    loop_inductance_estimate,
    via_impedance_estimate,
    PCBHealthReport,
    ImpedanceResult,
    DecouplingResult,
    PDNResult,
    CurrentCapacityResult,
    ThermalEstimate,
    EPSILON_0,
    FR4_ER,
    IPC_K_OUTER,
)


# ═══════════════════════════════════════════════════════════════
# 1. Microstrip / Stripline Impedance
# ═══════════════════════════════════════════════════════════════

class TestMicrostripImpedance:
    def test_50_ohm_on_fr4(self):
        """Standard 50Ω microstrip on FR4: ~0.3mm trace on 0.2mm substrate."""
        z0 = microstrip_impedance(0.3, 0.2, er=4.5)
        assert 40 <= z0 <= 60, f"Expected ~50Ω, got {z0}"

    def test_wider_trace_lower_impedance(self):
        """Wider trace → lower impedance."""
        z_narrow = microstrip_impedance(0.2, 0.2, er=4.5)
        z_wide = microstrip_impedance(0.5, 0.2, er=4.5)
        assert z_narrow > z_wide, f"Narrow={z_narrow}, Wide={z_wide}"

    def test_thicker_substrate_higher_impedance(self):
        """Thicker dielectric → higher impedance (stay in narrow regime)."""
        z_thin = microstrip_impedance(0.15, 0.2, er=4.5)
        z_thick = microstrip_impedance(0.15, 0.4, er=4.5)
        assert z_thick > z_thin

    def test_zero_width_returns_inf(self):
        assert microstrip_impedance(0, 0.2) == float('inf')

    def test_zero_height_returns_inf(self):
        assert microstrip_impedance(0.3, 0) == float('inf')


class TestStriplineImpedance:
    def test_stripline_lower_than_microstrip(self):
        """Stripline Z₀ < microstrip Z₀ for same geometry."""

        z_ms = microstrip_impedance(0.3, 0.2, er=4.5)
        z_sl = stripline_impedance(0.3, 0.2, er=4.5)
        # Stripline surrounded by dielectric → lower impedance
        assert z_sl < z_ms, f"MS={z_ms}, SL={z_sl}"


class TestTraceWidthForImpedance:
    def test_50_ohm_microstrip_width(self):
        """50Ω ≈ 0.3mm on 0.2mm FR4."""
        w = trace_width_for_impedance(50, 0.2, er=4.5)
        assert 0.2 <= w <= 0.45, f"Expected ~0.3mm, got {w}"

    def test_90_ohm_wider_than_50(self):
        """90Ω differential requires narrower traces."""
        w50 = trace_width_for_impedance(50, 0.2)
        w90 = trace_width_for_impedance(90, 0.2)
        assert w90 < w50

    def test_stripline_mode(self):
        w = trace_width_for_impedance(50, 0.5, kind="stripline")
        assert 0.1 <= w <= 1.0


class TestDifferentialImpedance:
    def test_diff_approx(self):
        """Differential impedance ≈ 2×Z₀ for tight coupling."""
        zdiff = differential_impedance(50, 0.15, 0.2)
        assert 70 <= zdiff <= 100, f"Expected ~90Ω, got {zdiff}"

    def test_wider_spacing_higher_diff(self):
        """Wider spacing → higher diff impedance."""
        z_close = differential_impedance(50, 0.15, 0.2)
        z_wide = differential_impedance(50, 0.5, 0.2)
        assert z_wide > z_close


# ═══════════════════════════════════════════════════════════════
# 2. Decoupling Capacitor
# ═══════════════════════════════════════════════════════════════

class TestCapacitorSelfResonantFreq:
    def test_100nf_typical(self):
        """100nF MLCC SRF ~10-50 MHz."""
        srf = capacitor_self_resonant_freq(100e-9, 1.0e-9)
        assert 5e6 <= srf <= 50e6, f"SRF={srf/1e6} MHz (expected 10-30)"

    def test_smaller_cap_higher_srf(self):
        """Smaller capacitance → higher SRF."""
        srf_100n = capacitor_self_resonant_freq(100e-9, 1.0e-9)
        srf_10n = capacitor_self_resonant_freq(10e-9, 1.0e-9)
        assert srf_10n > srf_100n

    def test_zero_cap_returns_zero(self):
        assert capacitor_self_resonant_freq(0, 1e-9) == 0.0


class TestDecouplingImpedance:
    def test_minimum_at_srf(self):
        """Impedance minimum at SRF."""
        c = 100e-9
        srf = capacitor_self_resonant_freq(c, 1.0e-9)
        z_at_srf = decoupling_impedance(c, srf, 0.03, 1.0e-9)
        z_away = decoupling_impedance(c, srf * 10, 0.03, 1.0e-9)
        assert z_at_srf < z_away, f"Z@SRF={z_at_srf}, Z@10×SRF={z_away}"

    def test_high_freq_capacitive_to_inductive(self):
        """Above SRF, capacitor behaves inductively — Z increases."""
        c = 100e-9
        srf = capacitor_self_resonant_freq(c, 1.0e-9)
        z_above = decoupling_impedance(c, srf * 100, 0.03, 1.0e-9)
        assert z_above > 9.5, f"At 100×SRF, Z should be high: {z_above}"


class TestAnalyzeDecouplingCapacitor:
    def test_0603_100nf(self):
        result = analyze_decoupling_capacitor(100e-9, "0603", "typical")
        assert 0.02 <= result.esr_ohm <= 0.05
        assert 0.3e-9 <= result.esl_h <= 2e-9
        assert result.self_resonant_freq_hz > 1e6
        assert result.effective_freq_range[1] > result.effective_freq_range[0]

    def test_unknown_package_defaults(self):
        result = analyze_decoupling_capacitor(100e-9, "XYZ", "typical")
        assert result.esr_ohm > 0  # uses default 0603


class TestDecouplingImpedanceSweep:
    def test_returns_log_spaced_points(self):
        sweep = decoupling_impedance_sweep(100e-9, 1e3, 1e9, 50)
        assert len(sweep) == 50
        for f, z in sweep:
            assert f > 0
            assert z > 0

    def test_basic_shape(self):
        """Sweep has classic V-shape (capacitive → resistive → inductive)."""
        sweep = decoupling_impedance_sweep(100e-9, 1e3, 1e9, 100)
        mid = len(sweep) // 2
        lo_z = min(z for _, z in sweep)
        hi_z = max(z for _, z in sweep)
        assert lo_z < hi_z  # V-shape


# ═══════════════════════════════════════════════════════════════
# 3. PDN Target Impedance
# ═══════════════════════════════════════════════════════════════

class TestPDNTargetImpedance:
    def test_3v3_500ma(self):
        z = pdn_target_impedance(3.3, 0.5, 5.0)
        # Z = (3.3*0.05) / (0.5*0.5) = 0.165/0.25 = 0.66Ω
        assert 0.5 <= z <= 0.8, f"Z_target={z}"

    def test_higher_ripple_higher_target(self):
        z5 = pdn_target_impedance(3.3, 0.5, 5.0)
        z10 = pdn_target_impedance(3.3, 0.5, 10.0)
        assert z10 > z5

    def test_higher_current_lower_target(self):
        """More current → tighter impedance requirement."""
        z_lo = pdn_target_impedance(3.3, 1.0)
        z_hi = pdn_target_impedance(3.3, 0.1)
        assert z_lo < z_hi


class TestPlaneCapacitance:
    def test_typical_4layer(self):
        """50×100mm board, 0.2mm plane spacing."""
        c = plane_capacitance(5000, 0.2, er=4.5)
        # ~1nF expected
        assert 0.5e-9 <= c <= 5e-9, f"C_plane={c*1e9:.2f} nF"

    def test_larger_area_more_capacitance(self):
        c_small = plane_capacitance(1000, 0.2)
        c_large = plane_capacitance(5000, 0.2)
        assert c_large > c_small


class TestAnalyzePDN:
    def test_returns_recommendations(self):
        result = analyze_pdn(3.3, 0.5, 5000, 0.2, 5.0, 100)
        assert result.target_impedance_ohm > 0
        assert result.plane_capacitance_f > 0
        assert result.decoupling_count >= 1
        assert len(result.recommended_caps) >= 3

    def test_high_current_more_caps(self):
        """Higher current → lower Z_target → harder → more caps needed."""
        lo = analyze_pdn(3.3, 0.1, 5000)  # low current → high Z_target → easy
        hi = analyze_pdn(3.3, 2.0, 5000)  # high current → low Z_target → hard
        assert hi.decoupling_count >= lo.decoupling_count


# ═══════════════════════════════════════════════════════════════
# 4. IPC-2221 Current Capacity
# ═══════════════════════════════════════════════════════════════

class TestIPC2221CurrentCapacity:
    def test_1mm_1oz_10c(self):
        """1mm trace, 1oz, 10°C → ~2.4A."""
        i = ipc2221_current_capacity(1.0, 1.0, 10.0, False)
        assert 2.0 <= i <= 3.0, f"Expected ~2.4A, got {i}"

    def test_inner_layer_lower_capacity(self):
        i_outer = ipc2221_current_capacity(1.0, 1.0, 10.0, False)
        i_inner = ipc2221_current_capacity(1.0, 1.0, 10.0, True)
        assert i_inner < i_outer

    def test_higher_temp_rise_more_current(self):
        i10 = ipc2221_current_capacity(1.0, 1.0, 10.0)
        i20 = ipc2221_current_capacity(1.0, 1.0, 20.0)
        assert i20 > i10

    def test_thicker_copper_more_current(self):
        i1oz = ipc2221_current_capacity(1.0, 1.0, 10.0)
        i2oz = ipc2221_current_capacity(1.0, 2.0, 10.0)
        assert i2oz > i1oz

    def test_wider_trace_more_current(self):
        i_narrow = ipc2221_current_capacity(0.5, 1.0, 10.0)
        i_wide = ipc2221_current_capacity(2.0, 1.0, 10.0)
        assert i_wide > i_narrow


class TestIPC2221TraceWidth:
    def test_3a_needs_1_3mm(self):
        """3A needs ~1.37mm on 1oz outer layer."""
        w = ipc2221_trace_width(3.0, 1.0, 10.0, False)
        assert 1.0 <= w <= 1.8, f"Width for 3A: {w}mm"

    def test_roundtrip(self):
        """Width(current) → current(width) ≈ original."""
        for current_a in [0.5, 1.0, 2.0, 5.0]:
            w = ipc2221_trace_width(current_a, 1.0, 10.0)
            i_back = ipc2221_current_capacity(w, 1.0, 10.0)
            assert abs(i_back - current_a) / current_a < 0.05, \
                f"Roundtrip: {current_a}A → {w}mm → {i_back}A"


class TestAnalyzeCurrentCapacity:
    def test_returns_dc_resistance(self):
        result = analyze_current_capacity(1.0, 2.0)
        assert result.dc_resistance_ohm_per_m > 0
        assert result.voltage_drop_v_per_m > 0

    def test_longer_trace_same_values(self):
        """Trace length doesn't affect current capacity calc."""
        short = analyze_current_capacity(1.0, 2.0, trace_length_mm=10)
        long_t = analyze_current_capacity(1.0, 2.0, trace_length_mm=100)
        assert short.current_a == long_t.current_a


# ═══════════════════════════════════════════════════════════════
# 5. Thermal
# ═══════════════════════════════════════════════════════════════

class TestThermalEstimate:
    def test_lqfp48_0_5w_safe(self):
        t = estimate_junction_temp(0.5, "LQFP-48")
        assert t.is_safe
        assert 40 <= t.junction_temp_c <= 60

    def test_high_power_unsafe(self):
        t = estimate_junction_temp(5.0, "SOT-23")
        assert not t.is_safe
        assert t.junction_temp_c > 150

    def test_unknown_package_default_theta(self):
        t = estimate_junction_temp(0.1, "UNKNOWN-PKG")
        assert t.theta_ja_c_per_w == 100.0  # default

    def test_ambient_temp_affects_tj(self):
        t25 = estimate_junction_temp(0.5, "TO-220", ambient_temp_c=25)
        t50 = estimate_junction_temp(0.5, "TO-220", ambient_temp_c=50)
        assert t50.junction_temp_c > t25.junction_temp_c


class TestPowerEstimation:
    def test_v_times_i(self):
        assert estimate_power_from_voltage_current(3.3, 0.5) == 1.65

    def test_ldo_power(self):
        pd = estimate_power_from_voltage_drop(5.0, 3.3, 0.5)
        assert pd == pytest.approx(0.85)

    def test_input_lower_than_output(self):
        pd = estimate_power_from_voltage_drop(3.3, 5.0, 0.5)
        assert pd == 0.0  # negative clamped


# ═══════════════════════════════════════════════════════════════
# 6. Crosstalk / EMC
# ═══════════════════════════════════════════════════════════════

class TestCrosstalk3WRule:
    def test_3w_passes(self):
        ok, ratio, _ = crosstalk_3w_rule_check(0.61, 0.2)
        assert ok
        assert ratio >= 3.0

    def test_2w_marginal(self):
        ok, ratio, _ = crosstalk_3w_rule_check(0.4, 0.2)
        assert ok  # marginal pass
        assert 2.0 <= ratio < 3.0

    def test_1w_fails(self):
        ok, ratio, _ = crosstalk_3w_rule_check(0.2, 0.2)
        assert not ok

    def test_zero_width_returns_false(self):
        ok, ratio, _ = crosstalk_3w_rule_check(0.6, 0)
        assert not ok


class TestLoopInductance:
    def test_positive_value(self):
        l = loop_inductance_estimate(100, 10)
        assert l > 0

    def test_larger_area_more_inductance(self):
        l_small = loop_inductance_estimate(50, 10)
        l_large = loop_inductance_estimate(200, 10)
        assert l_large > l_small


class TestViaImpedance:
    def test_returns_positive_values(self):
        l, c = via_impedance_estimate(0.3, 0.2)
        assert l > 0
        assert c > 0

    def test_smaller_via_more_inductance(self):
        l_small, _ = via_impedance_estimate(0.2, 0.2)
        l_large, _ = via_impedance_estimate(0.5, 0.2)
        # smaller via → higher inductance
        assert l_small > l_large


# ═══════════════════════════════════════════════════════════════
# 7. PCBHealthReport
# ═══════════════════════════════════════════════════════════════

class TestPCBHealthReport:
    def test_empty_report(self):
        r = PCBHealthReport()
        assert r.total_issues == 0
        assert r.overall_score == 100.0

    def test_with_issues(self):
        r = PCBHealthReport(
            impedance_issues=["Z₀ mismatch on NET1"],
            decoupling_issues=["Missing 100nF near U1"],
        )
        assert r.total_issues == 2
        md = r.to_markdown()
        assert "NET1" in md
        assert "U1" in md
        assert "综合评分" in md

    def test_markdown_no_issues(self):
        r = PCBHealthReport()
        md = r.to_markdown()
        assert "所有电气检查通过" in md
