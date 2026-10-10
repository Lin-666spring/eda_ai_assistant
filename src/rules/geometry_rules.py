"""走线/过孔/几何类规则 —— 从 checker.py 机械迁出（P1-6 阶段B，纯移动）。"""

import logging
import math
import re
from collections import Counter
from ..constants import PCB
from ..pcb.geometry import chain_segments, point_in_polygon, segment_touches_polygon, trace_corners

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
    _is_gnd_net,
    _is_inner_layer,
    _is_power_or_ground_net,
    _kw_hit,
    _net_class,
    _net_kw_hit,
    _parallel_overlap_len,
    _parse_capacitance,
    _parse_component_value,
    _pt_seg_dist,
    _seg_seg_dist,
    group_violations_by_component,
    rule_kind,
)

logger = logging.getLogger(__name__)


def _shape_touches(sa: dict, sb: dict) -> bool:
    """铜形 A 的外环是否触及铜形 B（A 的环边采样点落入 B 内/边上）。

    孤岛判定的连通传递用：网格填充铜互触即导通。采样步长 0.5mm，
    对板级尺度的贴合判定足够。
    """
    outer_b = sb.get("outer") or []
    if len(outer_b) < 3:
        return False
    voids_b = sb.get("voids") or []
    outer_a = sa.get("outer") or []
    n_a = len(outer_a)
    for i in range(n_a):
        x1, y1 = outer_a[i]
        x2, y2 = outer_a[(i + 1) % n_a]
        length = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(length / 0.5))
        for k in range(n + 1):
            t = k / n
            if point_in_polygon((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t),
                                outer_b, voids_b):
                return True
    return False


def _net_chain_path_len(segments, tol: float = 0.01) -> float:
    """网络走线段集的最长连续路径长（mm）。

    chain_segments 串折线；端点处度数 ≥3 的分支结点会把贯通路径切成
    多条折线，所以再在「折线端点图」上取**树的直径**（两次最远点 BFS，
    每个连通分量取最大）——叶子到叶子才是信号的实际最坏走法。
    带环分量（信号网里几乎不存在）保守按分量总长计。
    """
    polys = chain_segments(segments, tol=tol)
    if not polys:
        return 0.0

    def _key(p):
        return (round(p[0], 3), round(p[1], 3))

    adj: dict[tuple, list[tuple[tuple, float]]] = {}
    for poly in polys:
        w = sum(math.dist(a, b) for a, b in zip(poly, poly[1:]))
        u, v = _key(poly[0]), _key(poly[-1])
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))

    def _farthest(start):
        dist = {start: 0.0}
        queue = [start]
        best_node, best_d = start, 0.0
        while queue:
            nxt = []
            for u in queue:
                for v, w in adj[u]:
                    if v not in dist:
                        dist[v] = dist[u] + w
                        if dist[v] > best_d:
                            best_node, best_d = v, dist[v]
                        nxt.append(v)
            queue = nxt
        return best_node, best_d, dist

    total = 0.0
    seen: set[tuple] = set()
    for node in adj:
        if node in seen:
            continue
        # 收集本连通分量的结点与边数，判环（邻接表里每条边出现两次）
        comp_nodes, comp_edge_ends = {node}, 0
        stack = [node]
        while stack:
            cur = stack.pop()
            comp_edge_ends += len(adj[cur])
            for nxt, _w in adj[cur]:
                if nxt not in comp_nodes:
                    comp_nodes.add(nxt)
                    stack.append(nxt)
        seen |= comp_nodes
        if comp_edge_ends // 2 >= len(comp_nodes):   # 有环：保守按总长
            total = max(total, sum(w for es in
                                   (adj[n] for n in comp_nodes)
                                   for _, w in es) / 2.0)
            continue
        u, _d1, _ = _farthest(node)
        _v, d2, _ = _farthest(u)
        total = max(total, d2)
    return total


class GeometryRulesMixin:
    """方法集由 facade DesignRuleChecker 组合；此处无状态、无 __init__。"""


    # ═══ PCB-data rules ═══

    def _check_signal_traces(self, bom_items, positions, netlist):
        """信号线宽度：绝对工艺下限（按层数区分），相对条款已删。

        绝对硬下限：≥4 层 0.088mm（标准多层工艺 3.5mil=0.0889mm 以内），<4 层
        0.1mm（一般厂最小 4mil）→ 细于下限可能做不出来。
        2026-10-09 噪声清扫：删除「细于本板主流线宽 60% 且混用线宽」相对条款——
        焊盘入口颈口(neck-down)是标准做法，金样 129 条警告全是这一类（RK3576
        一板 73 条：0.127mm 颈口 vs 0.254mm 主流）。0.127mm(5mil) 下限也曾校准
        过：金样 ≤2 层板有 438 个网落在 [0.1,0.127)、一板 149 网，会重演
        「一板 500 条」误报（constants 2026-09-24 注），故下限维持 0.1mm。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        # 2026-09-24 抽查修正：绝对下限按层数区分。
        # 2026-10-09 再校准：≥4 层下限 0.09 → 0.088——3.5mil = 0.0889mm 是标准
        # 多层工艺，原 0.09 比它大 1µm，把金样里整板按 3.5mil 布线的万兆软路由
        # 板误报 79 条。
        layer_count = len({t.layer for t in pcb.traces if t.layer}) or len(
            getattr(pcb, "layers", None) or []
        )
        abs_min = 0.088 if layer_count >= 4 else PCB.SIGNAL_TRACE_ABS_MIN_WIDTH_MM
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
        # 本板信号线宽众数（按折线条数）——只用于建议文案里给出对照
        dom_w = Counter(t.width_mm for t in sig_traces).most_common(1)[0][0]
        for name, w in net_min.items():
            if w >= abs_min:
                continue
            violations.append(RuleViolation(
                rule_name="信号线宽度检查",
                description=f"网络 [{name}] 最小线宽 {w:.3f}mm，细于工艺下限 {abs_min}mm",
                severity=RuleSeverity.WARNING, location=name,
                suggestion=(f"确认该网络线宽是否有意为之：工艺下限约 {abs_min}mm"
                            f"({3.5 if abs_min < 0.1 else 4}mil)，本板其余走线多用 {dom_w:.3f}mm。"
                            "高速信号还需确认阻抗匹配。"),
                theory="走线宽度由 PCB 工艺能力和信号完整性共同决定。一般厂最小 4mil(0.1mm)，"
                       "多层板常规能力 3.5mil(0.09mm)。细于下限的走线可能蚀刻不良/过电流能力不足。"))
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

        # 从 BOM 估算电源电流；电机驱动电流单独取出，在 _estimate_net_current
        # 里路由到 VM/MOTOR 动力网，不再摊进主电源（2026-10-10 标准表批）
        est_current_a = self._estimate_power_current(bom_items)
        motor_current_a = self._estimate_motor_current(bom_items)
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
            I = self._estimate_net_current(name, est_current_a, motor_current_a)
            is_inner = _is_inner_layer(pcb, layer)
            capacity = ipc2221_current_capacity(mw, cu, tr, is_inner)
            req_w = ipc2221_trace_width(I, cu, tr, is_inner)

            # 2026-10-10 标准表批：加 1.5× 余量带——capacity<I 才是 ERROR，
            # I≤capacity<1.5I 提示余量不足（WARNING）。估算电流本身带 ±20%
            # 误差，0.89A 容量对 0.90A 需求报 ERROR 是假阳性边界。
            if capacity < I:
                severity = RuleSeverity.ERROR
                head = "载流不足"
                cmp_txt = "<"
                tail = f"，需宽 ≥{req_w:.3f}mm"
            elif capacity < 1.5 * I:
                severity = RuleSeverity.WARNING
                head = "载流余量不足(<1.5×)"
                cmp_txt = "≈"
                tail = f"，无故障裕量，建议宽 ≥{req_w:.3f}mm"
            else:
                continue
            violations.append(RuleViolation(
                rule_name="电源线载流检查",
                description=(
                    f"电源网络 [{name}] {layer or '未知层'}"
                    f"（{'内层' if is_inner else '外层'}）: "
                    f"线宽 {mw:.3f}mm 载流 {capacity:.2f}A "
                    f"{cmp_txt} 需求 {I:.2f}A，{head}{tail}"
                ),
                severity=severity,
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
        artifact_floor = PCB.TRACE_CORNER_ARTIFACT_ANGLE_FLOOR_DEG
        right_min = PCB.TRACE_RIGHT_ANGLE_MIN_DEG
        right_max = PCB.TRACE_RIGHT_ANGLE_MAX_DEG
        # 2026-09-24 抽查修正：
        # ① 直角只对高速/时钟/差分网络报——规则自述「普通低速线可接受」，对所有网络
        #    一律 INFO 的结果是 75/76 块板都响；
        # ② 锐角增加「焊盘入口几何」二次过滤——抽样里 2/3 的锐角其实是元件焊盘/过孔
        #    入口的短拐角（腿长 0.2mm、距元件 0.4mm），不是布线拐角。
        # 2026-10-09 噪声清扫（78 板金样，439 条里 369 条「最尖 45.0°」）：
        # ③ 闭合折线（铺铜外框/void 轮廓/网格单元）豁免——覆铜几何里的 45° 是画法
        #    不是酸陷阱（45° 折线布线的内角只会是 135°/90°）；
        # ④ 内角 <1° 的折返点跳过——端点串联在近重合节点上产生的数值伪影（零宽缝隙）。
        # ⑤ 顶点吸附在过孔圆心（±VIA_SNAP）的尖角跳过——那是两条路径经同一过孔
        #    相接的结合点，不是布线拐角（金样 341 个剩余尖角里 110 个顶点与过孔
        #    圆心完全重合）；
        # ⑥ 内角恰为 45°（±GRID_EPS）的栅格楔形跳过——45° 栅格布线的真拐角内角
        #    只会是 135°/90°，内角 45.0° 全部来自「独立路径端点相接」或蛇形/绕障
        #    折返（金样 199/341），均非布线失误；自由角度的楔形仍照报；
        # ⑦ (net,layer) 已注册覆铜区的 trace 整组跳过——GND 覆铜 thermal/void 的
        #    弧弦模板角（如 RK3576 的 82.4°×N）是覆铜几何，不是走线。
        diff_members: set = set()
        for _label, nets, _src in self._diff_groups_src(pcb):
            diff_members.update(str(n).upper() for n in nets)
        pour_keys: set = {
            (str(p.get("net_name")), str(p.get("layer")))
            for p in (getattr(pcb, "copper_pours", None) or [])
            # 只认真铺铜：FILL/POLY 补丁铜（2026-10-09 起入表）不该扩大
            # 覆铜区豁免面，否则其同名网络的走线拐角会被整组吞掉
            if str(p.get("source") or "POUR") == "POUR"
        }
        via_pts: list = []
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
            via_pts.append((ax, ay))
            anchor_grid.setdefault((math.floor(ax), math.floor(ay)), []).append((ax, ay))
        for pos in (getattr(pcb, "component_positions", None) or {}).values():
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                ax, ay = float(pos["x"]), float(pos["y"])
                anchor_grid.setdefault((math.floor(ax), math.floor(ay)), []).append((ax, ay))
        clear_r = PCB.TRACE_CORNER_PAD_CLEAR_MM
        pad_leg = PCB.TRACE_CORNER_PAD_LEG_MM
        via_snap = PCB.TRACE_CORNER_VIA_SNAP_MM
        grid_eps = PCB.TRACE_CORNER_GRID_EPS_DEG

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

        def _at_via_join(c) -> bool:
            """顶点吸附过孔圆心 → 两条路径经同一过孔相接的结合点。"""
            x, y = c.vertex[0], c.vertex[1]
            return any(math.hypot(x - vx, y - vy) <= via_snap for vx, vy in via_pts)

        acute_violations = []
        right_violations = []
        for t in pcb.traces:
            if not t.net_name:
                continue
            if (t.net_name, t.layer) in pour_keys:
                continue        # ⑦ 覆铜网格/thermal 弦线混入的「走线」
            corners = trace_corners(t.segments, min_leg_mm=PCB.TRACE_CORNER_MIN_LEG_MM)
            if not corners:
                continue
            acute = [c for c in corners
                     if artifact_floor <= c.angle_deg < acute_max
                     and not c.is_closed
                     and abs(c.angle_deg - 45.0) > grid_eps
                     and not _at_via_join(c)
                     and not _is_pad_entry(c)]
            right = [c for c in corners if right_min <= c.angle_deg <= right_max
                     and not c.is_closed
                     and not _at_via_join(c)]
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
        # 2026-10-09 抽查修正：裸子串 "SW" 命中 …BUZZER_SWITCH/GUN_SWITCH（拨码/
        # 轻触开关网络被当高速网）。改用网络名词边界匹配（右侧放行数字后缀
        # SW1/CLK2），并把电源/地网整体排除——缝合孔再多也属正常。
        kws = [k.lower() for k in PCB.VIA_DENSITY_NET_KEYWORDS]
        via_per_net: dict[str, int] = {}
        for v in (pcb.vias or []):
            net = getattr(v, "net_name", "") or getattr(v, "net", "")
            if not net:
                continue
            if _is_power_or_ground_net(net):
                continue
            if not _net_kw_hit(net, kws):
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


    @staticmethod
    def _pair_parallel_overlap(pcb, pair, cap: int = 20000) -> float:
        """差分对两条网络在同层走线间的最大平行重叠长度 (mm)；无同层走线返回 0。"""
        first: dict[str, list] = {}
        for t in pcb.traces:
            if t.net_name == pair[0]:
                first.setdefault(t.layer, []).extend(
                    (s[0], s[1], s[2], s[3]) for s in (t.segments or [])
                )
        best = 0.0
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
                    ov = _parallel_overlap_len(a, b, (s0[0], s0[1]), (s0[2], s0[3]))
                    if ov > best:
                        best = ov
        return best


    def _check_diff_pair_spacing(self, bom_items, positions, netlist):
        """差分对间距：成对走线应紧耦合（对内最小间距不应远大于线宽）。

        2026-09-24 抽查修正：① 只判工程 NET 规则里设计者显式定义的差分组——靠
        P/N、+/- 后缀猜出来的配对（D1_P/D1-、IN_D+/IN_D-）不是差分信号，一律跳过；
        ② 门限取「明显松耦合」（4W）：抽样判读里 3.0~4.5W 属阈值边界，
        按 3W 一刀切会把正常设计报成缺陷。
        2026-10-09 抽查修正：③ 高速接口门控——设计者给音频/UART/RC 节点标
        differentialName 不等于差分阻抗受控，只对 USB/HDMI/LVDS 等接口组判间距；
        ④ 平行重叠前置——两网没有实质平行走线（最长平行段 <5mm）时，「最小间距」
        量到的是交叉/换层泄漏距离，报「耦合过松」没有意义（抽样里重叠 0.0mm
        相距 2.8mm 也报 11.2W）。
        批4 2026-10-10 复核：四重门（engine声明+高速接口+平行≥5mm+>4W）为
        2026-10-09 有意收紧，金样零触发为预期，非死代码，逻辑不动。
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
            if not _kw_hit(f"{label} {' '.join(nets)}".lower(), _HIGH_SPEED_IF_KW):
                continue
            if self._pair_parallel_overlap(pcb, (nets[0], nets[1])) < PCB.CROSSTALK_MIN_PARALLEL_MM:
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


    # ── 差分对内等长公差分档（mm，2026-10-10 标准表批）──
    # FR4 ≈6.7ps/mm。USB2.0 位周期 2.08ns，2mm≈13ps，版图指南普遍放宽到
    # 1~2mm；HDMI/LVDS/MIPI/PCIE/SATA 与以太网 MDI 对内等长常用 0.5mm 档。
    # 表外差分组（RS485/CAN/SDIO 等工程声明的「差分组」）没有严格等长要求，
    # 沿用旧判据 2.0mm 绝对 + 10% 相对。描述文案与判据同取这一张表。
    _DIFF_SKEW_BANDS: tuple[tuple[tuple[str, ...], float, str], ...] = (
        (("USB",), 2.0, "USB2.0"),
        (("HDMI", "LVDS", "MIPI", "PCIE", "SATA"), 0.5, "高速串行"),
        (("ETH", "LAN", "RGMII"), 0.5, "以太网 MDI"),
    )
    _DIFF_SKEW_DEFAULT_MM = 2.0
    _DIFF_SKEW_DEFAULT_REL = 0.10   # 表外组附加相对判据（组内长度差 ≥10%）

    def _check_diff_pair_length(self, bom_items, positions, netlist):
        """差分对等长：按接口分档取对内长度差公差（_DIFF_SKEW_BANDS）。

        2026-09-24 抽查修正：0.5mm 一刀切对 USB2.0（位周期 2083ps，
        3.25mm≈22ps）、音频功放、直流输入 ± 都过严。
        2026-10-10 标准表批：0.5mm 换成按接口分档——USB2.0 档 2.0mm，
        HDMI/LVDS/MIPI/PCIE/SATA/ETH 档 0.5mm，表外组 2.0mm 绝对 + 10%
        相对（旧行为）；违规描述的门限数字与判据同取 _DIFF_SKEW_BANDS，
        消除「描述写 0.5mm、判据实际 2.0mm」的两张皮。
        2026-10-10 几何批：网络长度从「全网线段和」改成 **链路径长**——
        旧口径把多分支网络的每条支路都加总，T 型/星形网络的和不是任何
        信号实际走过的距离，支路越多差分差越虚高。现按 chain_segments
        串成折线，再在折线端点图上取**最长路径**（树直径；贯通结点的
        路径跨折线拼接，闭合环组件按全环长保守计）。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        diff_nets: set[str] = set()
        for _label, nets, _source in self._diff_groups_src(pcb):
            diff_nets.update(n for n in nets if n)
        lengths: dict[str, float] = {}
        for name in diff_nets:
            segs = [s for t in pcb.traces
                    if (t.net_name or "") == name
                    for s in (t.segments or []) if len(s) >= 4]
            if segs:
                lengths[name] = _net_chain_path_len(segs)
        for label, nets, source in self._diff_groups_src(pcb):
            lens = [lengths.get(n, 0.0) for n in nets]
            lens = [x for x in lens if x > 0]
            if len(lens) < 2:
                continue
            diff_mm = round(max(lens) - min(lens), 4)
            avg_len = sum(lens) / len(lens)
            # 接口分档：label+网络名命中哪档就用哪档公差。
            # 几何批修正：text 已 lower，关键词也必须 lower——旧写法
            # `kw in text`（大写关键词 vs 小写文本）恒 False，整张
            # _DIFF_SKEW_BANDS 是死代码，所有组都落表外口径
            # （金样两批 0 条分档文案，29b9766 引入时未暴露）。
            text = f"{label} {' '.join(nets)}".lower()
            tol, band = next(
                ((t, name) for kws, t, name in self._DIFF_SKEW_BANDS
                 if any(kw.lower() in text for kw in kws)),
                (self._DIFF_SKEW_DEFAULT_MM, "表外差分组"))
            over = diff_mm > tol
            if band == "表外差分组":
                over = over or diff_mm >= self._DIFF_SKEW_DEFAULT_REL * avg_len
            if not over:
                continue
            violations.append(RuleViolation(
                rule_name="差分对等长检查",
                description=(f"差分/等长组 [{label}] 走线长度差 {diff_mm}mm "
                             f"({band}判据门限 {tol}mm，组内平均长 {avg_len:.1f}mm): "
                             + ", ".join(nets[:4])),
                severity=(RuleSeverity.WARNING if source == "engine" else RuleSeverity.INFO),
                location=label,
                    suggestion=(f"差分对走线长度差应 ≤{tol}mm（{band}档）。"
                                "用蛇形走线补偿短的一侧。蛇形幅度≥3W,间距≥2S。"),
                    theory="差分信号依赖两条线同时到达接收端来维持共模抑制。长度不匹配→到达时间差→差模分量→共模噪声↑、眼图闭合。FR4 中约 6.7ps/mm。",
                ))
        return violations


    # 调试/RTC 时钟网：包地建议对它们没有意义（SWD/JTAG 调试时钟速率低且
    # 短；32.768kHz RTC 晶振波长以公里计）。
    _CLOCK_GUARD_EXCLUDE_RE = re.compile(
        r"SWCLK|SWDCLK|SWD_CLK|\bTCK\b|\bTMS\b|\bTDO\b|\bTDI\b|32K|OSC32|32768")

    def _check_clock_guard_trace(self, bom_items, positions, netlist):
        """时钟信号包地：高频时钟应有包地走线

        2026-10-09 噪声清扫：原实现网络名含 CLK/OSC… 即报，金样 50 板 249 条
        （SWCLK 调试时钟、32.768kHz RTC 晶振也响）。加两道门：
        ① 调试/RTC 网排除（_CLOCK_GUARD_EXCLUDE_RE）；
        ② 长度门 CLOCK_GUARD_MIN_LENGTH_MM——包地防的是长距离耦合，晶振到 MCU
          的短线（金样分布：<10mm 占 31%、<15mm 占 14%）没有包地价值；≥15mm
          的长时钟跑线才提示（金样剩 ~140 条）。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        clk_kw = ["CLK", "CLOCK", "OSC", "XTAL", "MCLK", "SCLK", "HCLK"]
        min_len = PCB.CLOCK_GUARD_MIN_LENGTH_MM
        net_len: dict[str, float] = {}
        for t in pcb.traces:
            if not t.net_name:
                continue
            acc = net_len.setdefault(t.net_name, 0.0)
            for s in t.segments:
                acc += math.dist((s[0], s[1]), (s[2], s[3]))
            net_len[t.net_name] = acc
        seen: set = set()
        for t in pcb.traces:
            name = (t.net_name or "").upper()
            if not any(kw.upper() in name for kw in clk_kw):
                continue
            if self._CLOCK_GUARD_EXCLUDE_RE.search(name):
                continue
            if net_len.get(t.net_name, 0.0) < min_len:
                continue
            # traces 按 (网络, 层) 聚合，同一时钟网络跨层会出现多次，按网络去重
            if t.net_name in seen:
                continue
            seen.add(t.net_name)
            violations.append(RuleViolation(
                rule_name="时钟信号包地检查",
                description=f"时钟网络 [{t.net_name}] 走线长约 {net_len[t.net_name]:.0f}mm，建议添加包地走线",
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
        2026-10-09 抽查修正：差分对自身两半豁免——P/N 两半本来就要 2W 紧耦合
        平行全程，套 3W 必然整组误报（10-06 抽查 5/5 串扰样本全是这一类，
        AirLink 21 对里 17 对、Mini-LinuxPC 17 对里 11 对）。同一差分组（工程
        声明或名字猜测配对）的两网不再互判串扰；「diff」类别只认工程声明，
        猜测配对的成员退回按名字分类。
        2026-10-10 判据批：最严对标注排除 GND 族（_is_gnd_net）——地线贴
        高速线是隔离手法，金样 11/71 条把 [信号/GND] 标成最严 offender；
        只改最严对标注、不改线对计数。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        diff_members: set = set()   # 仅工程声明 →「diff」类别（按接口名猜的不算）
        exempt_pairs: set = set()   # 同一差分组两半 → 对内豁免（含名字猜测配对）
        for label, nets, src in self._diff_groups_src(pcb):
            ups = sorted({str(n).upper() for n in nets})
            if src == "engine":
                diff_members.update(ups)
            if len(ups) == 2:
                exempt_pairs.add((ups[0], ups[1]))
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
                net_u = (t.net_name or "").upper()
                for s in t.segments:
                    idx = len(segs)
                    a, b = (s[0], s[1]), (s[2], s[3])
                    x0, x1 = (a[0], b[0]) if a[0] <= b[0] else (b[0], a[0])
                    y0, y1 = (a[1], b[1]) if a[1] <= b[1] else (b[1], a[1])
                    segs.append((t.net_name, net_u, w, a, b, x0, x1, y0, y1, cls))
                    for ci in range(int((x0 - radius) // cell), int((x1 + radius) // cell) + 1):
                        for cj in range(int((y0 - radius) // cell), int((y1 + radius) // cell) + 1):
                            grid.setdefault((ci, cj), []).append(idx)
            contested: dict = {}
            for i, (net, net_u, w, a, b, x0, x1, y0, y1, cls) in enumerate(segs):
                seen = set()
                for ci in range(int((x0 - radius) // cell), int((x1 + radius) // cell) + 1):
                    for cj in range(int((y0 - radius) // cell), int((y1 + radius) // cell) + 1):
                        for j in grid.get((ci, cj), ()):
                            if j <= i or j in seen:
                                continue
                            seen.add(j)
                            n2, n2_u, w2, c, d, cx0, cx1, cy0, cy1, cls2 = segs[j]
                            if n2 == net:
                                continue
                            # 差分对自身两半：紧耦合是设计意图，不构成串扰风险
                            pk = (net_u, n2_u) if net_u <= n2_u else (n2_u, net_u)
                            if pk in exempt_pairs:
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
            # 2026-10-10 判据批：最严对标注排除 GND 族——地线贴高速线是隔离/
            # 回流手法不是风险源（suggestion 自己也建议「加接地隔离」），金样
            # 71 条串扰里 11 条的最严对是 [信号/GND]（最大 200.7mm）。只改
            # 标注不动计数：N 对几何事实仍在，若全对都是 GND 相邻则不标最严。
            sig_pool = {k: v for k, v in hits.items()
                        if not (_is_gnd_net(k[0]) or _is_gnd_net(k[1]))}
            desc = (f"{layer} 层 {len(hits)} 对走线平行间距 <{factor:.0f}W 且重叠 "
                    f"≥{min_par}mm")
            if sig_pool:
                worst = max(sig_pool.items(), key=lambda kv: kv[1])
                desc += f"；最严重 [{worst[0][0]}/{worst[0][1]}] {worst[1]:.1f}mm"
            violations.append(RuleViolation(
                rule_name="3W 串扰间距检查",
                description=desc,
                severity=RuleSeverity.WARNING, location=layer,
                suggestion=(f"平行走线间距 ≥{factor:.0f}W(W=线宽)，高速信号 ≥5W。增大间距或加接地隔离；"
                            "平行长度越短越安全。"),
                theory="微带线串扰在间距=3W 时近端串扰(NEXT)≈1~3%。间距减半→NEXT↑6~10dB。串扰强度随平行长度增加，交叉/垂直走线不构成串扰。3W 是经验准则。",
            ))
        return violations


    def _check_loop_area(self, bom_items, positions, netlist):
        """环路面积：高速信号应最小化电流环路面积

        批4 2026-10-10 审计残留：
        ① 裸子串 "SW" 命中 …BUZZER_SWITCH/GUN_SWITCH（拨码/轻触开关网络被当
           高速网）——关键词复用 PCB.VIA_DENSITY_NET_KEYWORDS 同一张表，
           匹配器统一换 _net_kw_hit（右侧放行数字后缀 SW1/CLK2，拒绝内嵌），
           表内容不动；与 _check_via_density 同口径；
        ② 电源/地网络排除（_is_power_or_ground_net，对齐串扰规则）；
        ③ 解析器没有回流路径几何，量不出真实环路面积——只有「名字像 +
           长度>50mm」两道弱证据时按需确认项措辞（INFO），文案明说需人工
           确认实际回流路径，不写确定性违规语气。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        violations = []
        kws = [k.lower() for k in PCB.VIA_DENSITY_NET_KEYWORDS]
        for net_name, net in (pcb.nets or {}).items():
            if _is_power_or_ground_net(net_name):
                continue
            if not _net_kw_hit(net_name, kws):
                continue
            length = getattr(net, "total_length_mm", 0) or 0
            if length > 50:  # >50mm 长的高速走线
                violations.append(RuleViolation(
                    rule_name="环路面积检查",
                    description=(f"网络 [{net_name}] 走线长度 {length:.0f}mm 且名字含"
                                 "高速关键词——环路面积可能偏大，需人工确认实际回流路径"),
                    severity=RuleSeverity.INFO, location=net_name,
                    suggestion="高速信号紧邻参考平面走线，信号/回流路径构成的环路面积最小化。多层板保证关键信号邻层为完整 GND 平面。",
                    theory="EMI 辐射强度 ∝ 环路面积 × 频率² × 电流。相邻层的信号-回流间距 = 介质厚度(4 层板 ≈0.1~0.2mm),环路面积极小。双层板缺连续参考平面,需手动布置回流路径。",
                ))
        return violations


    def _check_copper_pour_connectivity(self, bom_items, positions, netlist):
        """铜皮连接：大面积铜皮应避免孤岛

        2026-10-09 数据补全后激活：解析器现读取 POUR 环几何，并把带网络的
        FILL/POLY 铜形入表（此前 copper_pours 只有网络名和环数，两块电赛板
        整片 GND 补丁铜被恒报「未包含铜皮数据」）。判定口径与数据能力边界：
        整片铜区边界内找不到任何同网络过孔、同层同网络走线端点 → 孤岛嫌疑；
        铜区内部因避让切成的小分片需要填充结果做布尔运算，.epru 不含填充
        几何，不判。
        """
        pcb = self._pcb_data
        if not pcb: return []
        shapes = [p for p in (getattr(pcb, "copper_pours", None) or [])
                  if p.get("net_name") and p.get("outer")]
        if not shapes:
            return [RuleViolation(
                rule_name="铜皮连接检查",
                description="PCB 文件未包含铜皮数据，请确认覆铜无孤岛",
                severity=RuleSeverity.INFO,
                suggestion="覆铜后执行 DRC 检查孤岛铜皮(Dead Copper/Islands)。孤岛铜皮应删除或添加过孔接地。",
                theory="孤岛铜皮既不接地也不接任何网络，相当于悬浮的天线→接收/辐射 EMI。GHz 频段时长度=λ/4 即可成为有效天线。删除或接地均可解决。",
            )]
        via_pts: dict = {}
        for v in (pcb.vias or []):
            if v.net_name:
                via_pts.setdefault(v.net_name, []).append(tuple(v.position))
        # 元件焊盘：双层板铜皮的主要接入方式（金样扩展板 0 个 GND 过孔、
        # 288 片 GND 补丁铜全靠焊盘桥接），没有它孤岛判定会整板误报
        pad_rows: dict = {}
        for p in (getattr(pcb, "pads", None) or []):
            if p.get("net"):
                pad_rows.setdefault(p["net"], []).append(p)
        trace_segs: dict = {}
        for t in (pcb.traces or []):
            if not t.net_name:
                continue
            trace_segs.setdefault((t.net_name, t.layer), []).extend(t.segments)
        # 有 orphan 焊盘记录的网络：焊盘几何缺失，铜片「无附件」不能作为
        # 孤岛证据（接入者恰好可能是那颗丢失的焊盘）——无法验证不判
        orphan_nets = set((getattr(pcb, "metadata", None) or {}).get("orphan_nets") or ())
        # 每片铜的直接接入证据。过孔/焊盘只对铜片外环判内点：热焊盘的清距
        # void 环会圈住焊盘中心，但物理上经辐条连接，void 不构成「未接入」
        # 证据。过孔贯通各层不看层；金属化焊盘（thru）任意层接入，表贴焊盘
        # 看层号；走线允许「穿过」铜片接入，且须与铜皮同层
        bboxes: list = []
        direct: list = []
        judged: list = []
        for sh in shapes:
            net = sh["net_name"]
            outer = sh["outer"]
            voids = sh.get("voids") or []
            xs = [p[0] for p in outer]
            ys = [p[1] for p in outer]
            bboxes.append((min(xs), min(ys), max(xs), max(ys)))
            if len(outer) < 3 or net in orphan_nets:
                direct.append(True)      # 不判的片视作已接入（不出孤岛报告）
                judged.append(False)
                continue
            judged.append(True)
            layer_id = sh.get("layer_id")
            attached = any(point_in_polygon(pt, outer)
                           for pt in via_pts.get(net, ()))
            if not attached:
                attached = any(
                    (pd.get("thru") or pd.get("layer_id") == layer_id)
                    and point_in_polygon((pd["x"], pd["y"]), outer)
                    for pd in pad_rows.get(net, ())
                )
            if not attached:
                for sx1, sy1, sx2, sy2 in trace_segs.get((net, sh.get("layer")), ()):
                    if (max(sx1, sx2) < xs[0] or min(sx1, sx2) > xs[2]
                            or max(sy1, sy2) < ys[0] or min(sy1, sy2) > ys[2]):
                        continue
                    if segment_touches_polygon((sx1, sy1), (sx2, sy2), outer, voids):
                        attached = True
                        break
            direct.append(attached)
        # 同网络铜形连通并查集：网格填充铜由大量互触小矩形组成，接入证据
        # 经「相邻铜形」传递（A 触 B、B 上有过孔 ⇒ A 也接入）
        parent = list(range(len(shapes)))

        def _find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        by_net: dict = {}
        for idx, sh in enumerate(shapes):
            by_net.setdefault(sh["net_name"], []).append(idx)
        for _net, idxs in by_net.items():
            for a in range(len(idxs)):
                ia = idxs[a]
                ax1, ay1, ax2, ay2 = bboxes[ia]
                for b in range(a + 1, len(idxs)):
                    ib = idxs[b]
                    bx1, by1, bx2, by2 = bboxes[ib]
                    if ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1:
                        continue
                    if _shape_touches(shapes[ia], shapes[ib]) or \
                            _shape_touches(shapes[ib], shapes[ia]):
                        parent[_find(ia)] = _find(ib)
        root_ok: dict = {}
        for idx in range(len(shapes)):
            r = _find(idx)
            root_ok[r] = root_ok.get(r, False) or direct[idx]
        islands = [shapes[i] for i in range(len(shapes))
                   if judged[i] and not root_ok[_find(i)]]
        if not islands:
            return []
        detail = "、".join(
            f"{s['net_name']}@{s.get('layer')}" for s in islands[:5])
        return [RuleViolation(
            rule_name="铜皮连接检查",
            description=(f"{len(islands)} 片铜区没有任何同网络过孔/焊盘/走线"
                         f"接入（含经相邻铜形传递），孤岛嫌疑: {detail}"),
            severity=RuleSeverity.INFO,
            suggestion="孤岛铜皮删除，或添加过孔接到同名网络；覆铜后重灌铺铜使孤岛消除。",
            theory="孤岛铜皮既不接地也不接任何网络，相当于悬浮的天线→接收/辐射 EMI。GHz 频段时长度=λ/4 即可成为有效天线。删除或接地均可解决。",
        )]


    # 测试点痕迹匹配（批4 2026-10-10）：封装名里独立 token 的 TP、
    # TESTPOINT/TEST-POINT/TEST POINT 变体、中文「测试点」
    _TP_FOOTPRINT_RE = re.compile(
        r"(?i)(?<![a-z0-9])tp(?![a-z0-9])|test[ _-]?point|测试点")

    def _check_testpoint_coverage(self, bom_items, positions, netlist):
        """测试点覆盖：关键网络应预留测试点

        批4 2026-10-10 审计残留改写：旧实现把所有命中关键词（VCC/RST/SWD…）
        的网络直接列为「缺少测试点」，全程没有测试点检测——与输入内容无关
        的存在性模板，金样大面积误报。现在：
        ① 真测试点检测：component_positions 里 footprint_name 命中
           TP/TESTPOINT/测试点 模式、或位号 TP 前缀的元件，经 netlist 收集
           其引脚所在网络；板上有任何测试点痕迹 → 静默（测点引脚↔网络的
           映射精度只够「板上有测试点」这一层，不逐网判缺）；
        ② 有 positions 但没有任何测试点痕迹，且 netlist 存在电源/复位/
           调试类关键网络 → 报一条汇总 INFO（不是逐网络 WARNING）；
        ③ 无 positions 或无 netlist → 诚实跳过：测试点痕迹在 positions、
           关键网络在 netlist，缺一即无法证伪，绝不再「关键词命中=缺测试点」。
        """
        pcb = self._pcb_data
        if not pcb: return []
        comp_pos = getattr(pcb, "component_positions", None) or {}
        nets = netlist or {}
        if not comp_pos or not nets:
            return []
        for ref, pos in comp_pos.items():
            pfx = "".join(ch for ch in str(ref) if ch.isalpha()).upper()
            if pfx == "TP":
                return []       # 位号 TP 前缀的元件：已有测试点痕迹
            if isinstance(pos, dict):
                fp = str(pos.get("footprint_name") or pos.get("footprint") or "")
                if fp and self._TP_FOOTPRINT_RE.search(fp):
                    return []
        # 关键网络：电源轨 + 复位/BOOT/调试口（_net_kw_hit 词边界，
        # SWD/SWCLK 不再内嵌命中其它词）
        key_net_kw = ("VCC", "VDD", "3V3", "5V", "RST", "RESET", "BOOT",
                      "SWD", "SWCLK", "SWDIO")
        key_nets = [n for n in nets if _net_kw_hit(n, key_net_kw)]
        if not key_nets:
            return []
        return [RuleViolation(
            rule_name="测试点覆盖检查",
            description=(f"板上未检测到测试点器件（位号 TP 前缀 / 封装 "
                         f"TP·TESTPOINT），{len(key_nets)} 个电源/复位/调试类"
                         f"关键网络缺乏专用测试点: {', '.join(key_nets[:5])}"),
            severity=RuleSeverity.INFO,
            location=", ".join(key_nets[:5]),
            suggestion="电源轨、复位、调试接口、关键信号预留 φ1.0mm 测试焊盘(TP)。间距≥2.54mm 便于探针/ICT。",
            theory="无测试点→调试时需手工飞线,成品批量测试用 ICT(在线测试)/飞针测试需夹具兼容的测试点布局。IPC-2221 建议测试点直径≥0.9mm,间距≥2.5mm。",
        )]


    def _check_silkscreen_readability(self, bom_items, positions, netlist):
        """丝印可读性：丝印应与焊盘/过孔有足够间距

        2026-10-09 噪声清扫：丝印几何（TEXT 坐标）尚未解析（.epro2 里 TEXT
        原子只有计数、无坐标，见 epro2_parser），没有数据就没有真实判定，
        原「含 N 个元件，建议检查丝印」是每板必响的模板（金样 78/78）。
        守卫读 metadata['silk_elements']（解析器落地丝印解析后填此键），当前
        恒缺 → 永不触发；数据可用后无需改判据即可启用。
        """
        pcb = self._pcb_data
        if not pcb:
            return []
        # 设计性休眠（批4 2026-10-10 确认）：解析器暂无 silk_elements 几何，
        # 规则保持静默；判据已备好，解析器落地丝印后无需改逻辑即可启用。
        if not (getattr(pcb, "metadata", None) or {}).get("silk_elements"):
            return []
        violations = []
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
        """丝印与焊盘间距：丝印文字不应覆盖焊盘

        2026-10-09 噪声清扫：同丝印可读性——丝印几何未解析，守卫
        metadata['silk_elements'] 落地前永不触发（原模板每板必响）。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.component_positions:
            return []
        # 设计性休眠（批4 2026-10-10 确认）：解析器暂无 silk_elements 几何，
        # 规则保持静默；判据已备好，解析器落地丝印后无需改逻辑即可启用。
        if not (getattr(pcb, "metadata", None) or {}).get("silk_elements"):
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

        2026-10-10 几何批：有真实轮廓环（outline_rings_mm，解析器由
        BOARD_OUTLINE 描边链回，含板内开槽）时按「线段-多边形边界真距离」
        判定——旧包围盒口径在圆角/异形板上与真边界差几毫米，切角板甚至
        会把含在板内的角区整体误报；跨界/越界段自然得 0。板框退回
        「铜包围盒」(source=copper) 时没有真边界，维持原守卫直接跳过；
        有 outline 而轮廓环缺失（异常数据）退回包围盒口径。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        bo = pcb.board_outline or {}
        if bo.get("source") != "outline":
            return []
        min_clearance = PCB.TRACE_EDGE_CLEARANCE_MIN_MM
        rings = bo.get("outline_rings_mm") or []
        near = []
        if rings:
            # 边表：(x1,y1,x2,y2, 边bbox) —— 逐边先做包围盒剪枝再算真距离
            edges = []
            for ring in rings:
                for a, b in zip(ring, ring[1:]):
                    edges.append((a[0], a[1], b[0], b[1],
                                  min(a[0], b[0]), min(a[1], b[1]),
                                  max(a[0], b[0]), max(a[1], b[1])))
            for t in pcb.traces:
                best = float("inf")
                for seg in (t.segments or []):
                    if len(seg) < 4:
                        continue
                    x1, y1, x2, y2 = seg[0], seg[1], seg[2], seg[3]
                    sx0, sx1 = (x1, x2) if x1 <= x2 else (x2, x1)
                    sy0, sy1 = (y1, y2) if y1 <= y2 else (y2, y1)
                    for ex0, ey0, ex1, ey1, bx0, by0, bx1, by1 in edges:
                        # 该边沿任一轴都远于当前最好值 → 不可能更近
                        if (bx0 - sx1 > best or sx0 - bx1 > best or
                                by0 - sy1 > best or sy0 - by1 > best):
                            continue
                        d = _seg_seg_dist((x1, y1), (x2, y2), (ex0, ey0), (ex1, ey1))
                        if d < best:
                            best = d
                    if best <= 0.0:
                        break
                if best < min_clearance:
                    near.append((t.net_name, best))
        else:
            minx, miny = bo["min_x_mm"], bo["min_y_mm"]
            maxx, maxy = bo["max_x_mm"], bo["max_y_mm"]
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
        # 2026-10-09 抽查修正：排除电源/地网——USB_GND 这类名字同时命中「usb」
        # 关键词和地网语义，地网上成串的缝合过孔不是 stub。
        stub_nets = sorted(
            net for net, cnt in via_count.items()
            if cnt >= 2 and not _is_power_or_ground_net(net)
            and any(kw.upper() in net.upper() for kw in high_speed_kw)
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
            # 2026-10-09 抽查修正：零引脚网络是解析丢针的产物（该板
            # orphan_pad_nets=77），不是「只接了一端的单端网络」；`<=1` 会把它们
            # 全数计入天线嫌疑。真正的单端网络恰好 1 个引脚。
            if len(pins) == 1 and name and not name.upper().startswith("GND"):
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
        """地平面连续性：GND 铺地应避免割裂

        2026-10-09 噪声清扫：原实现只要 pcb 存在就报一条通用科普（78/78 板全响）。
        改为看 copper_pours 证据：已有 GND 族铺铜 → 静默（连续性没有几何数据
        可算，不空喊）；完全没有 GND 铺铜（常见于简单双面板）→ 才提示。
        """
        pcb = self._pcb_data
        if not pcb:
            return []
        gnd_kw = ("GND", "AGND", "DGND", "PGND", "VSS", "EARTH")
        for p in (getattr(pcb, "copper_pours", None) or []):
            net = str(p.get("net_name") or "").upper()
            if any(kw in net for kw in gnd_kw):
                return []
        return [RuleViolation(
            rule_name="地平面连续性检查",
            description="未检测到 GND 族铺铜，建议整板铺地",
            severity=RuleSeverity.INFO,
            suggestion="关键信号(时钟/高频)下方保证完整 GND 平面。信号跨分割区需加stitching电容(10nF)桥接回流。",
            theory="高速信号的回流电流沿最小阻抗路径(紧邻信号线下方)流回源端。地平面割裂→回流绕行→环路面积↑→EMI↑。>50MHz 信号必须保证连续参考平面。",
        )]


    def _check_via_thermal_relief(self, bom_items, positions, netlist):
        """过孔热焊盘：大面积铜皮上的过孔应使用热焊盘连接

        批4 2026-10-10 审计残留：旧判据 via_count>20 就报模板文案——与过孔
        所属网络毫无关系，每块多过孔板必响。现在只统计**电源/地网络上**的
        过孔（PCBVia.net_name + _is_power_or_ground_net）；整板过孔都没有
        net 信息 → 诚实跳过（无法区分缝合孔/信号孔）；电源类网络过孔 >20
        时提示「电源网络过孔密集，建议热焊盘/多过孔并联」，一般信号过孔不报。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.vias: return []
        via_net_counts: dict[str, int] = {}
        net_info_seen = False
        for v in (pcb.vias or []):
            net = getattr(v, "net_name", "") or getattr(v, "net", "") or ""
            if not net:
                continue        # 无网络归属的过孔判不了用途，不计不报
            net_info_seen = True
            if _is_power_or_ground_net(net):
                via_net_counts[net] = via_net_counts.get(net, 0) + 1
        if not net_info_seen:
            return []          # 通道缺失（过孔无 net 属性）：诚实跳过
        pwr_total = sum(via_net_counts.values())
        if pwr_total <= 20:
            return []
        worst_net, worst_cnt = max(via_net_counts.items(), key=lambda kv: kv[1])
        return [RuleViolation(
            rule_name="过孔热焊盘检查",
            description=(f"电源/地网络过孔共 {pwr_total} 个（最密 [{worst_net}] "
                         f"{worst_cnt} 个）——电源网络过孔密集，建议热焊盘/多过孔并联"),
            severity=RuleSeverity.INFO,
            location=worst_net,
            suggestion="大电流路径单孔载流不足时多过孔并联分摊电流；大面积 GND/VCC 铜皮上的过孔用热焊盘(十字花连接)而非全连接，便于手工焊接返修。",
            theory="全连接过孔在大面积铜皮上散热极快→烙铁无法熔化焊锡→虚焊。热焊盘用 4 条细径(通常 0.25mm)限制热传导；电源网络多过孔并联可摊薄单孔电流与寄生电感。",
        )]


    def _check_hs_signal_reference_plane(self, bom_items, positions, netlist):
        """高速信号参考平面检查

        批4 2026-10-10 审计残留：
        ① 裸子串 "USB" 命中 USB_GND/USB_VBUS（电源地网被当高速信号网）——
           关键词改 _net_kw_hit 词边界（右侧放行数字后缀），对齐串扰口径；
        ② 电源/地网络排除（_is_power_or_ground_net）；
        ③ 解析器没有叠层/平面分割几何，量不出「跨分割」——本条是需确认项：
           severity 保持 WARNING，描述明确需人工确认，不写已判定语气。
        """
        pcb = self._pcb_data
        if not pcb or not pcb.traces: return []
        hs_kw = ("CLK", "USB", "HDMI", "PCIE", "SDRAM", "LVDS", "ETH")
        hs_nets = sorted({t.net_name for t in pcb.traces
                          if t.net_name
                          and not _is_power_or_ground_net(t.net_name)
                          and _net_kw_hit(t.net_name, hs_kw)})
        if hs_nets:
            return [RuleViolation(
                rule_name="高速信号参考平面检查",
                description=(f"{len(hs_nets)} 个高速网络需人工确认邻层为完整 GND "
                             f"参考平面（需确认项：解析器无叠层/平面分割几何，"
                             f"未实测跨分割）: {', '.join(hs_nets[:5])}"),
                severity=RuleSeverity.WARNING,
                location=", ".join(hs_nets[:3]),
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

        叠层按铜层数推断取典型叠层预设 STACKUP_PRESETS（.epro2 不含叠层
        数据；4 层 JLC PP 0.2104/εr≈4.6 与 impedance_recheck 复算口径一致）。
        2 层板没有参考平面，微带公式在 h≈1.565mm 下受控阻抗必不达标——
        违规降级 WARNING 并注明根因，≥4 层保持 ERROR。
        """
        from src.pcb.calculator import (
            microstrip_impedance, trace_width_for_impedance, differential_impedance,
            stackup_for_layers, infer_copper_layer_count,
        )

        pcb = self._pcb_data
        if not pcb or not pcb.traces:
            return []

        n_layers = infer_copper_layer_count(pcb)
        stackup = stackup_for_layers(n_layers)
        h_mm, er = stackup.h_signal_mm, stackup.er
        # 2 层板无参考平面：h≈1.565mm 下任何线宽都凑不出 90~100Ω，
        # 按 ERROR 报会全板飘红；降级 WARNING 说明根因。
        two_layer = n_layers <= 2

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
            # 批4 2026-10-10 审计残留：原先裸子串 kw in n，USB_GND/USB_VBUS 这类
            # 电源地网名也命中表项；统一 _net_kw_hit 词边界（与单端 single_kw
            # 的 _kw_hit 同口径，网络名允许数字后缀 USB2/ETH0）
            z_target = next((z for kw, z in diff_targets.items()
                             if any(_net_kw_hit(n, (kw,)) for n in key)), None)
            if z_target is None:
                continue
            orig = pairs[key]
            if not all(n in widths for n in orig):
                continue          # 有成员未布线，无法判定
            w = min(widths[n] for n in orig)
            if key not in gap_cache:      # 每对只算一次对内间距（几何很贵）
                gap_cache[key] = self._pair_min_gap(pcb, list(orig))
            s_mm = gap_cache[key]
            gap_estimated = False
            if not s_mm or s_mm <= 0:
                # 批4：保留 2×线宽兜底计算，但描述必须注明是估算（见下）
                s_mm = 2 * w
                gap_estimated = True
            z_actual = differential_impedance(
                microstrip_impedance(w, h_mm, er=er), s_mm, h_mm, er=er)
            # 批4：±25% 容差从两处硬编码收编 PCB.IMPEDANCE_TOLERANCE
            if abs(z_actual - z_target) <= z_target * PCB.IMPEDANCE_TOLERANCE:
                continue
            tol_pct = int(round(PCB.IMPEDANCE_TOLERANCE * 100))
            stack_note = (f"{n_layers} 层板典型叠层（{stackup.note}）"
                          if not two_layer else
                          f"{n_layers} 层板典型叠层（{stackup.note}）；"
                          "2 层板无参考平面，受控阻抗需 ≥4 层或带平面结构才可实现")
            violations.append(RuleViolation(
                rule_name="特征阻抗匹配检查",
                description=(f"差分对 [{'/'.join(orig)}]: 线宽 {w:.3f}mm / "
                             f"对内间距 {s_mm:.3f}mm → Z≈{z_actual:.0f}Ω，"
                             f"偏离目标 {z_target:.0f}Ω 超过 ±{tol_pct}%"
                             + ("（间距未量得，按 2×线宽估算，建议人工复核）"
                                if gap_estimated else "")),
                severity=RuleSeverity.WARNING if two_layer else RuleSeverity.ERROR,
                location="/".join(orig),
                suggestion=(f"调整线宽 {w:.3f}mm 与对内间距 {s_mm:.3f}mm 的组合，"
                            f"使差分阻抗 ≈{z_target:.0f}Ω（当前 {z_actual:.0f}Ω）"
                            f"。介质厚度/介电常数按 {stack_note}估算；精确控制请用 "
                            "PCB 厂商提供的叠层参数（Polar Si9000）。"),
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
            # 批4：±25% 容差收编 PCB.IMPEDANCE_TOLERANCE（与差分半区同口径）
            if abs(z0_single - 50.0) <= 50.0 * PCB.IMPEDANCE_TOLERANCE:
                continue
            tol_pct = int(round(PCB.IMPEDANCE_TOLERANCE * 100))
            w_target = trace_width_for_impedance(50.0, h_mm, er=er)
            stack_note = (f"{n_layers} 层板典型叠层（{stackup.note}）"
                          if not two_layer else
                          f"{n_layers} 层板典型叠层（{stackup.note}）；"
                          "2 层板无参考平面，50Ω 受控阻抗需 ≥4 层才可实现")
            violations.append(RuleViolation(
                rule_name="特征阻抗匹配检查",
                description=(f"网络 [{name}] 单端: 线宽 {w:.3f}mm → Z≈{z0_single:.0f}Ω，"
                             f"偏离目标 50Ω 超过 ±{tol_pct}%"),
                severity=RuleSeverity.WARNING if two_layer else RuleSeverity.ERROR,
                location=name,
                suggestion=(f"调整线宽至 {w_target:.3f}mm 使 Z₀≈50Ω"
                            f"（当前 {w:.3f}mm → {z0_single:.0f}Ω）。"
                            f"介质厚度/介电常数按 {stack_note}估算；精确控制请用 "
                            "PCB 厂商提供的叠层参数（Polar Si9000）。"),
                theory="微带线 Z₀=(87/√(εr+1.41))·ln(5.98h/(0.8w+t))。"
                       "阻抗不匹配→反射(Γ=(ZL-Z₀)/(ZL+Z₀))→过冲/振铃/EMI↑。",
            ))
        return violations
