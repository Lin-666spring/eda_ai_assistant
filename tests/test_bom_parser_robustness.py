"""BOM 解析器健壮性回归测试（验收报告 A-7/A-8）。

- A-7: 数量列坏单元格（'ABC'/'2 (盘)'/'1,000'）不得毁掉整份导入。
- A-8: 含空格/# 的英文表头（"Part Number"、"LCSC Part #"）不得被静默丢弃。
"""

import pytest

from src.bom.parser import BOMItem, BOMParser


def _write_csv(tmp_path, content: str, name: str = "bom.csv") -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8-sig")
    return str(p)


class TestBadQuantityCell:
    """A-7：坏数量单元格降级为 1，不中断导入。"""

    def test_non_numeric_quantity(self, tmp_path):
        p = _write_csv(tmp_path,
                       "位号,参数,封装,数量\nR1,10k,0603,ABC\nR2,4k7,0603,2\n")
        items = BOMParser().parse(p)
        assert len(items) == 2
        assert items[0].quantity == 1   # 'ABC' → 降级 1
        assert items[1].quantity == 2

    def test_quantity_with_unit_note(self, tmp_path):
        p = _write_csv(tmp_path, "位号,参数,数量\nC1,100nF,2 (盘)\n")
        items = BOMParser().parse(p)
        assert items[0].quantity == 2   # '2 (盘)' → 2

    def test_quantity_thousands_separator(self, tmp_path):
        p = _write_csv(tmp_path, "位号,参数,数量\nC1,100nF,\"1,000\"\n")
        items = BOMParser().parse(p)
        assert items[0].quantity == 1000

    def test_empty_quantity(self, tmp_path):
        p = _write_csv(tmp_path, "位号,参数,数量\nC1,100nF,\n")
        items = BOMParser().parse(p)
        assert items[0].quantity == 1

    def test_bomitem_direct_bad_quantity(self):
        assert BOMItem(reference="R1", value="10k", package="0603",
                       part_number="", quantity="3").quantity == 3
        assert BOMItem(reference="R2", value="10k", package="0603",
                       part_number="", quantity="XX").quantity == 1


class TestEnglishHeadersWithSpaces:
    """A-8：英文表头（空格/#）必须真正取到值。"""

    def test_part_number_column_with_space(self, tmp_path):
        p = _write_csv(tmp_path,
                       "Designator,Value,Package,Part Number,Quantity\n"
                       "R1,10k,0603,0603WAF1002T5E,1\n"
                       "C1,100nF,0402,CL05B104KB54PNC,2\n")
        items = BOMParser().parse(p)
        assert len(items) == 2
        assert items[0].part_number == "0603WAF1002T5E"
        assert items[1].part_number == "CL05B104KB54PNC"
        assert items[1].quantity == 2

    def test_lcsc_part_hash_column(self, tmp_path):
        p = _write_csv(tmp_path,
                       "Designator,LCSC Part #,Quantity\nC1,C123456,1\n")
        items = BOMParser().parse(p)
        assert items[0].part_number == "C123456"

    def test_chinese_headers_still_work(self, tmp_path):
        p = _write_csv(tmp_path, "位号,参数,封装,数量\nR1,10k,0603,3\n")
        items = BOMParser().parse(p)
        assert items[0].value == "10k"
        assert items[0].quantity == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
