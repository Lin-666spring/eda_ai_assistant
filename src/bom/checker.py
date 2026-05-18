"""
BOM 位号查重器
检测重复的位号，防止焊接冲突
"""

import logging
from collections import Counter
from dataclasses import dataclass

from .parser import BOMItem

logger = logging.getLogger(__name__)


@dataclass
class DuplicateInfo:
    """重复位号信息"""

    reference: str
    occurrences: list[BOMItem]  # 冲突的 BOM 条目列表


class BOMDuplicateChecker:
    """BOM 位号重复检查器"""

    def check(self, items: list[BOMItem]) -> list[DuplicateInfo]:
        ref_to_items = self._group_references(items)
        duplicates = [
            DuplicateInfo(reference=ref, occurrences=occurrences)
            for ref, occurrences in ref_to_items.items()
            if len(occurrences) > 1
        ]
        if duplicates:
            logger.warning(f"发现 {len(duplicates)} 个重复位号")
        else:
            logger.info("位号检查通过，无重复")
        return duplicates

    def check_multi_file(
        self, file_items: dict[str, list[BOMItem]]
    ) -> list[DuplicateInfo]:
        ref_to_source: dict[str, list[tuple[str, BOMItem]]] = {}
        for file_name, items in file_items.items():
            for ref, occurrences in self._group_references(items).items():
                for item in occurrences:
                    if ref not in ref_to_source:
                        ref_to_source[ref] = []
                    ref_to_source[ref].append((file_name, item))

        cross_duplicates = []
        for ref, sources in ref_to_source.items():
            if len(sources) > 1:
                conflicting_items = [item for _, item in sources]
                file_names = [file_name for file_name, _ in sources]
                cross_duplicates.append(
                    DuplicateInfo(reference=ref, occurrences=conflicting_items)
                )
                logger.warning(
                    f"跨文件重复: {ref} 出现在 {', '.join(file_names)}"
                )
        return cross_duplicates

    @staticmethod
    def _group_references(
        items: list[BOMItem],
    ) -> dict[str, list[BOMItem]]:
        ref_to_items: dict[str, list[BOMItem]] = {}
        for item in items:
            for ref in item.reference_list:
                if ref not in ref_to_items:
                    ref_to_items[ref] = []
                ref_to_items[ref].append(item)
        return ref_to_items

    def get_report(self, duplicates: list[DuplicateInfo]) -> str:
        if not duplicates:
            return "✅ BOM 位号检查通过，无重复位号。"

        lines = [
            "=" * 50,
            "        BOM 位号查重报告",
            "=" * 50,
            f"发现 {len(duplicates)} 个重复位号：",
            "-" * 50,
        ]

        for duplicate in duplicates:
            parts = [f"  🔴 {duplicate.reference} — "]
            for item in duplicate.occurrences:
                parts.append(
                    f"型号 {item.part_number} ({item.package}) "
                    f"← 位号组: {item.reference}"
                )
            lines.append(" | ".join(parts))

        lines.append("=" * 50)
        return "\n".join(lines)

    def get_reference_summary(self, items: list[BOMItem]) -> dict:
        all_refs = []
        for item in items:
            all_refs.extend(item.reference_list)

        counter = Counter(all_refs)
        prefix_counter: dict[str, int] = {}
        for ref in all_refs:
            prefix = "".join(c for c in ref if c.isalpha())
            prefix_counter[prefix] = prefix_counter.get(prefix, 0) + 1

        return {
            "total_references": len(all_refs),
            "total_unique": len(set(all_refs)),
            "duplicate_count": sum(1 for v in counter.values() if v > 1),
            "by_prefix": prefix_counter,
        }
