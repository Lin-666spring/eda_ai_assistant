"""
BOM 模块单元测试
"""

import sys
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.bom.parser import BOMParser, BOMItem
from src.bom.merger import BOMMerger, MergedBOMItem
from src.bom.validator import BOMValidator, ValidationResult
from src.bom.checker import BOMDuplicateChecker, DuplicateInfo
from src.bom.normalizer import ValueNormalizer

# 测试数据路径
TEST_DATA = Path(__file__).parent
SAMPLE_BOM = TEST_DATA / "sample_bom.csv"
SAMPLE_POS = TEST_DATA / "sample_positions.csv"


class TestBOMParser:
    """BOM 解析器测试"""

    @pytest.fixture
    def parser(self):
        return BOMParser()

    def test_parse_csv(self, parser):
        """测试 CSV 解析"""
        items = parser.parse(str(SAMPLE_BOM))
        assert len(items) == 23
        assert all(isinstance(item, BOMItem) for item in items)

    def test_parse_first_item(self, parser):
        """测试首条记录内容"""
        items = parser.parse(str(SAMPLE_BOM))
        first = items[0]
        assert first.reference == "R1"
        assert first.value == "10kΩ"
        assert first.package == "0603"
        assert first.part_number == "C25804"

    def test_reference_list(self, parser):
        """测试位号列表解析"""
        items = parser.parse(str(SAMPLE_BOM))
        assert items[0].reference_list == ["R1"]

    def test_to_dataframe(self, parser):
        """测试转回 DataFrame"""
        items = parser.parse(str(SAMPLE_BOM))
        df = parser.to_dataframe(items)
        assert len(df) == 23
        assert "位号" in df.columns

    def test_file_not_found(self, parser):
        """测试文件不存在异常"""
        with pytest.raises(FileNotFoundError):
            parser.parse("nonexistent.csv")

    def test_unsupported_format(self, parser):
        """测试不支持的格式"""
        with pytest.raises(ValueError):
            parser.parse("test.txt")


class TestBOMMerger:
    """BOM 合并器测试"""

    @pytest.fixture
    def items(self):
        parser = BOMParser()
        return parser.parse(str(SAMPLE_BOM))

    def test_merge_count(self, items):
        """测试合并后数量"""
        merger = BOMMerger()
        merged = merger.merge(items)
        assert len(merged) < len(items)  # 应减少
        assert len(merged) == 15

    def test_merge_resistor_group(self, items):
        """测试电阻合并"""
        merger = BOMMerger()
        merged = merger.merge(items)
        # 查找 10kΩ 电阻组
        r10k = next((m for m in merged if "C25804" in m.part_number), None)
        assert r10k is not None
        assert r10k.total_quantity == 3
        assert "R1" in r10k.references
        assert "R2" in r10k.references
        assert "R3" in r10k.references

    def test_merge_capacitor_group(self, items):
        """测试电容合并"""
        merger = BOMMerger()
        merged = merger.merge(items)
        c100nf = next((m for m in merged if "C1588" in m.part_number), None)
        assert c100nf is not None
        assert c100nf.total_quantity == 4
        assert all(r in c100nf.references for r in ["C1", "C2", "C3", "C6"])

    def test_merge_report(self, items):
        """测试合并报告"""
        merger = BOMMerger()
        merged = merger.merge(items)
        report = merger.get_merge_report(items, merged)
        assert "原始条目数：23" in report
        assert "合并后条目数：15" in report

    def test_value_normalization(self):
        """测试单位归一化"""
        from src.bom.normalizer import ValueNormalizer
        nv1 = ValueNormalizer.normalize("10kΩ")
        nv2 = ValueNormalizer.normalize("10K")
        assert nv1.category_key == nv2.category_key
        assert nv1.component_type == "R"


class TestBOMValidator:
    """封装校验器测试"""

    @pytest.fixture
    def items(self):
        parser = BOMParser()
        return parser.parse(str(SAMPLE_BOM))

    def test_validate_all_pass(self, items):
        """测试全部通过（正确封装）"""
        validator = BOMValidator()
        results = validator.validate(items)
        assert all(r.is_valid for r in results)

    def test_mcu_package_wrong(self):
        """测试 MCU 封装错误检测"""
        validator = BOMValidator()
        bad_item = BOMItem(
            reference="U1", value="", package="QFN-48",
            part_number="STM32F103C8T6", description="MCU",
        )
        results = validator.validate([bad_item])
        assert not results[0].is_valid
        assert "LQFP-48" in results[0].expected_package

    def test_passive_components_skip(self):
        """测试无源元件跳过校验"""
        validator = BOMValidator()
        cap = BOMItem(
            reference="C1", value="100nF", package="0603",
            part_number="C1588", description="贴片电容",
        )
        results = validator.validate([cap])
        assert results[0].is_valid  # 无源元件始终通过

    def test_validation_report(self, items):
        """测试校验报告"""
        validator = BOMValidator()
        results = validator.validate(items)
        report = validator.get_validation_report(results)
        assert "通过：23" in report


class TestBOMDuplicateChecker:
    """位号查重器测试"""

    @pytest.fixture
    def items(self):
        parser = BOMParser()
        return parser.parse(str(SAMPLE_BOM))

    def test_no_duplicates(self, items):
        """测试无重复位号"""
        checker = BOMDuplicateChecker()
        duplicates = checker.check(items)
        assert len(duplicates) == 0

    def test_has_duplicates(self):
        """测试有重复位号"""
        checker = BOMDuplicateChecker()
        dup_items = [
            BOMItem(reference="R1,R2", value="10kΩ", package="0603", part_number="C25804"),
            BOMItem(reference="R1,R3", value="1kΩ", package="0603", part_number="C21190"),
        ]
        duplicates = checker.check(dup_items)
        assert len(duplicates) == 1
        assert duplicates[0].reference == "R1"

    def test_cross_file_duplicates(self):
        """测试跨文件重复"""
        checker = BOMDuplicateChecker()
        file1 = [BOMItem(reference="R1,R2", value="10kΩ", package="0603", part_number="A")]
        file2 = [BOMItem(reference="R1,R3", value="1kΩ", package="0603", part_number="B")]
        dup = checker.check_multi_file({"board1.csv": file1, "board2.csv": file2})
        assert len(dup) == 1

    def test_summary(self, items):
        """测试统计摘要"""
        checker = BOMDuplicateChecker()
        summary = checker.get_reference_summary(items)
        assert summary["total_references"] == 23
        assert summary["duplicate_count"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
