"""走线/过孔/几何类规则 —— 从 checker.py 机械迁出（P1-6 阶段B，纯移动）。"""

import logging
import math
import re
from collections import Counter
from ..constants import PCB
from ..pcb.geometry import trace_corners

from .base import (
    RuleSeverity,
    RuleViolation,
    _COMPONENT_MODEL_PATH,
    _COMPONENT_VOCAB_PATH,
    _DCDC_DESC_KW,
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
    group_violations_by_component,
    rule_kind,
)

logger = logging.getLogger(__name__)

class GeometryRulesMixin:
    """方法集由 facade DesignRuleChecker 组合；此处无状态、无 __init__。"""


    # ═══ PCB-data rules ═══

    def _check_signal_traces(self, bom_items, positions, netlist):
        """信号线宽度：按「本板实际线宽」判定，而不是一条固定下限。

        1) 绝对硬下限：细于 SIGNAL_TRACE_ABS_MIN_WIDTH_MM（≈4mil，一般厂最小）→ 可能做不出来
        2) 相对异常：细于本板信号线宽众数的 SIGNAL_TRACE_REL_MIN_RATIO 倍 →
           明显偏离本板设计意图，多半误用了细线；整板统一用细线的设计不会误报
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        # 2026-09-24 抽查修正：① 绝对下限按层数区分（≥4 层常规工艺能力 0.09mm，
        # 原实现对所有板一律取 0.1mm）；② 相对判据只对「同一网络内混用多种线宽」
        # 生效——整条网络统一选细则多半是有意的设计（如阻抗控制的 3.5mil 网络），
        # 抽样里 5/5 误报都是这一类。
        layer_count = len({t.layer for t in pcb.traces if t.layer}) or len(
            getattr(pcb, "layers", None) or []
        )
        abs_min = 0.09 if layer_count >= 4 else PCB.SIGNAL_TRACE_ABS_MIN_WIDTH_MM
        ratio = PCB.SIGNAL_TRACE_REL_MIN_RATIO
        sig_traces = [
            t for t in pcb.traces
            if t.net_name and t.width_mm > 0
            and not any(kw.upper() in t.net_name.upper() for kw in PCB.POWER_NET_KEYWORDS)
        ]
        net_min: dict[str, float] = {}
        for t in sig_traces:
            prev = net_min.get(t.net_name, float("inf"))
            if t.width_mm < prev:
                net_min[t.net_name] = t.width_mm
        if not net_min:
            return []
        # 本板信号线宽众数（按折线条数）—— 代表设计者实际选用的工艺线宽
        dom_w = Counter(t.width_mm for t in sig_traces).most_common(1)[0][0]
        rel_floor = dom_w * ratio
        widths_by_net: dict[str, set] = {}
        for t in sig_traces:
            widths_by_net.setdefault(t.net_name, set()).add(round(t.width_mm, 4))
        for name, w in net_min.items():
            if w >= abs_min and w >= rel_floor:
                continue
            if w < abs_min:
                why = f"细于工艺下限 {abs_min}mm"
            else:
                if len(widths_by_net.get(name, ())) < 2:
                    continue   # 整网统一细线 = 设计意图，不判误设
                why = (f"仅本板主流线宽 {dom_w:.3f}mm 的 {ratio:.0%}"
                       f"（{rel_floor:.3f}mm），且该网络内混用了多种线宽")
            violations.append(RuleViolation(
                rule_name="信号线宽度检查",
                description=f"网络 [{name}] 最小线宽 {w:.3f}mm，{why}",
                severity=RuleSeverity.WARNING, location=name,
                suggestion=(f"确认该网络线宽是否有意为之：工艺下限约 {abs_min}mm(4mil)，"
                            f"本板其余走线多用 {dom_w:.3f}mm。高速信号还需确认阻抗匹配。"),
                theory="走线宽度由 PCB 工艺能力和信号完整性共同决定。一般厂最小 4mil(0.1mm)。"
                       "同一块板通常有意选用一套线宽，明显偏离本板主流的网络更可能是误设，"
                       "因此判据取「绝对下限」与「本板主流线宽」两者较宽者。"))
        return violations


    def _check_power_traces(self, bom_items, positions, netlist):
        """电源线载流 — 使用 IPC-2221 真实计算，结合电流估算"""
        from src.pcb.calculator import ipc2221_current_capacity, ipc2221_trace_width

        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        pw_traces = [t for t in pcb.traces
                     if t.net_name and t.width_mm > 0 and any(
                     kw.upper() in t.net_name.upper()
                     for kw in PCB.POWER_NET_KEYWORDS)]
        if not pw_traces: return violations

        # 从 BOM 估算电源电流
        est_current_a = self._estimate_power_current(bom_items)
        tr, cu = PCB.IPC_TEMP_RISE, PCB.IPC_COPPER_OZ

        # 每条网络取**最窄的那条走线**，外层/内层按它自己的层判定。
        # 2026-09-18 抽查修正：原实现用「整板只要有一条 inner 层电源走线就为 True」
        # 的板级布尔，把 Top/Bottom 上的电源线也按内层系数算，容量直接腰斩
        # （k 0.024 vs 0.048），在 23/76 块多层板上产出 ERROR 级误报。
        narrow: dict[str, tuple[float, str]] = {}
        for t in pw_traces:
            if not t.net_name:
                continue
            layer = str(getattr(t, "layer", "") or "")
            prev = narrow.get(t.net_name)
            if prev is None or t.width_mm < prev[0]:
                narrow[t.net_name] = (t.width_mm, layer)

        for name, (mw, layer) in narrow.items():
            # 用估算电流或按网络名定制
            I = self._estimate_net_current(name, est_current_a)
            is_inner = _is_inner_layer(pcb, layer)
            capacity = ipc2221_current_capacity(mw, cu, tr, is_inner)
            req_w = ipc2221_trace_width(I, cu, tr, is_inner)

            if capacity < I:
                violations.append(RuleViolation(
                    rule_name="电源线载流检查",
                    description=(
                        f"电源网络 [{name}] {layer or '未知层'}"
                        f"（{'内层' if is_inner else '外层'}）: "
                        f"线宽 {mw:.3f}mm 载流 {capacity:.2f}A "
                        f"< 需求 {I:.2f}A，需宽 ≥{req_w:.3f}mm"
                    ),
                    severity=RuleSeverity.ERROR,
                    location=name,
                    suggestion=(
                        f"当前 {mw:.3f}mm (1oz) 仅承载 {capacity:.2f}A。"
                        f"加宽至 ≥{req_w:.3f}mm 或改用 {cu*2}oz 铜厚。"
                        f"1oz → 2oz 载流提升约 {ipc2221_current_capacity(mw,cu*2,tr,is_inner)/capacity:.1f}×"
                    ),
                    theory="IPC-2221 §6.2: I=k·ΔT^0.44·A^0.725。基于铜箔截面积与允许温升的物理模型，"
                           "是 PCB 行业标准载流公式。",
                ))
        return violations


    def _check_trace_acute_angles(self, bom_items, positions, netlist):
        """走线拐角：锐角（酸陷阱）与直角（SI 角部阻抗突变）。

        必须先做端点串联：.epru/.epro2 同一 (网络, 层) 的 LINE 线段不按路径顺序
        记录、且可能重复，直接取相邻两段夹角会得到一堆假的 0°/180°
        （见 src/pcb/geometry.py）。串联后只在度数为 2 的节点取角，T/X 形节点
        （焊盘、过孔、分支）的角度不代表走线拐角。每侧腿短于
        TRACE_CORNER_MIN_LEG_MM 的退化拐角跳过。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces:
            return []
        acute_max = PCB.TRACE_ACUTE_ANGLE_MAX_DEG
        right_min = PCB.TRACE_RIGHT_ANGLE_MIN_DEG
        right_max = PCB.TRACE_RIGHT_ANGLE_MAX_DEG
        # 2026-09-24 抽查修正：
        # ① 直角只对高速/时钟/差分网络报——规则自述「普通低速线可接受」，对所有网络
        #    一律 INFO 的结果是 75/76 块板都响；
        # ② 锐角增加「焊盘入口几何」二次过滤——抽样里 2/3 的锐角其实是元件焊盘/过孔
        #    入口的短拐角（腿长 0.2mm、距元件 0.4mm），不是布线拐角。
        diff_members: set = set()
        for _label, nets, _src in self._diff_groups_src(pcb):
            diff_members.update(str(n).upper() for n in nets)
        anchor_grid: dict = {}
        for v in (pcb.vias or []):
            # 2026-10-06 修复：PCBVia 只有 position 元组、没有 x/y 属性，
            # 原来的 getattr(v, "x", None) 永远拿不到坐标 → 过孔锚点从未生效，
            # 顶点落在过孔上的焊盘入口拐角不会被过滤。优先 position，兼容 x/y。
            pos = getattr(v, "position", None)
            if pos is not None and len(tuple(pos)) >= 2:
                ax, ay = float(pos[0]), float(pos[1])
            else:
                vx, vy = getattr(v, "x", None), getattr(v, "y", None)
                if vx is None or vy is None:
                    continue
                ax, ay = float(vx), float(vy)
            anchor_grid.setdefault((math.floor(ax), math.floor(ay)), []).append((ax, ay))
        for pos in (getattr(pcb, "component_positions", None) or {}).values():
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                ax, ay = float(pos["x"]), float(pos["y"])
                anchor_grid.setdefault((math.floor(ax), math.floor(ay)), []).append((ax, ay))
        clear_r = PCB.TRACE_CORNER_PAD_CLEAR_MM
        pad_leg = PCB.TRACE_CORNER_PAD_LEG_MM

        def _is_pad_entry(c) -> bool:
            """两腿都短、且顶点贴着焊盘/过孔 → 焊盘入口几何，不是走线拐角。"""
            if max(c.leg_in_mm, c.leg_out_mm) >= pad_leg:
                return False
            x, y = c.vertex[0], c.vertex[1]
            for ci in range(math.floor(x - clear_r), math.floor(x + clear_r) + 1):
                for cj in range(math.floor(y - clear_r), math.floor(y + clear_r) + 1):
                    for ax, ay in anchor_grid.get((ci, cj), ()):
                        if math.hypot(x - ax, y - ay) < clear_r:
                            return True
            return False

        acute_violations = []
        right_violations = []
        for t in pcb.traces:
            if not t.net_name:
                continue
            corners = trace_corners(t.segments, min_leg_mm=PCB.TRACE_CORNER_MIN_LEG_MM)
            if not corners:
                continue
            acute = [c for c in corners
                     if c.angle_deg < acute_max and not _is_pad_entry(c)]
            right = [c for c in corners if right_min <= c.angle_deg <= right_max]
            if right and _net_class(t.net_name, diff_members) not in ("diff", "high"):
                right = []      # 低速网络的直角可接受，不再逐块板提示
            if acute:
                worst = min(acute, key=lambda c: c.angle_deg)
                loc = f"({worst.vertex[0]:.2f}, {worst.vertex[1]:.2f})mm"
                acute_violations.append(RuleViolation(
                    rule_name="走线锐角检查",
                    description=(
                        f"网络 [{t.net_name}] {t.layer} 有 {len(acute)} 处锐角，"
                        f"最尖 {worst.angle_deg:.1f}° @{loc}"
                    ),
                    severity=RuleSeverity.WARNING,
                    location=t.net_name,
                    suggestion="改用 45° 折线或圆弧过渡；锐角处补泪滴/加宽拐角",
                    theory=(
                        "锐角(<90°)在蚀刻时形成「酸陷阱」(acid trap)：蚀刻液易残留、"
                        "过度蚀刻，导致开路/短路与长期可靠性问题。另外拐角较直线段"
                        "等效变宽(√2 倍)→局部特征阻抗下降、信号反射。IPC 推荐 45°/圆弧。"
                    ),
                ))
            if right:
                right_violations.append(RuleViolation(
                    rule_name="走线直角检查",
                    description=(
                        f"网络 [{t.net_name}] {t.layer} 有 {len(right)} 处直角走线"
                    ),
                    severity=RuleSeverity.INFO,
                    location=t.net_name,
                    suggestion="高速/时钟线用 45° 或圆弧代替直角；普通低速线可接受",
                    theory=(
                        "直角拐角处线宽等效增大(√2 倍)→局部电容上升、阻抗不连续，"
                        "在 >50MHz 或长走线上会引起反射与 EMI 恶化。"
                    ),
                ))
        # 锐角(WARNING) 排在直角(INFO) 前，报告与实验口径都稳定
        return acute_violations + right_violations


    def _check_via_density(self, bom_items, positions, netlist):
        """过孔密度：只对高速信号网络判定（电源/地缝合孔成百上千属正常）"""
        pcb = self._pcb_data
        if not pcb or not pcb.vias: return []
        violations = []
        limit = PCB.VIA_DENSITY_MAX_PER_NET
        kws = PCB.VIA_DENSITY_NET_KEYWORDS
        via_per_net: dict[str, int] = {}
        for v in (pcb.vias or []):
            net = getattr(v, "net_name", "") or getattr(v, "net", "")
            if not net:
                continue
            if not any(kw.upper() in net.upper() for kw in kws):
                continue
            via_per_net[net] = via_per_net.get(net, 0) + 1
        for net, count in via_per_net.items():
            if count >= limit:
                violations.append(RuleViolation(
                    rule_name="过孔密度检查",
                    description=f"高速网络 [{net}] 过孔数量({count}) ≥ {limit}",
                    severity=RuleSeverity.INFO, location=net,
                    suggestion="每过孔引入 ≈0.5nH 寄生电感，高速信号路径建议 ≤2 过孔",
                    theory="过孔寄生电感≈0.5~1nH，寄生电容≈0.3~0.5pF。>50MHz 时多个过孔串联致阻抗不连续和 EMI 恶化。IPC-2221 建议关键信号过孔≤2。"))
        return violations


    # ── 差分对辅助 ──

    @staticmethod
    def _diff_groups_src(pcb) -> list:
        """差分/等长分组 → [(组名, [网络, ...], 来源), ...]，来源 = 'engine' | 'guess'。

        用工程 NET 规则里设计者显式定义的 differential / equal_length 组
        （比名字猜测可靠）；没有元数据时退化为 P/N、+/- 后缀两两配对。
        2026-09-24 抽查修正：两种来源必须可区分——靠后缀猜出来的
        D1_P/D1-、IN_D+/IN_D- 根本不是差分信号，不能再按差分对判 ERROR/WARNING。
        """
        groups: dict[str, list] = {}
        for entry in (getattr(pcb, "differential_pairs", None) or []):
            net = entry.get("net") or ""
            g = entry.get("differential") or entry.get("equal_length_group")
            if net and g:
                groups.setdefault(str(g), []).append(net)
        out = [(label, sorted(set(nets)), "engine") for label, nets in groups.items()]
        out = [x for x in out if len(x[1]) >= 2]
        if out:
            return out

        pol = {"P": "P", "N": "N", "+": "P", "-": "N"}
        by_base: dict[str, dict] = {}
        for t in pcb.traces:
            name = t.net_name or ""
            for suf in ("_P", "_N", "_p", "_n", "+", "-"):
                if len(name) > len(suf) and name.endswith(suf):
                    by_base.setdefault(name[: -len(suf)], {})[pol[suf[-1].upper()]] = name
                    break
        return [
            (base, [members["P"], members["N"]], "guess")
            for base, members in by_base.items()
            if "P" in members and "N" in members
        ]


    @staticmethod
    def _pair_min_gap(pcb, pair, cap: int = 20000):
        """差分对两条网络在同层走线之间的最小线段距离 (mm)；无同层走线返回 None。"""
        first = {}
        for t in pcb.traces:
            if t.net_name == pair[0]:
                first.setdefault(t.layer, []).extend(
                    (s[0], s[1], s[2], s[3]) for s in (t.segments or [])
                )
        best = None
        n = 0
        for t in pcb.traces:
            if t.net_name != pair[1]:
                continue
            other = first.get(t.layer)
            if not other:
                continue
            for s in (t.segments or []):
                a, b = (s[0], s[1]), (s[2], s[3])
                for s0 in other:
                    n += 1
                    if n > cap:
                        return best
                    d = _seg_seg_dist(a, b, (s0[0], s0[1]), (s0[2], s0[3]))
                    if best is None or d < best:
                        best = d
        return best


    def _check_diff_pair_spacing(self, bom_items, positions, netlist):
        """差分对间距：成对走线应紧耦合（对内最小间距不应远大于线宽）。

        2026-09-24 抽查修正：① 只判工程 NET 规则里设计者显式定义的差分组——靠
        P/N、+/- 后缀猜出来的配对（D1_P/D1-、IN_D+/IN_D-）不是差分信号，一律跳过；
        ② 门限取「明显松耦合」（4W）：抽样判读里 3.0~4.5W 属阈值边界，
        按 3W 一刀切会把正常设计报成缺陷。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        limit = max(PCB.DIFF_PAIR_MAX_GAP_FACTOR, 4.0)
        for label, nets, source in self._diff_groups_src(pcb):
            if source != "engine":      # 名字猜测的配对不作为差分对判间距
                continue
            if len(nets) != 2:   # 等长总线（≥3 条）不判间距
                continue
            gap = self._pair_min_gap(pcb, (nets[0], nets[1]))
            if gap is None:
                continue
            widths = [
                t.width_mm for t in pcb.traces
                if t.net_name in nets and t.width_mm > 0
            ]
            avg_w = sum(widths) / len(widths) if widths else 0.0
            if avg_w <= 0:
                continue
            ratio = gap / avg_w
            if ratio > limit:
                violations.append(RuleViolation(
                    rule_name="差分对间距检查",
                    description=(f"差分对 [{nets[0]} / {nets[1]}] 最小间距 {gap:.3f}mm "
                                 f"≈ {ratio:.1f}W > {limit:.0f}W，耦合过松"),
                    severity=RuleSeverity.INFO, location=nets[0],
                    suggestion=(f"差分对应紧耦合：当前间距 {ratio:.1f}W，建议 ≤{limit:.0f}W"
                                f"（≈2×线宽）。USB=90Ω, LVDS=100Ω。"),
                    theory="差分阻抗 Zdiff=2×Zodd，取决于 W/S/H/εr。USB2.0 要求 90Ω±15%，LVDS 要求 100Ω±10%。线距过大→Zdiff↑→CMRR↓；线距过小→串扰↑。"))
        return violations


    def _check_diff_pair_length(self, bom_items, positions, netlist):
        """差分对等长：同组两条走线长度差应 < DIFF_PAIR_MAX_SKEW_MM"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        tol = PCB.DIFF_PAIR_MAX_SKEW_MM
        lengths: dict[str, float] = {}
        for t in pcb.traces:
            name = t.net_name or ""
            if not name:
                continue
            lengths[name] = lengths.get(name, 0.0) + sum(
                math.hypot(s[2] - s[0], s[3] - s[1]) for s in (t.segments or [])
            )
        for label, nets, source in self._diff_groups_src(pcb):
            lens = [lengths.get(n, 0.0) for n in nets]
            lens = [x for x in lens if x > 0]
            if len(lens) < 2:
                continue
            diff_mm = round(max(lens) - min(lens), 4)
            avg_len = sum(lens) / len(lens)
            # 2026-09-24 抽查修正：0.5mm 一刀切对 USB2.0（位周期 2083ps，3.25mm≈22ps）、
            # 音频功放、直流输入 ± 都过严。改用量则：极差 ≥2mm 或 ≥10% 走线长度才算真失配；
            # 名字猜测出来的配对降级为 INFO，不再按差分对判 WARNING。
            if not (diff_mm >= 2.0 or diff_mm >= 0.10 * avg_len):
                continue
            violations.append(RuleViolation(
                rule_name="差分对等长检查",
                description=(f"差分/等长组 [{label}] 走线长度差 {diff_mm}mm "
                             f"(判据门限 {tol}mm，组内平均长 {avg_len:.1f}mm): "
                             + ", ".join(nets[:4])),
                severity=(RuleSeverity.WARNING if source == "engine" else RuleSeverity.INFO),
                location=label,
                    suggestion=f"差分对走线长度差应 <{tol}mm。用蛇形走线补偿短的一侧。蛇形幅度≥3W,间距≥2S。",
                    theory="差分信号依赖两条线同时到达接收端来维持共模抑制。长度不匹配→到达时间差→差模分量→共模噪声↑、眼图闭合。FR4 中约 6.7ps/mm。",
                ))
        return violations


    def _check_clock_guard_trace(self, bom_items, positions, netlist):
        """时钟信号包地：高频时钟应有包地走线"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        clk_kw = ["CLK", "CLOCK", "OSC", "XTAL", "MCLK", "SCLK", "HCLK"]
        seen: set = set()
        for t in pcb.traces:
            name = (t.net_name or "").upper()
            if not any(kw.upper() in name for kw in clk_kw):
                continue
            # traces 按 (网络, 层) 聚合，同一时钟网络跨层会出现多次，按网络去重
            if t.net_name in seen:
                continue
            seen.add(t.net_name)
            violations.append(RuleViolation(
                rule_name="时钟信号包地检查",
                description=f"时钟网络 [{t.net_name}] 建议添加包地走线",
                severity=RuleSeverity.INFO, location=t.net_name,
                suggestion="时钟走线两侧加接地护线(GND guard trace)，每隔 λ/20 打过孔接地。护线距时钟线 ≥3W。",
                theory="时钟是 PCB 上最强 EMI 源—高幅值、固定频率、陡峭边沿(tr<1ns 含数百 MHz 谐波)。包地走线将电场约束在信号-护线间,降低对邻线的串扰。接地过孔间距≤λ/20(如 100MHz→FR4 λ≈1.5m→λ/20≈7.5mm)。",
            ))
        return violations


    def _check_crosstalk_spacing(self, bom_items, positions, netlist):
        """3W 串扰间距：只看「平行且间距 <3W」的高速/时钟/差分线对。

        只比较真实线段-线段最短距离；交叉点/垂直走线两线必然接近但不构成串扰，
        因此额外要求平行重叠长度 ≥ CROSSTALK_MIN_PARALLEL_MM 才算风险。
        2026-09-24 抽查修正：加网络类别门控——电源/地线对与按键/蜂鸣器/32kHz/GPIO
        等低速网络不再套 3W 准则（抽样里报出的线对 5/5 都是这类）。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        diff_members: set = set()
        for _label, nets, _src in self._diff_groups_src(pcb):
            diff_members.update(str(n).upper() for n in nets)
        factor = PCB.CROSSTALK_SPACING_FACTOR
        min_par = PCB.CROSSTALK_MIN_PARALLEL_MM
        by_layer: dict[str, list] = {}
        for t in pcb.traces:
            if t.segments:
                by_layer.setdefault(t.layer, []).append(t)

        for layer, traces in by_layer.items():
            if len(traces) < 2:
                continue
            max_w = max((t.width_mm or 0.0) for t in traces) or 0.2
            radius = factor * max_w
            cell = max(radius, 0.3)
            grid: dict = {}
            segs = []
            for t in traces:
                w = t.width_mm or 0.0
                # 网络类别在这里只算一次（内层循环里逐对重算会把 3W 判定拖慢一个量级）
                cls = ("power" if _is_power_or_ground_net(t.net_name)
                       else _net_class(t.net_name, diff_members))
                for s in t.segments:
                    idx = len(segs)
                    a, b = (s[0], s[1]), (s[2], s[3])
                    x0, x1 = (a[0], b[0]) if a[0] <= b[0] else (b[0], a[0])
                    y0, y1 = (a[1], b[1]) if a[1] <= b[1] else (b[1], a[1])
                    segs.append((t.net_name, w, a, b, x0, x1, y0, y1, cls))
                    for ci in range(int((x0 - radius) // cell), int((x1 + radius) // cell) + 1):
                        for cj in range(int((y0 - radius) // cell), int((y1 + radius) // cell) + 1):
                            grid.setdefault((ci, cj), []).append(idx)
            contested: dict = {}
            for i, (net, w, a, b, x0, x1, y0, y1, cls) in enumerate(segs):
                seen = set()
                for ci in range(int((x0 - radius) // cell), int((x1 + radius) // cell) + 1):
                    for cj in range(int((y0 - radius) // cell), int((y1 + radius) // cell) + 1):
                        for j in grid.get((ci, cj), ()):
                            if j <= i or j in seen:
                                continue
                            seen.add(j)
                            n2, w2, c, d, cx0, cx1, cy0, cy1, cls2 = segs[j]
                            if n2 == net:
                                continue
                            # 电源/地线对、低速网络对不构成 3W 串扰风险：
                            # 至少要有一侧是高速/时钟/差分网络才继续算几何
                            if not (cls in ("diff", "high") or cls2 in ("diff", "high")):
                                continue
                            avg_w = (w + w2) * 0.5
                            if avg_w <= 0:
                                continue
                            thr = factor * avg_w
                            # O(1) AABB 剪枝：多数候选在此被拒，避免昂贵距离计算
                            if (cx0 - x1 > thr or x0 - cx1 > thr
                                    or cy0 - y1 > thr or y0 - cy1 > thr):
                                continue
                            # 先判平行（便宜），再算线段距离
                            ov = _parallel_overlap_len(a, b, c, d)
                            if ov <= 0:
                                continue
                            if _seg_seg_dist(a, b, c, d) >= thr:
                                continue
                            key = (net, n2) if net <= n2 else (n2, net)
                            contested[key] = contested.get(key, 0.0) + ov
            hits = {k: v for k, v in contested.items() if v >= min_par}
            if not hits:
                continue
            worst = max(hits.items(), key=lambda kv: kv[1])
            violations.append(RuleViolation(
                rule_name="3W 串扰间距检查",
                description=(f"{layer} 层 {len(hits)} 对走线平行间距 <{factor:.0f}W 且重叠 "
                             f"≥{min_par}mm；最严重 [{worst[0][0]}/{worst[0][1]}] {worst[1]:.1f}mm"),
                severity=RuleSeverity.WARNING, location=layer,
                suggestion=(f"平行走线间距 ≥{factor:.0f}W(W=线宽)，高速信号 ≥5W。增大间距或加接地隔离；"
                            "平行长度越短越安全。"),
                theory="微带线串扰在间距=3W 时近端串扰(NEXT)≈1~3%。间距减半→NEXT↑6~10dB。串扰强度随平行长度增加，交叉/垂直走线不构成串扰。3W 是经验准则。",
            ))
        return violations


    def _check_loop_area(self, bom_items, positions, netlist):
        """环路面积：高速信号应最小化电流环路面积"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        high_speed_kw = ["CLK", "PWM", "SW", "SENSE", "FB", "DRV", "GATE", "DRIVE"]
        for net_name, net in (pcb.nets or {}).items():
            name_upper = net_name.upper()
            if any(kw.upper() in name_upper for kw in high_speed_kw):
                length = getattr(net, "total_length_mm", 0)
                if length > 50:  # >50mm 长的高速走线
                    violations.append(RuleViolation(
                        rule_name="环路面积检查",
                        description=f"高速网络 [{net_name}] 走线长度 {length:.0f}mm，环路面积可能偏大",
                        severity=RuleSeverity.INFO, location=net_name,
                        suggestion="高速信号紧邻参考平面走线，信号/回流路径构成的环路面积最小化。多层板保证关键信号邻层为完整 GND 平面。",
                        theory="EMI 辐射强度 ∝ 环路面积 × 频率² × 电流。相邻层的信号-回流间距 = 介质厚度(4 层板 ≈0.1~0.2mm),环路面积极小。双层板缺连续参考平面,需手动布置回流路径。",
                    ))
        return violations


    def _check_copper_pour_connectivity(self, bom_items, positions, netlist):
        """铜皮连接：大面积铜皮应避免孤岛"""
        pcb = self._pcb_data
        if not pcb: return []
        violations = []
        pours = getattr(pcb, "copper_pours", None) or []
        if not pours:
            violations.append(RuleViolation(
                rule_name="铜皮连接检查",
                description="PCB 文件未包含铜皮数据，请确认覆铜无孤岛",
                severity=RuleSeverity.INFO,
                suggestion="覆铜后执行 DRC 检查孤岛铜皮(Dead Copper/Islands)。孤岛铜皮应删除或添加过孔接地。",
                theory="孤岛铜皮既不接地也不接任何网络，相当于悬浮的天线→接收/辐射 EMI。GHz 频段时长度=λ/4 即可成为有效天线。删除或接地均可解决。",
            ))
            return violations
        return violations


    def _check_testpoint_coverage(self, bom_items, positions, netlist):
        """测试点覆盖：关键网络应预留测试点"""
        pcb = self._pcb_data
        if not pcb: return []
        violations = []
        key_net_kw = ["VCC", "VDD", "3V3", "5V", "RST", "BOOT", "SWD", "SWCLK", "SWDIO"]
        nets_without_tp = []
        for net_name in (pcb.nets or {}):
            name_upper = net_name.upper()
            if any(kw.upper() in name_upper for kw in key_net_kw):
                nets_without_tp.append(net_name)
        if nets_without_tp:
            violations.append(RuleViolation(
                rule_name="测试点覆盖检查",
                description=f"{len(nets_without_tp)} 个关键网络缺少测试点: {', '.join(nets_without_tp[:5])}",
                severity=RuleSeverity.INFO,
                suggestion="电源轨、复位、调试接口、关键信号预留 φ1.0mm 测试焊盘(TP)。间距≥2.54mm 便于探针/ICT。",
                theory="无测试点→调试时需手工飞线,成品批量测试用 ICT(在线测试)/飞针测试需夹具兼容的测试点布局。IPC-2221 建议测试点直径≥0.9mm,间距≥2.5mm。",
            ))
        return violations


    def _check_silkscreen_readability(self, bom_items, positions, netlist):
        """丝印可读性：丝印应与焊盘/过孔有足够间距"""
        pcb = self._pcb_data
        if not pcb: return []
        violations = []
        # 丝印数据通常不在轻量解析中，给出通用建议
        comp_count = len(pcb.component_positions or {})
        if comp_count > 10:
            violations.append(RuleViolation(
                rule_name="丝印可读性检查",
                description=f"PCB 包含 {comp_count} 个元件，建议检查丝印可读性",
                severity=RuleSeverity.INFO,
                suggestion="丝印方向统一(左→右或下→上)，不与焊盘/过孔重叠，字符高度≥1.0mm。位号与元件一一对应。",
                theory="丝印是PCB装配和维修的关键信息载体。字符过小或重叠→人工焊接误插率↑。IPC-A-600 规定丝印应与焊盘间距≥0.2mm,避免字符在阻焊开窗处脱落。",
            ))
        return violations


    def _check_silkscreen_pad_clearance(self, bom_items, positions, netlist):
        """丝印与焊盘间距：丝印文字不应覆盖焊盘"""
        pcb = self._pcb_data
        if not pcb or not pcb.component_positions:
            return []
        comp_count = len(pcb.component_positions)
        if comp_count > 5:
            return [RuleViolation(
                rule_name="丝印焊盘间距检查",
                description=f"PCB 含 {comp_count} 个元件，丝印与焊盘间距需确认",
                severity=RuleSeverity.INFO,
                suggestion="丝印距焊盘≥0.2mm(IPC-A-600)。位号丝印勿覆盖焊盘或过孔。字符高度≥1.0mm，方向统一。",
                theory="丝印在阻焊开窗处附着力差→脱落不清。焊盘上丝印影响可焊性且字符在回流焊后不可读。IPC-A-600 Acceptable Class 2 标准。",
            )]
        return []


    def _check_trace_edge_clearance(self, bom_items, positions, netlist):
        """走线到板边：走线距板框应有安全间距

        用板框包围盒算真实边距。板框退回「铜包围盒」(source=copper) 时边距恒为 0，
        没有判定意义，直接跳过。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        bo = pcb.board_outline or {}
        if bo.get("source") != "outline":
            return []
        min_clearance = PCB.TRACE_EDGE_CLEARANCE_MIN_MM
        minx, miny = bo["min_x_mm"], bo["min_y_mm"]
        maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
        near = []
        for t in pcb.traces:
            pts = []
            for seg in (t.segments or []):
                if len(seg) >= 4:
                    pts.append((seg[0], seg[1]))
                    pts.append((seg[2], seg[3]))
            if not pts:
                continue
            clearance = min(
                min(px - minx, maxx - px, py - miny, maxy - py) for px, py in pts
            )
            if clearance < min_clearance:
                near.append((t.net_name, clearance))
        if not near:
            return []
        worst = min(c for _, c in near)
        names = ", ".join(sorted({n for n, _ in near if n})[:5])
        return [RuleViolation(
            rule_name="走线板边间距检查",
            description=f"{len(near)} 条走线距板框 <{min_clearance}mm（最小 {worst:.3f}mm）: {names}",
            severity=RuleSeverity.WARNING,
            location=", ".join(sorted({n for n, _ in near if n})[:3]),
            suggestion=f"走线/铜皮距板边≥{min_clearance}mm(V-cut≥0.8mm)。板边走线在铣边时易被切断或暴露铜。",
            theory="PCB 铣边公差通常±0.15mm，V-cut 深度控制公差±0.1mm。板边间距不足→铣刀损伤走线致开路或微短。JLC 铜到边最小 0.2mm / 推荐 0.3mm。",
        )]



    def _check_stub_length(self, bom_items, positions, netlist):
        """短桩线(stub)检查：高速信号应避免长 stubs。

        2026-09-24 抽查修正：原判据「网络名含 CLK/USB/... 且存在过孔」就报
        「可能存在 stub 效应」，全程没有长度或分支测量——二层板（只有 Top/Bottom，
        过孔仅用于换层）根本不存在 stub，抽样 5/5 全是这类误报。现在要求：
        ① 板子 ≥4 层（多层板才可能由内层走线形成分支）；
        ② 同一网络有 ≥2 个过孔（才可能构成「过孔→走线→过孔」的分支结构）。
        无拓扑信息时量不出 stub 长度，故本规则仍属提示类（INFO）。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.vias: return []
        layers = [str(x) for x in (getattr(pcb, "layers", None) or [])]
        layer_count = len(set(layers)) if layers else len({t.layer for t in pcb.traces if t.layer})
        if layer_count < 4:
            return []
        high_speed_kw = {"CLK", "SCK", "SDIO", "SDRAM", "USB", "HDMI", "PCIE"}
        via_count: dict[str, int] = {}
        for v in pcb.vias:
            net = getattr(v, "net_name", "") or getattr(v, "net", "") or ""
            if net:
                via_count[net] = via_count.get(net, 0) + 1
        stub_nets = sorted(
            net for net, cnt in via_count.items()
            if cnt >= 2 and any(kw.upper() in net.upper() for kw in high_speed_kw)
        )
        if stub_nets:
            return [RuleViolation(
                rule_name="短桩线检查",
                description=(f"{layer_count} 层板高速网络 {', '.join(stub_nets[:3])} "
                             f"各有 ≥2 个过孔，可能存在 stub 分支"),
                severity=RuleSeverity.INFO,
                suggestion="高速信号过孔→走线→过孔结构中，分支长度(Stub)应<λ/10。多余过孔 stub 需背钻或避免。",
                theory="Stub 在高速信号路径中形成1/4波长谐振腔——f_res=c/(4×L×√εr)。当 f_res 落入信号带宽时产生深度陷波，破坏眼图。>1GHz 信号 stub 需<3mm。",
            )]
        return []


    def _check_net_antenna(self, bom_items, positions, netlist):
        """天线效应检查：大面积未连接网络的铜皮可能成为天线"""
        pcb = self._pcb_data
        if not pcb or not pcb.nets: return []
        unconnected = 0
        for name, net in pcb.nets.items():
            pins = getattr(net, "pins", []) or []
            if len(pins) <= 1 and name and not name.upper().startswith("GND"):
                unconnected += 1
        if unconnected > 2:
            return [RuleViolation(
                rule_name="天线效应检查",
                description=f"{unconnected} 个网络仅连接 ≤1 个引脚，可能为浮空网络或天线",
                severity=RuleSeverity.WARNING,
                suggestion="单端网络(只有1个引脚)检查是否为未布线或孤岛。大面积浮空铜皮=EMI天线。",
                theory="浮空导体在电磁场中感应电压，长度=λ/4时成为高效天线。10cm 导体在 750MHz 共振。删除浮空铜或接地(打过孔)。",
            )]
        return []


    def _check_ground_plane_continuity(self, bom_items, positions, netlist):
        """地平面连续性：GND 铺地应避免割裂"""
        pcb = self._pcb_data
        if not pcb: return []
        return [RuleViolation(
            rule_name="地平面连续性检查",
            description="高速信号需要连续的地平面作为回流路径。割裂的地平面增加环路面积和EMI。",
            severity=RuleSeverity.INFO,
            suggestion="关键信号(时钟/高频)下方保证完整 GND 平面。信号跨分割区需加stitching电容(10nF)桥接回流。",
            theory="高速信号的回流电流沿最小阻抗路径(紧邻信号线下方)流回源端。地平面割裂→回流绕行→环路面积↑→EMI↑。>50MHz 信号必须保证连续参考平面。",
        )]


    def _check_via_thermal_relief(self, bom_items, positions, netlist):
        """过孔热焊盘：大面积铜皮上的过孔应使用热焊盘连接"""
        pcb = self._pcb_data
        if not pcb or not pcb.vias: return []
        via_count = len(pcb.vias)
        if via_count > 20:
            return [RuleViolation(
                rule_name="过孔热焊盘检查",
                description=f"PCB 含 {via_count} 个过孔，大面积铜皮上的过孔应使用热焊盘(Thermal Relief)连接",
                severity=RuleSeverity.INFO,
                suggestion="大面积 GND/VCC 铜皮上的过孔用热焊盘(十字花连接)而非全连接，便于手工焊接返修。",
                theory="全连接过孔在大面积铜皮上散热极快→烙铁无法熔化焊锡→虚焊。热焊盘用 4 条细径(通常 0.25mm)限制热传导，使焊点可达到焊接温度。",
            )]
        return []


    def _check_hs_signal_reference_plane(self, bom_items, positions, netlist):
        """高速信号参考平面检查"""
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        hs_nets = [t.net_name for t in pcb.traces
                   if t.net_name and any(kw.upper() in t.net_name.upper()
                   for kw in ["CLK", "USB", "HDMI", "PCIE", "SDRAM", "LVDS", "ETH"])]
        if hs_nets:
            return [RuleViolation(
                rule_name="高速信号参考平面检查",
                description=f"{len(set(hs_nets))} 个高速网络需确认邻层为完整 GND 参考平面",
                severity=RuleSeverity.WARNING,
                suggestion="高速信号邻层必须是完整 GND 平面(不分割)。4层板推荐 SIG-GND-PWR-SIG 叠层。",
                theory="微带线/带状线特性阻抗取决于信号到参考平面的距离(H)。邻层跨分割区→阻抗突变→反射、串扰↑。IPC-2221 建议高速信号不能跨越参考平面分割区。",
            )]
        return []


    def _check_impedance_matching(self, bom_items, positions, netlist):
        """特征阻抗匹配 — 只判「目标表」命中的高速接口差分对，按对聚合一次。

        2026-09-24 抽查修正（原判据三处硬伤）：
        ① 目标表本身就是差分值（USB 90Ω / HDMI·LVDS·ETH 100Ω），却拿单端
           microstrip_impedance 去比 → 结构性偏差，USB 网络必报；
        ② 按网络名子串命中即报 ERROR，USB_VBUS / HDMI_HCEC / HDMI_TX_SDA 全中；
        ③ traces[:50] 截断且按折线逐条报，同一网络重复计数。

        2026-10-09 判读修正（78 板全量 297 条逐条复核，
        experiment_results/impedance_recheck_2026-10-09/）：
        ④ 单端半区 45 条全是 SPI/SIM/SDIO/晶振类时钟名——「时钟按 50Ω」并非
           任何板子的设计要求，语料里真 RF 为 0——单端缩到 RF/天线（词边界）；
        ⑤ 差分对 P/N 两条各报一次 → 按对聚合，一条违规带双网名；
        ⑥ 目标表未命中的对（RS485、WL-SDIO 等工程声明的「差分组」）此前默认
           套 100Ω——这些接口没有受控阻抗要求，改为表外不判；表补
           MIPI/DSI/CSI、PCIE、SATA（均 100Ω 差分，语料 47 对按真实标准保留）。

        叠层仍按 4 层典型 h=0.2mm/εr=4.5 兜底（.epro2 不含叠层数据）；4 层板
        LVDS/USB 样本换 JLC 真实叠层（PP 0.21mm/εr≈4.6）复算同样越界——
        保留的差分告警是真检出，不是 h 假设的产物。
        """
        from src.pcb.calculator import (
            microstrip_impedance, trace_width_for_impedance, differential_impedance,
        )

        pcb = self._pcb_data
        if not pcb or not pcb.traces:
            return []

        h_mm, er = 0.2, 4.5   # 工程未提供叠层参数时的 4 层板典型兜底值

        # 差分组（工程声明优先，退化后缀配对）：upper 排序键去重 → 原名对
        pairs: dict[tuple, tuple] = {}
        for _label, nets, _src in self._diff_groups_src(pcb):
            if len(nets) != 2:
                continue
            key = tuple(sorted(str(n).upper() for n in nets))
            pairs.setdefault(key, tuple(str(n) for n in nets))
        diff_members = {n for key in pairs for n in key}

        # 每个网络只取最小线宽判一次（原来按折线条数逐条报，同一网络重复计数）
        widths: dict[str, float] = {}
        for t in pcb.traces:
            if t.net_name and t.width_mm > 0:
                prev = widths.get(t.net_name)
                if prev is None or t.width_mm < prev:
                    widths[t.net_name] = t.width_mm

        # 高速接口差分目标（Ω）。表外接口（RS485/CAN/SDIO 等声明的「差分组」）
        # 没有受控阻抗要求，不套默认值硬判。
        diff_targets = {"USB": 90.0, "HDMI": 100.0, "LVDS": 100.0, "ETH": 100.0,
                        "MIPI": 100.0, "PCIE": 100.0, "SATA": 100.0}
        single_kw = ("rf", "ant", "antenna")

        violations = []
        gap_cache: dict = {}
        for key in sorted(pairs):
            z_target = next((z for kw, z in diff_targets.items()
                             if any(kw in n for n in key)), None)
            if z_target is None:
                continue
            orig = pairs[key]
            if not all(n in widths for n in orig):
                continue          # 有成员未布线，无法判定
            w = min(widths[n] for n in orig)
            if key not in gap_cache:      # 每对只算一次对内间距（几何很贵）
                gap_cache[key] = self._pair_min_gap(pcb, list(orig))
            s_mm = gap_cache[key]
            if not s_mm or s_mm <= 0:
                s_mm = 2 * w
            z_actual = differential_impedance(
                microstrip_impedance(w, h_mm, er=er), s_mm, h_mm, er=er)
            if abs(z_actual - z_target) <= z_target * 0.25:
                continue
            violations.append(RuleViolation(
                rule_name="特征阻抗匹配检查",
                description=(f"差分对 [{'/'.join(orig)}]: 线宽 {w:.3f}mm / "
                             f"对内间距 {s_mm:.3f}mm → Z≈{z_actual:.0f}Ω，"
                             f"偏离目标 {z_target:.0f}Ω 超过 ±25%"),
                severity=RuleSeverity.ERROR,
                location="/".join(orig),
                suggestion=(f"调整线宽 {w:.3f}mm 与对内间距 {s_mm:.3f}mm 的组合，"
                            f"使差分阻抗 ≈{z_target:.0f}Ω（当前 {z_actual:.0f}Ω）"
                            f"。介质厚度/介电常数按 4 层板典型值 {h_mm}mm / εr={er} "
                            "估算；精确控制请用 PCB 厂商提供的叠层参数（Polar Si9000）。"),
                theory="微带线 Z₀=(87/√(εr+1.41))·ln(5.98h/(0.8w+t))；差分线 "
                       "Zdiff≈2·Z₀·(1-0.48·exp(-0.96·s/h))——差分网络必须用差分公式与差分"
                       "目标比对，拿单端公式去比差分目标会结构性地差近一倍。"
                       "阻抗不匹配→反射(Γ=(ZL-Z₀)/(ZL+Z₀))→过冲/振铃/EMI↑。",
            ))

        # 单端只判 RF/天线（50Ω）：时钟/SPI/晶振类网络没有受控阻抗要求
        for name, w in sorted(widths.items()):
            if _is_power_or_ground_net(name):
                continue
            if name.upper() in diff_members:
                continue
            if not _kw_hit(name.lower(), single_kw):
                continue
            z0_single = microstrip_impedance(w, h_mm, er=er)
            if abs(z0_single - 50.0) <= 50.0 * 0.25:
                continue
            w_target = trace_width_for_impedance(50.0, h_mm, er=er)
            violations.append(RuleViolation(
                rule_name="特征阻抗匹配检查",
                description=(f"网络 [{name}] 单端: 线宽 {w:.3f}mm → Z≈{z0_single:.0f}Ω，"
                             f"偏离目标 50Ω 超过 ±25%"),
                severity=RuleSeverity.ERROR,
                location=name,
                suggestion=(f"调整线宽至 {w_target:.3f}mm 使 Z₀≈50Ω"
                            f"（当前 {w:.3f}mm → {z0_single:.0f}Ω）。"
                            f"介质厚度/介电常数按 4 层板典型值 {h_mm}mm / εr={er} "
                            "估算；精确控制请用 PCB 厂商提供的叠层参数（Polar Si9000）。"),
                theory="微带线 Z₀=(87/√(εr+1.41))·ln(5.98h/(0.8w+t))。"
                       "阻抗不匹配→反射(Γ=(ZL-Z₀)/(ZL+Z₀))→过冲/振铃/EMI↑。",
            ))
        return violations
