"""
BOM 元件合并引擎
将相同型号、封装、参数的元件合并为一条记录
"""

import logging
from dataclasses import dataclass, field

from .parser import BOMItem
from .normalizer import ValueNormalizer
from ..exceptions import BOMEmptyError
from ..constants import BOM

logger = logging.getLogger(__name__)


@dataclass
class MergedBOMItem:
    """合并后的 BOM 条目"""

    part_number: str
    package: str
    value: str
    total_quantity: int
    references: list[str] = field(default_factory=list)
    description: str = ""
    manufacturer: str = ""

    @property
    def reference_str(self) -> str:
        """合并后的位号字符串"""
        return ", ".join(self.references)


class BOMMerger:
    """BOM 同类元件合并引擎"""

    def __init__(self, tolerance: float = BOM.DEFAULT_MERGE_TOLERANCE):
        self.tolerance = tolerance

    def merge(self, items: list[BOMItem]) -> list[MergedBOMItem]:
        """
        合并同类元件。

        合并条件：
        1. 型号（part_number）完全一致
        2. 封装（package）完全一致
        3. 参数值在容差范围内（通过 ValueNormalizer 判断）

        Raises:
            BOMEmptyError: 输入列表为空
        """
        if not items:
            raise BOMEmptyError("无法合并空的 BOM 列表")

        groups: dict[tuple[str, str, str], MergedBOMItem] = {}

        for item in items:
            key = self._group_key(item)

            if key in groups:
                existing = groups[key]
                existing.total_quantity += item.quantity
                existing.references.extend(item.reference_list)
            else:
                groups[key] = MergedBOMItem(
                    part_number=item.part_number,
                    package=item.package,
                    value=item.value,
                    total_quantity=item.quantity,
                    references=item.reference_list.copy(),
                    description=item.description,
                    manufacturer=item.manufacturer,
                )

        result = sorted(
            groups.values(),
            key=lambda merged: (merged.part_number, merged.package),
        )
        logger.info(
            "合并完成：%d 条 → %d 组（精简 %d 条）",
            len(items), len(result), len(items) - len(result),
        )
        return result

    def merge_with_ai_suggestion(
        self,
        items: list[BOMItem],
        ai_suggestion: list[dict],
    ) -> list[MergedBOMItem]:
        """
        根据 AI 建议合并（AI 识别出合并候选组）。

        TODO: 根据 AI 建议进一步合并（如将 10kΩ → 10K 识别为同一元件）
        """
        return self.merge(items)

    # ── 内部方法 ──

    def _group_key(self, item: BOMItem) -> tuple[str, str, str]:
        """生成合并分组键：型号、封装、归一化参数值"""
        normalized = ValueNormalizer.normalize(item.value)
        return (item.part_number, item.package, normalized.category_key)

    # ── 报告生成 ──

    def get_merge_report(
        self, original: list[BOMItem], merged: list[MergedBOMItem]
    ) -> str:
        """生成合并报告文本"""
        if not original:
            return f"{BOM.REPORT_DOUBLE_SEP}\n  无 BOM 数据可合并\n{BOM.REPORT_DOUBLE_SEP}"

        reduction = len(original) - len(merged)
        ratio = reduction / len(original) * 100

        lines = [
            BOM.REPORT_DOUBLE_SEP,
            "          BOM 合并报告",
            BOM.REPORT_DOUBLE_SEP,
            f"原始条目数：{len(original)}",
            f"合并后条目数：{len(merged)}",
            f"精简条目数：{reduction}",
            f"精简比例：{ratio:.1f}%",
            BOM.REPORT_SEPARATOR,
        ]

        for item in merged:
            if len(item.references) > 1:
                lines.append(
                    f"📦 {item.part_number} ({item.package}) "
                    f"×{item.total_quantity} → 位号: {item.reference_str}"
                )

        lines.append(BOM.REPORT_DOUBLE_SEP)
        return "\n".join(lines)
