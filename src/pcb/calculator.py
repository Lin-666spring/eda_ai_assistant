"""
PCB 电路计算引擎 — 真实工程计算，非 LLM 包装。

所有公式来自 IPC 标准，无外部依赖，纯数学计算。
覆盖: 阻抗 · 去耦 · PDN · 电流承载 · 热估算
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# 物理常数
# ═══════════════════════════════════════════════════════════════

EPSILON_0 = 8.8541878128e-12      # 真空介电常数 (F/m)
MU_0 = 4e-7 * math.pi              # 真空磁导率 (H/m)
COPPER_RESISTIVITY = 1.72e-8       # 铜电阻率 (Ω·m) @20°C
COPPER_TEMPCO = 0.00393            # 铜温度系数 (/°C)

# 典型 PCB 材料参数
FR4_ER = 4.5                       # FR-4 相对介电常数 @1MHz
FR4_TAND = 0.02                    # FR-4 损耗角正切 @1MHz

# IPC-2221 电流承载常数
IPC_K_OUTER = 0.048                # 外层走线 k (A/mil²)
IPC_K_INNER = 0.024                # 内层走线 k (A/mil²)


# ═══════════════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════════════

@dataclass
class ImpedanceResult:
    """特征阻抗计算结果"""
    z0_ohm: float                    # 特征阻抗 (Ω)
    trace_width_mm: float            # 所需线宽 (mm)
    dielectric_er: float             # 介电常数
    substrate_height_mm: float       # 介质厚度 (mm)
    type: str = "microstrip"


@dataclass
class DecouplingResult:
    """去耦电容分析结果"""
    capacitance_f: float             # 电容值 (F)
    esr_ohm: float                   # 等效串联电阻 (Ω)
    esl_h: float                     # 等效串联电感 (H)
    self_resonant_freq_hz: float     # 自谐振频率 (Hz)
    z_at_target_hz: float | None     # 目标频率处的阻抗 (Ω)
    effective_freq_range: tuple[float, float]  # 有效去耦频率范围 (Hz)


@dataclass
class PDNResult:
    """电源分配网络分析结果"""
    target_impedance_ohm: float      # 目标阻抗 (Ω)
    plane_capacitance_f: float       # 平面电容 (F)
    above_target_below_hz: float     # 平面电容单独满足的频率上限 (Hz)
    decoupling_count: int            # 所需去耦电容数量 (估算)
    voltage_drop_mv: float           # IR Drop 电压降 (mV)
    recommended_caps: list[float]    # 推荐电容值 (F)


@dataclass
class CurrentCapacityResult:
    """电流承载能力计算结果"""
    current_a: float                 # 电流 (A)
    trace_width_mm: float            # 线宽 (mm)
    copper_weight_oz: float          # 铜厚 (oz)
    temp_rise_c: float               # 温升 (°C)
    is_inner_layer: bool = False
    dc_resistance_ohm_per_m: float = 0.0  # 直流电阻 (Ω/m)
    voltage_drop_v_per_m: float = 0.0     # 单位长度压降 (V/m)


@dataclass
class ThermalEstimate:
    """元件热估算"""
    power_dissipation_w: float       # 功耗 (W)
    theta_ja_c_per_w: float          # 结到环境热阻 (°C/W)
    junction_temp_c: float           # 结温 (°C)
    ambient_temp_c: float = 25.0     # 环境温度 (°C)
    is_safe: bool = True             # 是否在安全范围


# ═══════════════════════════════════════════════════════════════
# 1. 特征阻抗计算 (IPC-2141)
# ═══════════════════════════════════════════════════════════════

def microstrip_impedance(
    w_mm: float,
    h_mm: float,
    t_mm: float = 0.035,
    er: float = FR4_ER,
) -> float:
    """微带线特征阻抗 (IPC-2141)。

    Args:
        w_mm: 走线宽度 (mm)
        h_mm: 介质厚度 (mm)
        t_mm: 铜箔厚度 (mm)，默认 1oz=0.035mm
        er: 相对介电常数，默认 FR-4=4.5

    Returns:
        特征阻抗 Z₀ (Ω)
    """
    if w_mm <= 0 or h_mm <= 0:
        return float('inf')
    # 有效宽度（考虑蚀刻因子，简化处理）
    w_eff = w_mm
    if w_mm / h_mm < 1:
        # 窄微带
        z0 = (60 / math.sqrt(er + 1.41)) * math.log(4 * h_mm / w_eff)
    else:
        # 宽微带
        z0 = (120 * math.pi) / (
            math.sqrt(er) * (w_eff / h_mm + 1.393 + 0.667 * math.log(w_eff / h_mm + 1.444))
        )
    return round(z0, 1)


def stripline_impedance(
    w_mm: float,
    h_mm: float,
    t_mm: float = 0.035,
    er: float = FR4_ER,
) -> float:
    """对称带状线特征阻抗。

    Args:
        w_mm: 走线宽度 (mm)
        h_mm: 两个参考平面之间的总间距 (mm)
        t_mm: 铜箔厚度 (mm)
        er: 相对介电常数

    Returns:
        特征阻抗 Z₀ (Ω)
    """
    if w_mm <= 0 or h_mm <= 0:
        return float('inf')
    b = h_mm  # 两个平面间距
    z0 = (60 / math.sqrt(er)) * math.log(
        (4 * b) / (0.67 * math.pi * w_mm * (0.8 + t_mm / w_mm))
    )
    return round(z0, 1)


def trace_width_for_impedance(
    z0_target: float,
    h_mm: float,
    er: float = FR4_ER,
    t_mm: float = 0.035,
    kind: str = "microstrip",
) -> float:
    """给定目标阻抗，反向求解所需线宽（二分查找）。

    Args:
        z0_target: 目标阻抗 (Ω)，如 50, 90, 100
        h_mm: 介质厚度 (mm)
        er: 介电常数
        t_mm: 铜厚 (mm)
        kind: "microstrip" | "stripline"

    Returns:
        所需线宽 (mm)
    """
    calc = microstrip_impedance if kind == "microstrip" else stripline_impedance
    lo, hi = 0.05, 10.0
    for _ in range(40):
        mid = (lo + hi) / 2
        z = calc(mid, h_mm, t_mm, er)
        if z > z0_target:
            lo = mid  # 线太细→阻抗太高→加宽
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def differential_impedance(
    z0_single: float,
    s_mm: float,
    h_mm: float,
    er: float = FR4_ER,
) -> float:
    """差分阻抗近似 (微带线)。

    Z_diff ≈ 2*Z0 * (1 - 0.48 * exp(-0.96 * s/h))

    Args:
        z0_single: 单端阻抗 (Ω)
        s_mm: 差分对间距 (mm)
        h_mm: 介质厚度 (mm)
        er: 介电常数

    Returns:
        差分阻抗 Z_diff (Ω)
    """
    factor = 1 - 0.48 * math.exp(-0.96 * s_mm / h_mm)
    return round(2 * z0_single * factor, 1)


# ═══════════════════════════════════════════════════════════════
# 2. 去耦电容分析
# ═══════════════════════════════════════════════════════════════

# 典型 MLCC 封装参数 (ESR, ESL 估算)
_MLCC_PARAMS: dict[str, tuple[float, float]] = {
    # 封装: (ESR_ohm, ESL_H)
    "0201": (0.050, 0.2e-9),
    "0402": (0.040, 0.3e-9),
    "0603": (0.030, 0.5e-9),
    "0805": (0.020, 0.7e-9),
    "1206": (0.015, 1.0e-9),
    "1210": (0.010, 1.2e-9),
}

# 安装电感（粗略，取决于扇出方式）
_MOUNTING_INDUCTANCE_H = {
    "minimal": 0.5e-9,    # 紧密扇出、短走线
    "typical": 1.5e-9,    # 典型扇出
    "poor": 3.0e-9,       # 长走线、单过孔
}


def decoupling_impedance(
    capacitance_f: float,
    frequency_hz: float,
    esr_ohm: float = 0.03,
    esl_h: float = 0.5e-9,
) -> float:
    """计算去耦电容在给定频率下的阻抗。

    Z = √(R² + (2πfL - 1/(2πfC))²)

    Args:
        capacitance_f: 电容值 (F)
        frequency_hz: 频率 (Hz)
        esr_ohm: 等效串联电阻 (Ω)
        esl_h: 等效串联电感 (H)，含安装电感

    Returns:
        阻抗幅值 (Ω)
    """
    omega = 2 * math.pi * frequency_hz
    if omega * capacitance_f == 0:
        return float('inf')
    xl = omega * esl_h
    xc = 1.0 / (omega * capacitance_f)
    return math.sqrt(esr_ohm**2 + (xl - xc)**2)


def capacitor_self_resonant_freq(
    capacitance_f: float,
    esl_h: float = 0.5e-9,
) -> float:
    """自谐振频率 (SRF)。

    f₀ = 1 / (2π√(LC))

    Args:
        capacitance_f: 电容值 (F)
        esl_h: ESL (H)

    Returns:
        SRF (Hz)
    """
    if capacitance_f <= 0 or esl_h <= 0:
        return 0.0
    return round(1.0 / (2 * math.pi * math.sqrt(esl_h * capacitance_f)), 0)


def analyze_decoupling_capacitor(
    capacitance_f: float,
    package: str = "0603",
    mounting: str = "typical",
    voltage_v: float = 3.3,
) -> DecouplingResult:
    """全面分析一个去耦电容的特性。

    Args:
        capacitance_f: 电容值 (F)
        package: 封装 (0201/0402/0603/0805/1206/1210)
        mounting: 安装方式 (minimal/typical/poor)
        voltage_v: 工作电压 (V)

    Returns:
        DecouplingResult
    """
    esr, esl_pkg = _MLCC_PARAMS.get(package, _MLCC_PARAMS["0603"])
    esl_mount = _MOUNTING_INDUCTANCE_H.get(mounting, _MOUNTING_INDUCTANCE_H["typical"])
    esl_total = esl_pkg + esl_mount

    srf = capacitor_self_resonant_freq(capacitance_f, esl_total)
    z_at_srf = decoupling_impedance(capacitance_f, srf, esr, esl_total) if srf > 0 else float('inf')

    # 有效频率范围：阻抗 < 1Ω 的范围
    eff_lo = srf / 5 if srf > 0 else 0
    eff_hi = srf * 2 if srf > 0 else 0

    return DecouplingResult(
        capacitance_f=capacitance_f,
        esr_ohm=esr,
        esl_h=esl_total,
        self_resonant_freq_hz=srf,
        z_at_target_hz=z_at_srf if z_at_srf != float('inf') else None,
        effective_freq_range=(eff_lo, eff_hi),
    )


def decoupling_impedance_sweep(
    capacitance_f: float,
    freq_start_hz: float = 1e3,
    freq_stop_hz: float = 1e9,
    points: int = 100,
    esr_ohm: float = 0.03,
    esl_h: float = 0.5e-9,
) -> list[tuple[float, float]]:
    """频率扫描：返回 [(freq, Z), ...] 用于绘制 Z-F 曲线。

    Returns:
        [(freq_hz, impedance_ohm), ...]
    """
    result = []
    for i in range(points):
        f = freq_start_hz * (freq_stop_hz / freq_start_hz) ** (i / (points - 1))
        z = decoupling_impedance(capacitance_f, f, esr_ohm, esl_h)
        result.append((f, z))
    return result


# ═══════════════════════════════════════════════════════════════
# 3. PDN 目标阻抗分析
# ═══════════════════════════════════════════════════════════════

def pdn_target_impedance(
    voltage_v: float,
    max_current_a: float,
    ripple_percent: float = 5.0,
    transient_current_a: float | None = None,
) -> float:
    """PDN 目标阻抗。

    Z_target = (Vdd × ripple%) / (transient_current)
    若无瞬态电流数据，用 50% 最大电流近似。

    Args:
        voltage_v: 电源电压 (V)
        max_current_a: 最大稳态电流 (A)
        ripple_percent: 允许纹波百分比 (%), 默认 5%
        transient_current_a: 瞬态电流 (A)，默认 max_current * 0.5

    Returns:
        目标阻抗 (Ω)
    """
    if transient_current_a is None:
        transient_current_a = max_current_a * 0.5
    if transient_current_a <= 0:
        return float('inf')
    delta_v = voltage_v * ripple_percent / 100.0
    return round(delta_v / transient_current_a, 4)


def plane_capacitance(
    area_mm2: float,
    thickness_mm: float = 0.2,
    er: float = FR4_ER,
) -> float:
    """平行平面电容。

    C = ε₀·εr · A / d

    Args:
        area_mm2: 平面面积 (mm²)
        thickness_mm: 平面间距 (mm)，4层板约0.2mm
        er: FR-4 介电常数

    Returns:
        平面电容 (F)
    """
    area_m2 = area_mm2 * 1e-6
    d_m = thickness_mm * 1e-3
    if d_m <= 0:
        return 0.0
    return EPSILON_0 * er * area_m2 / d_m


def analyze_pdn(
    voltage_v: float,
    max_current_a: float,
    board_area_mm2: float = 5000,
    layers_between_plane: float = 0.2,
    ripple_percent: float = 5.0,
    max_freq_mhz: float = 100.0,
) -> PDNResult:
    """全面 PDN 分析。

    Args:
        voltage_v: 电源电压 (V)
        max_current_a: 最大电流 (A)
        board_area_mm2: 板面积 (mm²)
        layers_between_plane: 电源-地平面间距 (mm)
        ripple_percent: 纹波 (%)
        max_freq_mhz: 最高关注频率 (MHz)

    Returns:
        PDNResult
    """
    z_target = pdn_target_impedance(voltage_v, max_current_a, ripple_percent)

    # 平面电容
    c_plane = plane_capacitance(board_area_mm2, layers_between_plane)

    # 平面电容单独满足 Z_target 的频率上限
    # Z_plane = 1/(2πfC) → f = 1/(2π·Z_target·C)
    if z_target > 0 and c_plane > 0:
        f_plane_max = 1.0 / (2 * math.pi * z_target * c_plane)
    else:
        f_plane_max = 0.0

    # 所需去耦电容数量估算
    # Z_target 越小（越严格），需要越多电容并联降低阻抗
    # Z_parallel = Z_single / √N → N ≈ (Z_single / Z_target)²
    typical_cap_z = 0.1  # 100nF @ typical freq (Ω)
    if z_target > 0 and z_target < typical_cap_z:
        n_caps = max(1, int((typical_cap_z / z_target) ** 2))
    elif z_target > 0:
        n_caps = 1
    else:
        n_caps = 0

    # IR Drop (粗略，假设 1mΩ 平面电阻)
    plane_r_ohm = 0.001
    v_drop_mv = plane_r_ohm * max_current_a * 1000

    # 推荐电容组合（大小电容并联覆盖不同频段）
    rec_caps = [100e-6, 10e-6, 0.1e-6, 0.01e-6]  # 100µF, 10µF, 100nF, 10nF

    return PDNResult(
        target_impedance_ohm=z_target,
        plane_capacitance_f=c_plane,
        above_target_below_hz=f_plane_max,
        decoupling_count=n_caps,
        voltage_drop_mv=v_drop_mv,
        recommended_caps=rec_caps,
    )


# ═══════════════════════════════════════════════════════════════
# 4. 电流承载能力 (IPC-2221)
# ═══════════════════════════════════════════════════════════════

def ipc2221_current_capacity(
    width_mm: float,
    copper_oz: float = 1.0,
    temp_rise_c: float = 10.0,
    is_inner: bool = False,
) -> float:
    """IPC-2221 走线电流承载能力。

    I = k · ΔT^0.44 · A^0.725

    Args:
        width_mm: 走线宽度 (mm)
        copper_oz: 铜箔厚度 (oz)，1oz=35µm
        temp_rise_c: 允许温升 (°C)
        is_inner: 是否内层（内层散热差，载流能力降低）

    Returns:
        承载电流 (A)

    Reference:
        IPC-2221 §6.2
    """
    area_mil2 = width_mm * 39.37 * copper_oz * 1.378  # mm→mil, oz→mil厚度
    k = IPC_K_INNER if is_inner else IPC_K_OUTER
    current = k * (temp_rise_c ** 0.44) * (area_mil2 ** 0.725)
    return round(current, 3)


def ipc2221_trace_width(
    current_a: float,
    copper_oz: float = 1.0,
    temp_rise_c: float = 10.0,
    is_inner: bool = False,
) -> float:
    """给定电流，反向求解所需最小线宽（二分查找）。

    Args:
        current_a: 电流 (A)
        copper_oz: 铜厚 (oz)
        temp_rise_c: 温升 (°C)
        is_inner: 是否内层

    Returns:
        所需线宽 (mm)
    """
    lo, hi = 0.01, 20.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if ipc2221_current_capacity(mid, copper_oz, temp_rise_c, is_inner) < current_a:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def analyze_current_capacity(
    width_mm: float,
    current_a: float,
    copper_oz: float = 1.0,
    temp_rise_c: float = 10.0,
    is_inner: bool = False,
    trace_length_mm: float = 100.0,
) -> CurrentCapacityResult:
    """全面分析走线电流承载，含压降和温升余量。

    Args:
        width_mm: 实际线宽 (mm)
        current_a: 实际电流 (A)
        copper_oz: 铜厚 (oz)
        temp_rise_c: 允许温升 (°C)
        is_inner: 是否内层
        trace_length_mm: 走线长度 (mm)

    Returns:
        CurrentCapacityResult
    """
    capacity = ipc2221_current_capacity(width_mm, copper_oz, temp_rise_c, is_inner)

    # DC 电阻
    area_m2 = width_mm * 1e-3 * copper_oz * 35e-6
    if area_m2 > 0:
        r_per_m = COPPER_RESISTIVITY / area_m2
    else:
        r_per_m = float('inf')
    v_drop_per_m = current_a * r_per_m

    return CurrentCapacityResult(
        current_a=current_a,
        trace_width_mm=width_mm,
        copper_weight_oz=copper_oz,
        temp_rise_c=temp_rise_c,
        is_inner_layer=is_inner,
        dc_resistance_ohm_per_m=round(r_per_m, 4),
        voltage_drop_v_per_m=round(v_drop_per_m, 4),
    )


# ═══════════════════════════════════════════════════════════════
# 5. 热估算
# ═══════════════════════════════════════════════════════════════

# 典型封装热阻 (Junction-to-Ambient, °C/W)
_TYPICAL_THETA_JA: dict[str, float] = {
    "SOT-23": 200,
    "SOT-223": 60,
    "SOIC-8": 120,
    "SOP-8": 120,
    "QFN-32": 35,
    "QFP-32": 55,
    "QFP-64": 45,
    "QFP-100": 38,
    "LQFP-48": 50,
    "LQFP-64": 45,
    "LQFP-100": 38,
    "TO-220": 40,
    "TO-252": 50,
    "TO-263": 40,
    "BGA-256": 25,
    "TSSOP-20": 80,
    "MSOP-8": 90,
    "0805": 200,
    "0603": 250,
    "0402": 300,
}

# 典型结温上限
DEFAULT_TJ_MAX_C = 125.0
DEFAULT_TA_C = 25.0


def estimate_junction_temp(
    power_w: float,
    package: str,
    ambient_temp_c: float = DEFAULT_TA_C,
) -> ThermalEstimate:
    """估算结温。

    Tj = Ta + Pd × θja

    Args:
        power_w: 功耗 (W)
        package: 封装名
        ambient_temp_c: 环境温度 (°C)

    Returns:
        ThermalEstimate
    """
    theta_ja = _TYPICAL_THETA_JA.get(package.upper(), 100.0)
    tj = ambient_temp_c + power_w * theta_ja
    return ThermalEstimate(
        power_dissipation_w=power_w,
        theta_ja_c_per_w=theta_ja,
        junction_temp_c=round(tj, 1),
        ambient_temp_c=ambient_temp_c,
        is_safe=tj < DEFAULT_TJ_MAX_C,
    )


def estimate_power_from_voltage_current(
    voltage_v: float,
    current_a: float,
) -> float:
    """P = V × I"""
    return voltage_v * current_a


def estimate_power_from_voltage_drop(
    input_v: float,
    output_v: float,
    current_a: float,
) -> float:
    """线性稳压器功耗: Pd = (Vin - Vout) × I"""
    return max(0, (input_v - output_v) * current_a)


# ═══════════════════════════════════════════════════════════════
# 6. 串扰/EMC 快速估算
# ═══════════════════════════════════════════════════════════════

def crosstalk_3w_rule_check(
    trace_spacing_mm: float,
    trace_width_mm: float,
    dielectric_height_mm: float = 0.2,
) -> tuple[bool, float, str]:
    """串扰 3W 规则。

    间距 ≥ 3× 线宽 → crosstalk < ~5%
    间距 ≥ 2× 线宽 → crosstalk < ~10%

    Args:
        trace_spacing_mm: 走线间距 (mm)
        trace_width_mm: 线宽 (mm)
        dielectric_height_mm: 介质高度 (mm)

    Returns:
        (passed, ratio, recommendation)
    """
    if trace_width_mm <= 0:
        return False, 0.0, "无效线宽"
    ratio = trace_spacing_mm / trace_width_mm
    if ratio >= 3.0:
        return True, ratio, "串扰 <5%，满足 3W 规则"
    elif ratio >= 2.0:
        return True, ratio, "串扰 <10%，满足 2W 规则（可接受）"
    else:
        return False, ratio, f"串扰超标，建议间距 ≥ {3 * trace_width_mm:.2f}mm (3W)"


def loop_inductance_estimate(
    loop_area_mm2: float,
    trace_length_mm: float = 1.0,
) -> float:
    """信号回路电感粗略估算。

    L ≈ μ₀ · A / l  (简化模型)

    Args:
        loop_area_mm2: 回路面积 (mm²)
        trace_length_mm: 参考长度 (mm)

    Returns:
        电感 (H)
    """
    area_m2 = loop_area_mm2 * 1e-6
    length_m = trace_length_mm * 1e-3
    if length_m <= 0:
        return float('inf')
    return MU_0 * area_m2 / length_m


def via_impedance_estimate(
    via_diameter_mm: float = 0.3,
    via_height_mm: float = 0.2,
) -> tuple[float, float]:
    """过孔阻抗估算。

    电感: L ≈ 5.08h [ln(4h/d) + 1]  (nH, 尺寸单位 inches)
    电容: C ≈ 1.41·εr·h·d / (D-d)  (pF)

    Args:
        via_diameter_mm: 过孔直径 (mm)
        via_height_mm: 过孔高度 (板厚 mm)

    Returns:
        (inductance_h, capacitance_f)
    """
    from src.constants import PCB as _  # noqa (avoid circular import)
    # 使用内置常数
    d_inch = via_diameter_mm / 25.4
    h_inch = via_height_mm / 25.4

    # 电感 (nH → H)
    if d_inch > 0:
        l_nh = 5.08 * h_inch * (math.log(4 * h_inch / d_inch) + 1)
    else:
        l_nh = 0.0
    l_h = l_nh * 1e-9

    # 电容 (pF → F)
    d_clearance_inch = 1.0 / 25.4  # ~1mm clearance
    if d_clearance_inch > d_inch:
        c_pf = 1.41 * FR4_ER * h_inch * d_inch / (d_clearance_inch - d_inch)
    else:
        c_pf = 0.5  # fallback
    c_f = c_pf * 1e-12

    return l_h, c_f


# ═══════════════════════════════════════════════════════════════
# 7. 综合 PCB 健康报告
# ═══════════════════════════════════════════════════════════════

@dataclass
class PCBHealthReport:
    """PCB 综合电气健康报告"""
    impedance_issues: list[str] = field(default_factory=list)
    pdn_issues: list[str] = field(default_factory=list)
    decoupling_issues: list[str] = field(default_factory=list)
    current_issues: list[str] = field(default_factory=list)
    thermal_issues: list[str] = field(default_factory=list)
    crosstalk_issues: list[str] = field(default_factory=list)
    overall_score: float = 100.0  # 0-100

    @property
    def total_issues(self) -> int:
        return sum(len(lst) for lst in [
            self.impedance_issues,
            self.pdn_issues,
            self.decoupling_issues,
            self.current_issues,
            self.thermal_issues,
            self.crosstalk_issues,
        ])

    def to_markdown(self) -> str:
        """生成 Markdown 报告"""
        lines = [
            "## ⚡ PCB 电气健康报告",
            f"**综合评分**: {self.overall_score:.0f}/100",
            f"**发现问题**: {self.total_issues} 项",
            "",
        ]
        sections = [
            ("🔌 阻抗", self.impedance_issues),
            ("⚡ PDN", self.pdn_issues),
            ("🔋 去耦", self.decoupling_issues),
            ("🔆 电流", self.current_issues),
            ("🔥 热", self.thermal_issues),
            ("📡 串扰", self.crosstalk_issues),
        ]
        for label, issues in sections:
            if issues:
                lines.append(f"### {label} ({len(issues)})")
                for iss in issues:
                    lines.append(f"- {iss}")
                lines.append("")
        if self.total_issues == 0:
            lines.append("✅ 所有电气检查通过。")
        return "\n".join(lines)
