"""PCB 设计规则检查 — facade（P1-6 阶段B 拆包后入口）。

规则实现按域拆在 bom_rules / geometry_rules / layout_rules 三个 mixin，
常量与辅助在 base.py；本类只保留生命周期（_rules 注册、check_all）、
netlist 归一与热力图。规则名字符串全部未动 —— 覆盖率/抽查/热力图
都按名字匹配。
"""

import logging
import math
import re
from typing import Optional
from ..constants import PCB
from ..pcb.models import PCBData

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
    group_violations_by_component,
    rule_kind,
)

logger = logging.getLogger(__name__)

from .bom_rules import BomRulesMixin
from .geometry_rules import GeometryRulesMixin
from .layout_rules import LayoutRulesMixin


class DesignRuleChecker(BomRulesMixin, GeometryRulesMixin, LayoutRulesMixin):
    """组合三个规则域的 mixin；_check_ 自动注册机制不变（__init__ 里
    sorted(dir(self)) 按名收集，mixin 方法都会出现在 self 上）。"""


    # ═══ Init + orchestration ═══

    def __init__(self):
        self._pcb_data: Optional[PCBData] = None
        self._positions: Optional[dict] = None
        # 每条规则抛出的异常（{rule, error}）——check_all 不再静默吞掉规则 bug，
        # 调用方/实验脚本可以据此把「规则异常」当红灯（见 audit-findings.md）。
        self.rule_errors: list[dict] = []
        self._rules = [getattr(self, name) for name in sorted(dir(self)) if name.startswith('_check_')]


    @staticmethod
    def _net_pins(net_value) -> list[str]:
        """规整一条网络的引脚表示：容忍 [pins] 列表或带 .pins 的对象。"""
        if isinstance(net_value, (list, tuple, set)):
            return [str(p) for p in net_value]
        pins = getattr(net_value, "pins", None)
        return [str(p) for p in (pins or [])]


    @staticmethod
    def normalize_netlist(netlist, pcb_data=None) -> dict:
        """把网络表归一化成 {网络名: ["U1.12", ...]}。

        软件的 CommandContext.netlist 与离线实验脚本都传 dict，但历史上
        controller 传的是空 list、且全项目从没给它赋过值，导致「未连接引脚」
        「上下拉电阻」两条规则在产品里恒不触发、而覆盖率实验里却有输出 ——
        实验与产品口径就此分裂。这里统一兜底：netlist 为空时从 pcb_data.nets 反推。
        """
        if isinstance(netlist, dict) and netlist:
            return netlist
        nets = getattr(pcb_data, "nets", None) if pcb_data is not None else None
        if nets:
            derived = {name: list(getattr(n, "pins", []) or []) for name, n in nets.items()}
            derived = {k: v for k, v in derived.items() if v}
            if derived:
                return derived
        return netlist if isinstance(netlist, dict) else {}


    def check_all(self, bom_items, positions=None, netlist=None, pcb_data=None):
        self._pcb_data = pcb_data
        self._positions = positions
        netlist = self.normalize_netlist(netlist, pcb_data)
        violations = []
        self.rule_errors = []
        for rule_func in self._rules:
            try:
                result = rule_func(bom_items, positions, netlist)
                if result: violations.extend(result)
            except Exception as e:
                self.rule_errors.append({
                    "rule": rule_func.__name__,
                    "error": f"{type(e).__name__}: {e}",
                })
                logger.warning(f"规则检查异常 ({rule_func.__name__}): {e}")
        if self.rule_errors:
            logger.warning(
                "规则检查有 %d 条规则抛异常: %s",
                len(self.rule_errors),
                ", ".join(err["rule"] for err in self.rule_errors),
            )
        self._coordinatize(violations)
        logger.info(f"规则检查完成: 发现 {len(violations)} 项违规")
        return violations

    def _coordinatize(self, violations):
        """违规坐标化：把 location 里的位号解析成板面坐标，写回 ``v.coords``。

        位置来源与热力图同一优先级（PCB > 坐标文件），位号→坐标的口径也
        复用同一段（``_violation_xy``），保证标记层与热力图永远指向同一处。
        没有位置数据时全部留空 —— 调用方按「未定位」处理，不算错误。
        """
        pos_source, _ = self._resolve_positions()
        if not violations or not pos_source:
            return
        ref_to_pos = self._extract_xy(pos_source)
        for v in violations:
            pts = self._violation_xy(v, ref_to_pos)
            if pts:
                v.coords = list(dict.fromkeys(pts))   # 保序去重（同一位置只标一次）

    # 热力图网格边长上下限（P1-6 阶段B：拆包脚本曾漏掉类级赋值，热力图测试抓回）
    DEFAULT_GRID_MM = 5.0
    MIN_GRID_MM = 0.5
    MAX_GRID_MM = 200.0

    @classmethod
    def _normalize_grid_size(cls, grid_size_mm) -> float:
        """网格边长容错：非法/非正值回落默认，并夹到 [0.5, 200] mm（防除零）。"""
        try:
            g = float(grid_size_mm)
        except (TypeError, ValueError):
            return cls.DEFAULT_GRID_MM
        if not math.isfinite(g) or g <= 0:
            return cls.DEFAULT_GRID_MM
        return max(cls.MIN_GRID_MM, min(cls.MAX_GRID_MM, g))


    def _resolve_positions(self, positions=None) -> tuple[dict, str]:
        """挑一份可用的「位号 → 坐标」，返回 (positions, 来源标记)。"""
        pcb_positions = getattr(self._pcb_data, "component_positions", None) if self._pcb_data else None
        if pcb_positions:
            return pcb_positions, "pcb"
        for candidate in (positions, self._positions):
            if candidate:
                return candidate, "positions"
        return {}, ""


    @staticmethod
    def _extract_xy(positions: dict) -> dict[str, tuple[float, float]]:
        """把各种坐标写法归一化成 {大写位号: (x, y)}，无法解析的条目跳过。"""
        ref_to_pos: dict[str, tuple[float, float]] = {}
        for ref, pos in positions.items():
            try:
                if isinstance(pos, dict):
                    px, py = pos.get("x"), pos.get("y")
                elif isinstance(pos, (tuple, list)) and len(pos) >= 2:
                    px, py = pos[0], pos[1]
                else:
                    continue
                px, py = float(px), float(py)
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(px) and math.isfinite(py)):
                continue
            ref_to_pos[str(ref).upper()] = (px, py)
        return ref_to_pos

    _REF_TOKEN_RE = re.compile(r'[A-Z]+\d+')

    @classmethod
    def _violation_xy(cls, v, ref_to_pos: dict) -> list[tuple[float, float]]:
        """一条违规 → 坐标点列表：location 抠位号 → 查表，查不到的位号跳过。

        不去重 —— 热力图按「一位号一格」计数（一违规可计多格），
        ``_coordinatize`` 存入 v.coords 时才做保序去重。
        """
        if not v.location or not ref_to_pos:
            return []
        return [ref_to_pos[ref] for ref in cls._REF_TOKEN_RE.findall(v.location.upper())
                if ref in ref_to_pos]


    def build_heatmap(self, violations, grid_size_mm=5.0, positions=None) -> dict:
        """违规 → 坐标网格，返回 ECharts 数据 + 元信息（前端据此显示单位/来源）。

        Returns:
            {
              "data": [[bx, by, count], ...],   # 空列表 = 没有可画的东西
              "grid_size_mm": 5.0,
              "source": "pcb" | "positions" | "",   # "" = 完全没有位置数据
              "x_min": float, "y_min": float,       # 网格原点(mm)，用于 tooltip 还原真实坐标
              "violation_count": int,               # 本轮违规条数
              "mapped": int,                        # 真正落进网格的计数（一违规可计多格）
            }
        """
        g = self._normalize_grid_size(grid_size_mm)
        pos_source, source = self._resolve_positions(positions)
        meta = {
            "data": [],
            "grid_size_mm": g,
            "source": source,
            "violation_count": len(violations or []),
            "mapped": 0,
        }

        ref_to_pos = self._extract_xy(pos_source) if pos_source else {}
        if not violations or not ref_to_pos:
            return meta

        xs = [p[0] for p in ref_to_pos.values()]
        ys = [p[1] for p in ref_to_pos.values()]
        x_min, y_min = min(xs) - g, min(ys) - g
        meta["x_min"], meta["y_min"] = x_min, y_min

        grid: dict[tuple[int, int], int] = {}
        for v in violations:
            for pos in self._violation_xy(v, ref_to_pos):
                bx = int((pos[0] - x_min) / g)
                by = int((pos[1] - y_min) / g)
                key = (bx, by)
                grid[key] = grid.get(key, 0) + 1

        meta["data"] = [[bx, by, cnt] for (bx, by), cnt in grid.items()]
        meta["mapped"] = sum(grid.values())
        return meta


    def get_heatmap_data(self, violations, grid_size_mm=5.0, positions=None):
        """兼容旧调用：只取 ``build_heatmap`` 的 [[x_bin, y_bin, count], ...] 部分。"""
        return self.build_heatmap(violations, grid_size_mm, positions)["data"]


    def get_report(self, violations):
        if not violations:
            return "设计规则检查通过，未发现违规项。"
        lines = ["=" * 55, "          PCB 设计规则检查报告", "=" * 55]
        for sev in (RuleSeverity.ERROR, RuleSeverity.WARNING, RuleSeverity.INFO):
            items = [v for v in violations if v.severity == sev]
            if not items: continue
            mark = {"error": "[错误]", "warning": "[警告]", "info": "[提示]"}[sev.value]
            lines.append(f"\n【{sev.value.upper()}】{mark} {len(items)} 项")
            for v in items:
                lines.append(f"  • [{v.rule_name}] {v.description}")
                if v.location: lines.append(f"    位置: {v.location}")
                if v.coords:
                    pts = ", ".join(f"({x:.2f}, {y:.2f})" for x, y in v.coords)
                    lines.append(f"    坐标: {pts} mm")
                if v.suggestion: lines.append(f"    建议: {v.suggestion}")
                if v.theory: lines.append(f"    理论: {v.theory}")
        lines.append("\n" + "=" * 55)
        return "\n".join(lines)
