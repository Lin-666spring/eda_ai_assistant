"""布局位置类规则 —— 从 checker.py 机械迁出（P1-6 阶段B，纯移动）。"""

import logging
import re
from ..constants import PCB

from .base import (
    RuleSeverity,
    RuleViolation,
    _COMPONENT_MODEL_PATH,
    _COMPONENT_VOCAB_PATH,
    _DCDC_DESC_KW,
    _HIGH_SPEED_IF_KW,
    _HIGH_SPEED_NET_KW,
    _LOW_SPEED_NET_KW,
    _ML_CONFIDENCE_THRESHOLD,
    _POWER_OR_GROUND_KW,
    _VOLTAGE_TOKEN_RE,
    _classify_component,
    _classify_component_fine,
    _component_count,
    _component_model_attempted,
    _component_predictor,
    _extract_voltage_rating,
    _init_component_model,
    _is_dcdc_part,
    _is_inner_layer,
    _is_power_or_ground_net,
    _kw_hit,
    _net_class,
    _parallel_overlap_len,
    _parse_capacitance,
    _parse_component_value,
    _pt_seg_dist,
    _seg_seg_dist,
    _xy,
    group_violations_by_component,
    rule_kind,
)

logger = logging.getLogger(__name__)

class LayoutRulesMixin:
    """方法集由 facade DesignRuleChecker 组合；此处无状态、无 __init__。"""


    # ═══ Position-data rules ═══

    def _check_analog_digital_separation(self, bom_items, positions, netlist):
        """模数分离：模拟/数字元件应物理分区"""
        if not positions or not bom_items: return []
        violations = []
        acoords, dcoords = [], []
        for item in bom_items:
            desc = f"{getattr(item, 'description', '') or ''} {getattr(item, 'part_number', '') or ''}".lower()
            # 2026-09-24 抽查修正：短关键词（AD/DA/OP…）改为词边界匹配，
            # 否则 "PicoBlade" 里的 "ad" 会让 FPC 连接器被当成模拟器件。
            is_a = _kw_hit(desc, PCB.ANALOG_COMPONENT_KW)
            is_d = _kw_hit(desc, PCB.DIGITAL_COMPONENT_KW)
            ref = getattr(item, "reference", "")
            fr = ref.split(",")[0].strip() if ref else ""
            if fr and fr in positions:
                x, y = _xy(positions[fr])
                if is_a: acoords.append((x, y, fr))
                elif is_d: dcoords.append((x, y, fr))
        if not acoords or not dcoords: return violations
        min_sep = PCB.AD_SEPARATION_MIN_MM
        cross = []
        for ax, ay, ar in acoords:
            for dx, dy, dr in dcoords:
                dist = ((ax - dx) ** 2 + (ay - dy) ** 2) ** 0.5
                if dist < min_sep:
                    cross.append((ar, dr, round(dist, 2)))
        if cross:
            pairs = ", ".join(f"{a}/{d}" for a, d, _ in cross[:5])
            more = f" ...等 {len(cross)} 对" if len(cross) > 5 else ""
            def _c(cs): return (sum(c[0] for c in cs)/len(cs), sum(c[1] for c in cs)/len(cs))
            acx, acy = _c(acoords); dcx, dcy = _c(dcoords)
            cd = ((acx - dcx) ** 2 + (acy - dcy) ** 2) ** 0.5
            violations.append(RuleViolation(
                rule_name="模数分离检查", description=f"发现 {len(cross)} 对模拟-数字元件间距<{min_sep}mm{more}",
                severity=RuleSeverity.WARNING, location=pairs,
                suggestion=f"模数区中心距 {cd:.1f}mm。分区布局+独立地铺铜+单点连接(0Ω/磁珠)。",
                theory="数字电路高频开关产生丰富谐波噪声，通过地平面耦合到模拟区→ADC 精度↓、运放纹波↑。模拟数字地应在 ADC 下方单点连接(0Ω/磁珠)，避免数字回路电流流经模拟地。"))
        return violations


    def _check_component_edge_clearance(self, bom_items, positions, netlist):
        """板边间距：元件距 PCB 板边应 ≥3mm（按板框包围盒算真实边距）

        2026-10-09 修正：旧判据拿绝对坐标比 `x<3 or y<3`，不减板框原点——
        原点偏移的板上恒不响，原点在 0 附近的板只判了左/下两条边。
        板框退回「铜包围盒」(source=copper) 时边距恒为 0、无判定意义，
        直接跳过（与走线板边规则同一守卫）。
        """
        if not positions: return []
        pcb = self._pcb_data
        bo = (pcb.board_outline or {}) if pcb else {}
        if bo.get("source") != "outline":
            return []
        mc = 3.0
        minx, miny = bo["min_x_mm"], bo["min_y_mm"]
        maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
        near = []
        for item in bom_items:
            ref = getattr(item, "reference", "")
            if ref and ref in positions:
                x, y = _xy(positions[ref])
                if min(x - minx, maxx - x, y - miny, maxy - y) < mc: near.append(ref)
        if near:
            return [RuleViolation(
                rule_name="板边间距检查", description=f"{len(near)} 个元件距板边 <{mc}mm: {', '.join(near[:5])}",
                severity=RuleSeverity.WARNING,
                suggestion=f"元件距板边 ≥{int(mc)}mm，高元件需更大间距",
                theory="PCB 板边在拼板分离、波峰焊夹持、机壳装配中承受最大机械应力。IPC-2222 §8.2 建议元件体距板边 ≥2.5mm，高元件≥5mm。传送边禁布区≥3mm。")]
        return []


    def _check_decoupling_proximity(self, bom_items, positions, netlist):
        """去耦电容距离：去耦电容应靠近 IC 电源引脚"""
        if not positions: return []
        violations = []
        # 2026-09-24 抽查修正：原判据把「除电阻/电感外的所有元件」都当 IC——
        # 咪头、蜂鸣器、电池座、螺丝孔全成了 IC，报出的「N 个去耦电容」其实是配对数。
        # 现在用统一的元件分类（位号前缀 + 封装 + value + ML 模型）。
        ics, caps = [], []
        for item in bom_items:
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if ref not in positions:
                continue
            kind = _classify_component(item)
            if kind == "cap":
                caps.append((ref, positions[ref]))
            elif kind == "ic":
                ics.append((ref, positions[ref]))
        if not ics: return violations
        md = 15.0
        far = []
        for cr, cp in caps:
            cx, cy = _xy(cp)
            nearest = None      # (距离, IC 位号)：按「到最近 IC」判定
            for ir, ip in ics:
                ix, iy = _xy(ip)
                dist = ((cx - ix) ** 2 + (cy - iy) ** 2) ** 0.5
                if nearest is None or dist < nearest[0]:
                    nearest = (dist, ir)
            # 2026-09-24 抽查修正：原来「任一 IC 距该电容 >md」就算——板上总有远端 IC，
            # 于是 73/76 块板都响。现在只看它到**最近** IC 的距离。
            if nearest is not None and nearest[0] > md:
                far.append((cr, nearest[1], round(nearest[0], 1)))
        if far:
            ps = ", ".join(f"{c}/{i}({d}mm)" for c, i, d in far[:3])
            violations.append(RuleViolation(
                rule_name="去耦电容距离检查",
                description=(f"{len({c for c, _, _ in far})} 个去耦电容距 IC >{md}mm"
                             f"（{len(far)} 对电容-IC 组合）: {ps}"),
                severity=RuleSeverity.WARNING,
                suggestion=f"去耦电容距 IC 电源引脚 ≤{int(md)}mm。距离每增加 1cm，退耦效果显著下降。",
                theory="PCB 走线寄生电感≈5~10nH/cm。去耦电容距 IC 每增 1cm，环路 L≈+8nH——10ns 内切换 50mA 时 Vdrop=L·di/dt=8nH×5×10⁶A/s=40mV。多层板建议电容同层距引脚≤10mm。"))
        return violations


    def _check_crystal_proximity(self, bom_items, positions, netlist):
        """晶振靠近 MCU：晶振应尽可能靠近 MCU 振荡器引脚"""
        if not positions: return []
        violations = []
        crystal_kw = ["晶振", "crystal", "XTAL"]
        mcu_kw = ["MCU", "STM32", "ESP32", "ATmega", "ARM", "单片机", "CPU"]
        crystal_positions = []
        mcu_positions = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if ref not in positions:
                continue
            pos = positions[ref]
            x, y = _xy(pos)
            if any(kw.lower() in desc for kw in crystal_kw):
                crystal_positions.append((ref, x, y))
            if any(kw.lower() in desc for kw in mcu_kw):
                mcu_positions.append((ref, x, y))
        if not crystal_positions or not mcu_positions:
            return violations
        max_dist = 25.0  # mm
        for cr, cx, cy in crystal_positions:
            closest = min(((cx - mx) ** 2 + (cy - my) ** 2) ** 0.5 for _, mx, my in mcu_positions)
            if closest > max_dist:
                violations.append(RuleViolation(
                    rule_name="晶振布局检查",
                    description=f"晶振 {cr} 距 MCU {closest:.0f}mm(建议≤{int(max_dist)}mm)",
                    severity=RuleSeverity.WARNING, location=cr,
                    suggestion="晶振紧靠 MCU OSC_IN/OSC_OUT 引脚，走线短而直，底部铺 GND 铜皮。晶振下方不走其他信号线。",
                    theory="晶振到 MCU 的走线每 1cm 引入约 8nH 寄生电感和 2~5pF 寄生电容→频率偏移和起振困难。皮尔斯振荡器依赖走线电容作为负载的一部分，走线过长破坏 CL 匹配。",
                ))
        return violations


    def _check_mounting_hole_keepout(self, bom_items, positions, netlist):
        """安装孔禁区：安装孔周围应有禁布区"""
        if not positions: return []
        violations = []
        hole_kw = ["HOLE", "MTG", "安装孔", "螺丝孔", "定位孔"]
        keepout_r = 3.0
        hole_refs = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')} {getattr(item, 'reference', '')}".lower()
            if not any(kw.lower() in desc for kw in hole_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            hole_refs.append(ref)
        near_holes = []
        for hole_ref in hole_refs:
            if hole_ref not in positions:
                continue
            hpos = positions[hole_ref]
            hx = hpos.get("x", 0) if isinstance(hpos, dict) else (hpos[0] if isinstance(hpos, (list, tuple)) else 0)
            hy = hpos.get("y", 0) if isinstance(hpos, dict) else (hpos[1] if isinstance(hpos, (list, tuple)) and len(hpos) > 1 else 0)
            for item in bom_items:
                ref = getattr(item, "reference", "").split(",")[0].strip()
                if ref in hole_refs or ref not in positions:
                    continue
                pos = positions[ref]
                x = pos.get("x", 0) if isinstance(pos, dict) else (pos[0] if isinstance(pos, (list, tuple)) else 0)
                y = pos.get("y", 0) if isinstance(pos, dict) else (pos[1] if isinstance(pos, (list, tuple)) and len(pos) > 1 else 0)
                dist = ((hx - x) ** 2 + (hy - y) ** 2) ** 0.5
                if dist < keepout_r:
                    near_holes.append(ref)
        if near_holes:
            violations.append(RuleViolation(
                rule_name="安装孔禁区检查",
                description=f"{len(near_holes)} 个元件距安装孔 <{int(keepout_r)}mm: {', '.join(near_holes[:5])}",
                severity=RuleSeverity.WARNING, location=", ".join(near_holes[:5]),
                suggestion=f"安装孔周围 ≥{int(keepout_r)}mm 禁止放置元件和走线。螺丝头/垫片可能压伤元件。",
                theory="螺丝安装时垫片/螺丝头直径通常比孔径大 3~5mm(如 M3 螺丝垫片≈7mm)。禁布区防止装配时机械损伤元件和焊点。IPC-2221 推荐禁布区≥孔径+2mm。",
            ))
        return violations


    def _check_temp_sensitive_placement(self, bom_items, positions, netlist):
        """温度敏感元件：温度敏感元件应远离热源"""
        violations = []
        temp_sensitive_kw = ["晶振", "crystal", "XTAL", "ADC", "基准", "reference", "REF", "传感器",
                            "电解电容", "electrolytic", "光耦", "optocoupler"]
        heat_source_kw = ["LDO", "DC-DC", "BUCK", "BOOST", "MOSFET", "功率电阻", "电源",
                         "regulator", "driver", "LED驱动"]
        temp_sensitive = []
        heat_sources = []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if any(kw.lower() in desc for kw in temp_sensitive_kw):
                temp_sensitive.append(ref)
            if any(kw.lower() in desc for kw in heat_source_kw):
                heat_sources.append(ref)
        if not temp_sensitive or not heat_sources:
            return violations
        if positions:
            warnings = 0
            min_distance = 10.0
            for tr in temp_sensitive:
                if tr not in positions: continue
                tp = positions[tr]
                tx = tp.get("x", 0) if isinstance(tp, dict) else (tp[0] if isinstance(tp, (list, tuple)) else 0)
                ty = tp.get("y", 0) if isinstance(tp, dict) else (tp[1] if isinstance(tp, (list, tuple)) and len(tp) > 1 else 0)
                for hr in heat_sources:
                    if hr not in positions: continue
                    hp = positions[hr]
                    hx = hp.get("x", 0) if isinstance(hp, dict) else (hp[0] if isinstance(hp, (list, tuple)) else 0)
                    hy = hp.get("y", 0) if isinstance(hp, dict) else (hp[1] if isinstance(hp, (list, tuple)) and len(hp) > 1 else 0)
                    dist = ((tx - hx) ** 2 + (ty - hy) ** 2) ** 0.5
                    if dist < min_distance:
                        warnings += 1
            if warnings > 2:
                violations.append(RuleViolation(
                    rule_name="温度敏感元件布局检查",
                    description=f"{warnings} 对温度敏感元件与热源间距 <{int(min_distance)}mm",
                    severity=RuleSeverity.WARNING,
                    suggestion=f"晶振/ADC/基准源/电解电容距离热源 ≥{int(min_distance)}mm。使用热仿真或红外热像仪验证。",
                    theory="晶振频率漂移 Δf/f≈α×ΔT(α≈-0.03ppm/°C²),温升 20°C→频率漂移可达 12ppm。电解电容在 85°C 以上工作时寿命指数衰减(105°C 品在 95°C 工作寿命减半)。",
                ))
        return violations


    def _check_emi_filter_proximity(self, bom_items, positions, netlist):
        """EMI 滤波器靠近入口：EMI 滤波器件应紧靠电源入口"""
        violations = []
        emi_kw = ["共模", "choke", "CMC", "EMI", "filter", "X电容", "Y电容"]
        conn_kw = ["电源", "DC-IN", "VIN", "PWR", "power", "端子", "插座", "connector", "HEADER"]
        emi_refs, conn_refs = [], []
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if any(kw.lower() in desc for kw in emi_kw):
                emi_refs.append(ref)
            if any(kw.lower() in desc for kw in conn_kw):
                conn_refs.append(ref)
        if not emi_refs or not conn_refs:
            return violations
        if positions:
            max_dist = 30.0
            far_pairs = []
            for er in emi_refs:
                if er not in positions: continue
                ep = positions[er]
                ex = ep.get("x", 0) if isinstance(ep, dict) else (ep[0] if isinstance(ep, (list, tuple)) else 0)
                ey = ep.get("y", 0) if isinstance(ep, dict) else (ep[1] if isinstance(ep, (list, tuple)) and len(ep) > 1 else 0)
                for cr in conn_refs:
                    if cr not in positions: continue
                    cp = positions[cr]
                    cx = cp.get("x", 0) if isinstance(cp, dict) else (cp[0] if isinstance(cp, (list, tuple)) else 0)
                    cy = cp.get("y", 0) if isinstance(cp, dict) else (cp[1] if isinstance(cp, (list, tuple)) and len(cp) > 1 else 0)
                    dist = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
                    if dist > max_dist:
                        far_pairs.append(f"{er}/{cr}({dist:.0f}mm)")
            if far_pairs:
                violations.append(RuleViolation(
                    rule_name="EMI 滤波器布局检查",
                    description=f"EMI 滤波器件距电源入口 >{int(max_dist)}mm: {', '.join(far_pairs[:3])}",
                    severity=RuleSeverity.WARNING,
                    suggestion=f"EMI 滤波器件紧靠电源连接器(≤{int(max_dist)}mm)。滤波前后分区敷铜,避免噪声耦合绕过滤波器。",
                    theory="EMI 滤波器的作用是将噪声电流旁路回源端。滤波器距入口越远,入口到滤波器间的走线越长→走线辐射的噪声绕过滤波器直接耦合到电源线,滤波器效果大幅降低。",
                ))
        return violations


    def _check_connector_edge_placement(self, bom_items, positions, netlist):
        """连接器边沿布局：连接器/接口应置于 PCB 边沿（按板框包围盒算真实边距）

        2026-10-09 修正：旧判据 `x>10 and y>10` 拿绝对坐标当边距，不减板框
        原点——原点偏移的板上连接器全被误判「距板边较远」。板框无真实轮廓
        (source != outline) 时无法算边距，跳过。
        """
        if not positions: return []
        pcb = self._pcb_data
        bo = (pcb.board_outline or {}) if pcb else {}
        if bo.get("source") != "outline":
            return []
        violations = []
        conn_kw = ["USB", "RJ45", "HDMI", "DB9", "排针", "端子", "CONNECTOR", "HEADER", "JACK",
                   "DC", "电源插座", "SD卡", "TF卡", "SIM卡", "FPC", "FFC"]
        max_board_edge = 10.0
        minx, miny = bo["min_x_mm"], bo["min_y_mm"]
        maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
        for item in bom_items:
            desc = f"{getattr(item, 'part_number', '')} {getattr(item, 'description', '')}".lower()
            if not any(kw.lower() in desc for kw in conn_kw):
                continue
            ref = getattr(item, "reference", "").split(",")[0].strip()
            if ref not in positions:
                continue
            x, y = _xy(positions[ref])
            clearance = min(x - minx, maxx - x, y - miny, maxy - y)
            if clearance > max_board_edge:
                violations.append(RuleViolation(
                    rule_name="连接器边沿布局检查",
                    description=f"连接器 {ref} 距最近板边 {clearance:.0f}mm（>{int(max_board_edge)}mm），可能影响插拔操作",
                    severity=RuleSeverity.INFO, location=ref,
                    suggestion="连接器/接口紧贴 PCB 边沿，开口朝外。机壳开孔位置与连接器对准，预留插头空间(如 USB 插头长度 ≈15mm)。",
                    theory="连接器置于板中心→机壳内部需延长开孔通道,增加机械设计难度且插拔力会使 PCB 弯曲。板边布局插拔力直接由机壳/固定柱承受。",
                ))
        return violations


    def _check_component_spacing(self, bom_items, positions, netlist):
        """元件间距：按导入顺序抽样比较相邻元件对（非空间最近邻全量检索）"""
        if not positions: return []
        min_spacing = 1.0
        close_pairs = 0
        pos_items = list(positions.items())
        for i in range(len(pos_items)):
            for j in range(i + 1, min(i + 5, len(pos_items))):
                p1 = pos_items[i][1]
                p2 = pos_items[j][1]
                x1, y1 = _xy(p1)
                x2, y2 = _xy(p2)
                if ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 < min_spacing:
                    close_pairs += 1
        if close_pairs > 3:
            return [RuleViolation(
                rule_name="元件间距检查",
                description=(f"抽样比较发现约 {close_pairs} 对元件间距 <{min_spacing}mm"
                             f"（按导入顺序取相邻对，非空间最近邻），可能影响 SMT 贴片和返修"),
                severity=RuleSeverity.INFO,
                suggestion="SMT 元件间≥0.5mm(0603), ≥0.8mm(0805)。高元件间≥1.5mm。连接器周围预留插拔空间。",
                theory="元件间距过小→SMT 钢网印刷桥连、回流焊阴影效应、烙铁无法伸入返修。IPC-7351 为每种封装定义了标准焊盘和间距。",
            )]
        return []


    def _check_fiducial_mark(self, bom_items, positions, netlist):
        """Mark点检查：批量生产PCB应有光学定位Mark点

        2026-10-09 噪声清扫：原实现 len(positions)>10 即报「未确认是否有 Mark」
        （78/78 板全响）。改为在 component_positions 的封装名/值/料号里找
        FIDUCIAL / MARK-POINT 类器件（金样 1/78 板有，footprint_name=
        'MARK-POINT'）：找到 → 静默；找不到 → 文案改为「未检测到」，可证伪。
        位号不参与匹配（M4 也可能是安装孔）。
        """
        if not positions or len(positions) <= 10:
            return []
        fiducial_kw = ("fiducial", "mark", "基准", "定位")
        for pos in positions.values():
            if not isinstance(pos, dict):
                continue
            blob = " ".join(
                str(pos.get(k) or "") for k in
                ("footprint_name", "footprint", "device", "value", "part_number")
            ).lower()
            if any(kw in blob for kw in fiducial_kw):
                return []
        return [RuleViolation(
            rule_name="光学定位点检查",
            description="未检测到光学定位(Mark)点器件，SMT 批量贴片前需确认",
            severity=RuleSeverity.INFO,
            suggestion="PCB 对角放置≥2个全局 Mark 点(Φ1.0mm 铜箔+Φ3.0mm 阻焊开窗)。细间距IC(QFP/BGA)局部加Mark点。",
            theory="SMT 贴片机通过识别 Mark 点校正 PCB 位置偏差。全局 Mark 用于整板定位，局部 Mark 用于精细间距元件定位。无 Mark 点→贴片精度不足→立碑/偏移。",
        )]
