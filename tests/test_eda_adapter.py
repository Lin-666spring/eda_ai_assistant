"""EDA 适配器单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.interfaces.eda_adapter import LCEDAAdapter, PCBData


@pytest.fixture
def adapter():
    return LCEDAAdapter()


@pytest.fixture
def sample_pos_path():
    return str(PROJECT_ROOT / "tests" / "sample_positions.csv")


class TestLCEDAAdapter:
    def test_tool_name(self, adapter):
        assert "立创EDA" in adapter.tool_name

    def test_get_positions(self, adapter, sample_pos_path):
        positions = adapter.get_positions(sample_pos_path)
        assert isinstance(positions, dict)
        assert len(positions) > 0

    def test_position_fields(self, adapter, sample_pos_path):
        positions = adapter.get_positions(sample_pos_path)
        first = next(iter(positions.values()))
        assert "x" in first
        assert "y" in first
        assert "rotation" in first
        assert "layer" in first
        assert "package" in first

    def test_positions_not_csv(self, adapter):
        result = adapter.get_positions("not_a_file.xlsx")
        assert result == {}

    def test_get_project_info(self, adapter):
        info = adapter.get_project_info("/fake/path")
        assert info["tool"] == adapter.tool_name
        assert ".csv" in info["supported_formats"]
