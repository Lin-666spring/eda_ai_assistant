"""PCB 电气健康检查 — 电路计算引擎，纯数学分析，不依赖 LLM。

P1-6 阶段 A（2026-10-08）：原为 AppController.run_electrical_health_check
的方法体，原样迁出；controller 保留一行委托。纯移动，零逻辑改动。
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def _point_segment_distance_sq(px: float, py: float,
                               x1: float, y1: float, x2: float, y2: float) -> float:
    """点到线段的最小距离平方（串扰实测间距用）。"""
    dx, dy = x2 - x1, y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 0.0:
        ex, ey = px - x1, py - y1
        return ex * ex + ey * ey
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    ex, ey = px - (x1 + t * dx), py - (y1 + t * dy)
    return ex * ex + ey * ey


def _segments_intersect(a1, a2, b1, b2) -> bool:
    """两线段是否相交（严格内部相交判定；端点接触由点距兜底为 0）。"""
    def cross(ox, oy, ax, ay, bx, by):
        return (ax - ox) * (by - oy) - (ay - oy) * (bx - ox)

    d1 = cross(b1[0], b1[1], b2[0], b2[1], a1[0], a1[1])
    d2 = cross(b1[0], b1[1], b2[0], b2[1], a2[0], a2[1])
    d3 = cross(a1[0], a1[1], a2[0], a2[1], b1[0], b1[1])
    d4 = cross(a1[0], a1[1], a2[0], a2[1], b2[0], b2[1])
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _min_trace_spacing_mm(t1, t2):
    """两条走线间的最小间距 (mm)；任一方缺几何数据返回 None（无法判定）。

    P1-7（验收 2026-10-24）：串扰间距必须用真实几何 —— 原实现把
    min(线宽)*2 这个编造值当间距喂给 3W/2W 检查，比值恒等于 2.0 恒满足
    2W 规则，串扰问题永远为 0（虚假安全结论）。
    """
    segs1, segs2 = t1.segments or [], t2.segments or []
    if not segs1 or not segs2:
        return None
    best_sq = float("inf")
    for a in segs1:
        ax1, ay1, ax2, ay2 = a[0], a[1], a[2], a[3]
        for b in segs2:
            bx1, by1, bx2, by2 = b[0], b[1], b[2], b[3]
            if _segments_intersect((ax1, ay1), (ax2, ay2), (bx1, by1), (bx2, by2)):
                return 0.0  # 不同网络的走线几何相交 → 间距 0，必然违规
            # 线段最小距离 = 各端点到对方线段的最小距离
            for px, py, x1, y1, x2, y2 in (
                (ax1, ay1, bx1, by1, bx2, by2),
                (ax2, ay2, bx1, by1, bx2, by2),
                (bx1, by1, ax1, ay1, ax2, ay2),
                (bx2, by2, ax1, ay1, ax2, ay2),
            ):
                best_sq = min(best_sq, _point_segment_distance_sq(px, py, x1, y1, x2, y2))
    return best_sq ** 0.5


def run_electrical_health_check(pcb, bom) -> str:
    """PCB 电气健康检查 — 使用电路计算引擎进行真实工程分析。

    覆盖: 阻抗 · PDN · 去耦 · 电流承载 · 热 · 串扰

    Returns:
        JSON 格式的检查结果（含 markdown 报告与评分）
    """
    from src.pcb.calculator import (
        PCBHealthReport,
        microstrip_impedance,
        ipc2221_current_capacity,
        analyze_decoupling_capacitor,
        crosstalk_3w_rule_check,
        estimate_junction_temp,
    )

    report = PCBHealthReport()
    if not bom:
        return json.dumps({"error": "请先导入 BOM 文件"}, ensure_ascii=False)

    # 1. 电流承载检查
    for trace in (pcb.traces if pcb else []):
        if trace.width_mm > 0 and trace.net_name:
            # 估算电流需求（简化为根据网络名猜测）
            is_power = any(kw in trace.net_name.upper() for kw in ("VCC", "VDD", "VIN", "+5", "+3", "POWER", "VBAT"))
            if is_power:
                capacity = ipc2221_current_capacity(trace.width_mm)
                # 检查常见电源电流等级
                if capacity < 1.0:
                    report.current_issues.append(
                        f"电源网络 {trace.net_name}: 走线宽 {trace.width_mm}mm "
                        f"仅承载 {capacity:.2f}A，建议加宽至 ≥0.5mm"
                    )
            elif trace.width_mm < 0.15:
                report.current_issues.append(
                    f"信号线 {trace.net_name}: 线宽仅 {trace.width_mm}mm，"
                    f"接近制造极限(0.1mm)，建议加宽"
                )

    # 2. 去耦电容检查
    voltage_guess = "3.3"  # 从 BOM 推断工作电压
    for item in bom:
        desc_upper = (item.description or "").upper() + (item.value or "").upper()
        if any(kw in desc_upper for kw in ("STM32", "MCU", "FPGA", "CPLD", "ARM", "单片机")):
            # 微控制器需要去耦
            has_decoupling = False
            for other in bom:
                other_desc = (other.description or "").upper() + (other.value or "").upper()
                if any(kw in other_desc for kw in ("0.1UF", "100NF", "104", "0.1ΜF")):
                    has_decoupling = True
                    break
            if not has_decoupling:
                report.decoupling_issues.append(
                    f"{item.reference} ({item.value}) 缺少 100nF 去耦电容。"
                    f"每个数字 IC 至少需要 1 个 100nF 电容靠近 VDD 引脚。"
                )

    # 3. 热估算
    for item in bom:
        pkg = (item.package or "").upper()
        if pkg and any(kw in (item.description or "").upper()
                      for kw in ("LDO", "REGULATOR", "稳压", "AMS1117", "LM1117")):
            # 估算 LDO 功耗
            power_w = 0.5  # 粗略估计
            t = estimate_junction_temp(power_w, pkg)
            if not t.is_safe:
                report.thermal_issues.append(
                    f"{item.reference} ({item.value}, {pkg}): "
                    f"估计结温 {t.junction_temp_c}°C 超过安全限 {125}°C。"
                    f"建议改用散热更好的封装或添加散热器。"
                )
            elif t.junction_temp_c > 85:
                report.thermal_issues.append(
                    f"{item.reference} ({item.value}, {pkg}): "
                    f"估计结温 {t.junction_temp_c}°C 偏高，建议关注散热。"
                )

    # 4. 串扰/EMC
    # P1-7（验收 2026-10-24）：间距用真实几何计算；缺几何数据的走线对记为
    # "无法判定"并如实上报 —— 数据不足时宁可承认无法判定，也绝不假通过
    # （"所有电气检查通过"的虚假安全结论比漏报更危险）。
    crosstalk_skipped = 0
    if pcb and pcb.traces:
        limit = min(20, len(pcb.traces))
        for i in range(limit):
            for j in range(i + 1, limit):
                t1, t2 = pcb.traces[i], pcb.traces[j]
                # 简化为检查同一层的相邻走线
                if t1.layer != t2.layer or t1.width_mm <= 0 or t2.width_mm <= 0:
                    continue
                if (t1.net_name or "") == (t2.net_name or ""):
                    # 同网络走线等电位/物理相连，间距不构成串扰风险
                    continue
                spacing = _min_trace_spacing_mm(t1, t2)
                if spacing is None:
                    crosstalk_skipped += 1
                    continue
                span = min(t1.width_mm, t2.width_mm)
                ok, ratio, msg = crosstalk_3w_rule_check(spacing, span)
                if not ok:
                    report.crosstalk_issues.append(
                        f"{t1.net_name} ↔ {t2.net_name}: {msg}"
                        f"（实测间距 {spacing:.3f}mm，基准线宽 {span:.3f}mm）"
                    )
                    break
    if crosstalk_skipped:
        report.crosstalk_issues.append(
            f"{crosstalk_skipped} 对走线缺少几何数据，串扰间距无法判定（未计入通过）"
        )

    # 5. 阻抗估计
    if pcb and pcb.traces:
        for trace in pcb.traces[:10]:
            if trace.width_mm > 0:
                z0 = microstrip_impedance(trace.width_mm, 0.2)  # 假设 4层板 0.2mm 介质
                if 45 <= z0 <= 55:
                    pass  # 50Ω 附近，正常
                elif z0 < 30 or z0 > 80:
                    report.impedance_issues.append(
                        f"网络 {trace.net_name or '?'}: 线宽 {trace.width_mm}mm → "
                        f"Z₀≈{z0}Ω (目标 50Ω)。建议调整为差分或加宽走线。"
                    )

    # 综合评分
    total = len(report.impedance_issues) + len(report.pdn_issues) + \
            len(report.decoupling_issues) + len(report.current_issues) + \
            len(report.thermal_issues) + len(report.crosstalk_issues)
    report.overall_score = max(50, 100 - total * 8)

    logger.info("Electrical health check: score=%.0f, issues=%d", report.overall_score, total)
    return json.dumps({
        "ok": True,
        "markdown": report.to_markdown(),
        "score": report.overall_score,
        "issues": report.total_issues,
        "details": {
            "impedance": report.impedance_issues,
            "pdn": report.pdn_issues,
            "decoupling": report.decoupling_issues,
            "current": report.current_issues,
            "thermal": report.thermal_issues,
            "crosstalk": report.crosstalk_issues,
        },
    }, ensure_ascii=False)
