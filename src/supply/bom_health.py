"""
BOM 健康检查引擎 — 库存、生命周期、替代料推荐、成本估算。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..bom.parser import BOMItem
from ..constants import SUPPLY
from .lcsc_client import ComponentInfo, LcscSearchClient

logger = logging.getLogger(__name__)


@dataclass
class BOMHealthReport:
    """BOM 健康检查报告"""
    total_items: int = 0
    in_stock_count: int = 0
    out_of_stock: list[dict] = field(default_factory=list)
    low_stock: list[dict] = field(default_factory=list)
    lifecycle_warnings: list[dict] = field(default_factory=list)
    alternatives: dict[str, list[dict]] = field(default_factory=dict)
    total_cost_estimate: float = 0.0
    not_found: list[str] = field(default_factory=list)

    @property
    def health_score(self) -> float:
        """BOM 健康分 (0-100)。"""
        if not self.total_items:
            return 100.0
        deductions = (
            len(self.out_of_stock) * 20
            + len(self.low_stock) * 5
            + len(self.lifecycle_warnings) * 10
            + len(self.not_found) * 2
        )
        return max(0.0, 100.0 - deductions)


class BOMHealthChecker:
    """BOM 健康检查引擎。

    对整张 BOM 做: 库存检查 / 生命周期预警 / 替代料推荐 / 成本估算。
    """

    def __init__(self, client: LcscSearchClient):
        self._client = client

    def check(self, bom_items: list[BOMItem]) -> BOMHealthReport:
        """全面健康检查。"""
        report = BOMHealthReport(total_items=len(bom_items))

        for item in bom_items:
            part = item.part_number
            if not part or part in ("N/A", "Unknown"):
                report.not_found.append(item.reference)
                continue

            info = self._client.is_available(part)
            if info is None:
                report.not_found.append(item.reference)
                continue

            if not info.in_stock:
                report.out_of_stock.append({
                    "reference": item.reference,
                    "part": part,
                    "package": item.package,
                    "lcsc_part": info.lcsc_part,
                })
            elif info.stock < 100:
                report.low_stock.append({
                    "reference": item.reference,
                    "part": part,
                    "stock": info.stock,
                })
            else:
                report.in_stock_count += 1

            # 生命周期检测
            lifecycle = self._check_lifecycle(part, info)
            if lifecycle:
                report.lifecycle_warnings.append(lifecycle)

            # 成本累计
            report.total_cost_estimate += info.min_price

        # 替代料推荐（仅对缺货项）
        for missing in report.out_of_stock:
            alts = self._recommend_alternatives(
                missing["part"], missing["package"]
            )
            if alts:
                report.alternatives[missing["part"]] = alts

        return report

    def recommend_alternatives(
        self, part_number: str, package: str = ""
    ) -> list[dict]:
        """推荐替代料。"""
        return self._recommend_alternatives(part_number, package)

    def estimate_total_cost(
        self, bom_items: list[BOMItem], quantity: int = 1
    ) -> float:
        """估算整张 BOM 采购成本。"""
        total = 0.0
        for item in bom_items:
            if not item.part_number:
                continue
            info = self._client.is_available(item.part_number)
            if info and info.min_price > 0:
                total += info.min_price * item.quantity * quantity
        return round(total, 2)

    # ── Internal ──

    def _recommend_alternatives(
        self, part_number: str, package: str
    ) -> list[dict]:
        """搜索替代料: 同封装 + 相近参数。"""
        try:
            result = self._client.search_by_part(
                package if package else part_number
            )
        except Exception:
            return []
        alts = []
        for item in result.items:
            if item.mfr_part == part_number:
                continue
            if package and item.package != package:
                continue
            if item.in_stock:
                alts.append({
                    "lcsc_part": item.lcsc_part,
                    "mfr_part": item.mfr_part,
                    "manufacturer": item.manufacturer,
                    "package": item.package,
                    "stock": item.stock,
                    "price": item.price_display,
                })
            if len(alts) >= SUPPLY.ALT_MAX_RECOMMEND:
                break
        return alts

    def _check_lifecycle(
        self, part_number: str, info: ComponentInfo
    ) -> Optional[dict]:
        """检测生命周期风险。"""
        text = f"{info.description} {info.stock_text}".lower()
        for kw in SUPPLY.EOL_KEYWORDS:
            if kw.lower() in text:
                return {
                    "part": part_number,
                    "lcsc_part": info.lcsc_part,
                    "warning": f"疑似 {kw} — 请核实生命周期状态",
                }
        return None

    # ── Report formatting ──

    @staticmethod
    def format_report(report: BOMHealthReport) -> str:
        """生成可读的健康检查报告。"""
        lines = [
            "=" * 58,
            "           BOM 健康检查报告",
            "=" * 58,
            f"  总物料: {report.total_items}  有货: {report.in_stock_count}  "
            f"缺货: {len(report.out_of_stock)}  低库存: {len(report.low_stock)}",
            f"  健康分: {report.health_score:.0f}/100",
            f"  估算单价成本: ¥{report.total_cost_estimate:.2f}",
        ]

        if report.not_found:
            lines.append("-" * 58)
            lines.append(f"  未查询到 ({len(report.not_found)} 项):")
            for ref in report.not_found[:10]:
                lines.append(f"    • {ref}")
            if len(report.not_found) > 10:
                lines.append(f"    ... 等 {len(report.not_found) - 10} 项")

        if report.out_of_stock:
            lines.append("-" * 58)
            lines.append(f"  缺货 ({len(report.out_of_stock)} 项):")
            for m in report.out_of_stock:
                alts = report.alternatives.get(m["part"], [])
                alt_str = f"  → 替代: {alts[0]['lcsc_part']}" if alts else ""
                lines.append(
                    f"    ✗ {m['reference']}  {m['part']} ({m['package']}){alt_str}"
                )

        if report.low_stock:
            lines.append("-" * 58)
            lines.append(f"  低库存 (<100) ({len(report.low_stock)} 项):")
            for m in report.low_stock:
                lines.append(f"    ⚠ {m['reference']}  {m['part']}  剩{m['stock']}件")

        if report.lifecycle_warnings:
            lines.append("-" * 58)
            lines.append(f"  生命周期预警 ({len(report.lifecycle_warnings)} 项):")
            for w in report.lifecycle_warnings:
                lines.append(f"    ⚡ {w['part']}: {w['warning']}")

        if report.total_cost_estimate > 0:
            lines.append("-" * 58)
            lines.append(f"  单价估值: ¥{report.total_cost_estimate:.2f}")

        lines.append("=" * 58)
        return "\n".join(lines)
