"""PCB 解析器 + 规则检查 + RAG 单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from src.pcb.models import PCBData, PCBTrace, PCBNet, PCBVia
from src.pcb.parser import (
    LCEDAJsonParser,
    LCEDAProParser,
    create_parser,
    PCBParseError,
)
from src.rules.checker import DesignRuleChecker, RuleViolation, RuleSeverity
from src.bom.parser import BOMItem
from src.constants import PCB


# ══════════════════ PCB Data Models ══════════════════

class TestPCBData:
    def test_empty(self):
        data = PCBData()
        assert data.net_count == 0
        assert data.trace_count == 0
        assert data.via_count == 0
        assert data.format == "unknown"

    def test_with_nets(self):
        data = PCBData(
            format="lceda_json",
            nets={"GND": PCBNet(name="GND", pins=["1", "2"]),
                  "VCC": PCBNet(name="VCC", pins=["1"])},
        )
        assert data.net_count == 2

    def test_get_nets_by_type(self):
        data = PCBData(
            nets={
                "VCC": PCBNet(name="VCC", pins=["1"]),
                "GND": PCBNet(name="GND", pins=["2"]),
                "SPI_CLK": PCBNet(name="SPI_CLK", pins=["3"]),
                "UART_TX": PCBNet(name="UART_TX", pins=["4"]),
            }
        )
        power, signal = data.get_nets_by_type(
            power_kw=PCB.POWER_NET_KEYWORDS,
            signal_kw=PCB.SIGNAL_NET_KEYWORDS,
        )
        assert len(power) == 2  # VCC, GND
        assert len(signal) == 2  # SPI_CLK, UART_TX (both non-power nets)


class TestPCBTrace:
    def test_basic(self):
        t = PCBTrace(net_name="GND", layer="TopLayer", width_mm=0.5)
        assert t.net_name == "GND"
        assert t.width_mm == 0.5

    def test_segments(self):
        t = PCBTrace(
            net_name="VCC", layer="TopLayer", width_mm=0.3,
            segments=[(0, 0, 10, 10), (10, 10, 20, 20)],
        )
        assert len(t.segments) == 2


# ══════════════════ LCEDA JSON Parser ══════════════════

class TestLCEDAJsonParser:
    @pytest.fixture
    def parser(self):
        return LCEDAJsonParser()

    @pytest.fixture
    def sample_path(self):
        return str(PROJECT_ROOT / "tests" / "sample_pcb.json")

    def test_parse_valid_file(self, parser, sample_path):
        data = parser.parse(sample_path)
        assert data.format == "lceda_json"
        assert data.net_count >= 4
        assert data.trace_count >= 9
        assert data.via_count >= 3
        assert "TopLayer" in data.layers

    def test_extracts_nets(self, parser, sample_path):
        data = parser.parse(sample_path)
        net_names = list(data.nets.keys())
        assert "GND" in net_names
        assert "VCC" in net_names
        assert "SPI_SCLK" in net_names

    def test_traces_have_width(self, parser, sample_path):
        data = parser.parse(sample_path)
        for t in data.traces:
            assert t.width_mm > 0
            assert t.layer in data.layers

    def test_file_not_found(self, parser):
        with pytest.raises(PCBParseError):
            parser.parse("/nonexistent/pcb.json")

    def test_unsupported_format(self, parser):
        with pytest.raises(PCBParseError):
            parser.parse(str(PROJECT_ROOT / "tests" / "sample_bom.csv"))

    def test_parse_nets_per_net(self, parser, sample_path):
        """每个网络的 pins 应该按焊盘编号归纳"""
        data = parser.parse(sample_path)
        gnd = data.nets.get("GND")
        assert gnd is not None
        assert len(gnd.pins) >= 2

    def test_trace_count_per_net(self, parser, sample_path):
        """走线统计应归入对应网络"""
        data = parser.parse(sample_path)
        gnd = data.nets.get("GND")
        assert gnd is not None
        assert gnd.trace_count >= 2


# ══════════════════ Factory Function ══════════════════

class TestCreateParser:
    def test_json_parser(self):
        p = create_parser("test.json")
        assert isinstance(p, LCEDAJsonParser)

    def test_epro_parser(self):
        p = create_parser("test.epro")
        assert isinstance(p, LCEDAProParser)

    def test_unsupported(self):
        with pytest.raises(PCBParseError):
            create_parser("test.unknown")


# ══════════════════ Design Rules with PCB Data ══════════════════

class TestSignalTraceCheck:
    @pytest.fixture
    def checker(self):
        return DesignRuleChecker()

    @pytest.fixture
    def pcb_with_signal_ok(self):
        return PCBData(
            format="lceda_json",
            layers=["TopLayer"],
            nets={
                "SPI_SCLK": PCBNet(name="SPI_SCLK", pins=["1", "2"]),
                "SPI_MISO": PCBNet(name="SPI_MISO", pins=["3", "4"]),
            },
            traces=[
                PCBTrace(net_name="SPI_SCLK", layer="TopLayer", width_mm=0.25),
                PCBTrace(net_name="SPI_MISO", layer="TopLayer", width_mm=0.3),
            ],
        )

    @pytest.fixture
    def pcb_with_signal_thin(self):
        return PCBData(
            format="lceda_json",
            layers=["TopLayer"],
            nets={"SPI_SCLK": PCBNet(name="SPI_SCLK", pins=["1", "2"])},
            traces=[
                PCBTrace(net_name="SPI_SCLK", layer="TopLayer", width_mm=0.12),
            ],
        )

    def test_signal_ok(self, checker, pcb_with_signal_ok):
        violations = checker.check_all([], {}, pcb_data=pcb_with_signal_ok)
        signal_v = [v for v in violations if "信号线" in v.rule_name]
        assert len(signal_v) == 0

    def test_signal_thin(self, checker, pcb_with_signal_thin):
        violations = checker.check_all([], {}, pcb_data=pcb_with_signal_thin)
        signal_v = [v for v in violations if "信号线" in v.rule_name]
        assert len(signal_v) >= 1
        assert signal_v[0].severity == RuleSeverity.WARNING

    def test_signal_no_pcb_data(self, checker):
        violations = checker.check_all([], {}, pcb_data=None)
        signal_v = [v for v in violations if "信号线" in v.rule_name]
        assert len(signal_v) == 0  # 无 PCB 数据时静默跳过


class TestPowerTraceCheck:
    @pytest.fixture
    def checker(self):
        return DesignRuleChecker()

    @pytest.fixture
    def pcb_with_power_ok(self):
        return PCBData(
            format="lceda_json",
            layers=["TopLayer"],
            nets={"VCC": PCBNet(name="VCC", pins=["1", "2"])},
            traces=[
                PCBTrace(net_name="VCC", layer="TopLayer", width_mm=1.0),
            ],
        )

    @pytest.fixture
    def pcb_with_power_thin(self):
        return PCBData(
            format="lceda_json",
            layers=["TopLayer"],
            nets={"VCC": PCBNet(name="VCC", pins=["1", "2"])},
            traces=[
                PCBTrace(net_name="VCC", layer="TopLayer", width_mm=0.05),  # too thin for 0.5A
            ],
        )

    def test_power_no_pcb(self, checker):
        violations = checker.check_all([], {}, pcb_data=None)
        power_v = [v for v in violations if "电源线" in v.rule_name]
        assert len(power_v) == 0

    def test_power_ok(self, checker, pcb_with_power_ok):
        violations = checker.check_all([], {}, pcb_data=pcb_with_power_ok)
        power_v = [v for v in violations if "电源线" in v.rule_name]
        assert len(power_v) == 0

    def test_power_thin(self, checker, pcb_with_power_thin):
        violations = checker.check_all([], {}, pcb_data=pcb_with_power_thin)
        power_v = [v for v in violations if "电源线" in v.rule_name]
        assert len(power_v) >= 1


class TestAnalogDigitalCheck:
    @pytest.fixture
    def checker(self):
        return DesignRuleChecker()

    def test_no_positions(self, checker):
        violations = checker.check_all([], {}, pcb_data=None)
        ad_v = [v for v in violations if "分离" in v.rule_name]
        assert len(ad_v) == 0

    def test_with_mixed_placement(self, checker):
        """模拟/数字元件间距不足时应报警"""
        bom = [
            BOMItem(reference="U1", value="", package="LQFP-48",
                    part_number="STM32F103C8T6", description="MCU"),
            BOMItem(reference="U2", value="", package="SOP-8",
                    part_number="LM358", description="运放"),
        ]
        positions = {
            "U1": {"x": 100, "y": 100, "rotation": 0, "layer": "Top"},
            "U2": {"x": 102, "y": 101, "rotation": 0, "layer": "Top"},
        }
        violations = checker.check_all(bom, positions, pcb_data=None)
        ad_v = [v for v in violations if "分离" in v.rule_name]
        assert len(ad_v) >= 1

    def test_with_separated_placement(self, checker):
        """模拟/数字元件远离时应通过"""
        bom = [
            BOMItem(reference="U1", value="", package="LQFP-48",
                    part_number="STM32F103C8T6", description="MCU"),
            BOMItem(reference="U2", value="", package="SOP-8",
                    part_number="LM358", description="运放"),
        ]
        positions = {
            "U1": {"x": 0, "y": 0, "rotation": 0, "layer": "Top"},
            "U2": {"x": 50, "y": 50, "rotation": 0, "layer": "Top"},
        }
        violations = checker.check_all(bom, positions, pcb_data=None)
        ad_v = [v for v in violations if "分离" in v.rule_name]
        assert len(ad_v) == 0


# ══════════════════ RAG Indexer/Retriever ══════════════════

class TestRAGIndexer:
    @pytest.fixture
    def indexer(self, tmp_path):
        from src.rag.indexer import RAGIndexer
        idx = RAGIndexer(persist_dir=str(tmp_path / "rag_test"))
        yield idx
        # cleanup
        import shutil
        try:
            shutil.rmtree(str(tmp_path / "rag_test"))
        except Exception:
            pass

    def test_index_text(self, indexer):
        count = indexer.index_text(
            title="测试文档",
            text="## 0603封装\n\n0603封装尺寸为1.6mm x 0.8mm。\n\n## 电阻选型\n\n贴片电阻常见精度为1%。",
            source="test",
        )
        assert count > 0
        assert indexer.chunk_count >= 2

    def test_clear(self, indexer):
        indexer.index_text("test", "some content")
        assert indexer.chunk_count > 0
        indexer.clear()
        assert indexer.chunk_count == 0

    def test_index_empty(self, indexer):
        count = indexer.index_text("empty", "")
        assert count == 0


class TestRAGRetriever:
    @pytest.fixture
    def retriever(self, tmp_path):
        from src.rag.indexer import RAGIndexer
        from src.rag.retriever import RAGRetriever

        persist = str(tmp_path / "rag_retrieve_test")
        indexer = RAGIndexer(persist_dir=persist)
        indexer.index_text(
            title="封装规格",
            text="0603封装尺寸为1.6mm x 0.8mm，0805封装尺寸为2.0mm x 1.25mm。",
        )
        indexer.index_text(
            title="电源设计",
            text="建议电源走线宽度不小于1mm，地线尽量宽以减少阻抗。",
        )
        yield RAGRetriever(persist_dir=persist)
        import shutil
        try:
            shutil.rmtree(persist)
        except Exception:
            pass

    def test_query(self, retriever):
        results = retriever.query("0603尺寸")
        assert len(results) >= 1

    def test_query_with_context(self, retriever):
        ctx = retriever.query_with_context("封装")
        assert "封装" in ctx or "0603" in ctx

    def test_query_no_results_handles_gracefully(self, retriever):
        results = retriever.query("xYzNotFound12345", top_k=2)
        assert isinstance(results, list)


# ══════════════════ Boundary / Edge Cases ══════════════════

class TestPCBParseEdgeCases:
    @pytest.fixture
    def parser(self):
        return LCEDAJsonParser()

    def test_empty_canvas(self, parser, tmp_path):
        import json
        f = tmp_path / "empty.json"
        f.write_text(json.dumps({"canvas": []}), encoding="utf-8")
        data = parser.parse(str(f))
        assert data.net_count == 0

    def test_canvas_with_unknown_shapes(self, parser, tmp_path):
        import json
        f = tmp_path / "unknown.json"
        f.write_text(json.dumps({"canvas": [
            "UNKNOWN~1~2~3~4~5",
            "TRACK~1~1~NET~0.3~0 0~10 10",
        ]}), encoding="utf-8")
        data = parser.parse(str(f))
        assert data.trace_count >= 1

    def test_canvas_mixed_nonstring(self, parser, tmp_path):
        import json
        f = tmp_path / "mixed.json"
        f.write_text(json.dumps({
            "canvas": [123, None, "TRACK~1~1~NET~0.3~0 0~10 10"]
        }), encoding="utf-8")
        data = parser.parse(str(f))
        assert data.trace_count >= 1

    def test_broken_json_file(self, parser, tmp_path):
        f = tmp_path / "broken.json"
        f.write_text("{this is not json", encoding="utf-8")
        with pytest.raises(PCBParseError):
            parser.parse(str(f))

    def test_track_non_numeric_width(self, parser, tmp_path):
        import json
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({
            "canvas": ["TRACK~1~1~NET~abc~0 0~10 10"]
        }), encoding="utf-8")
        data = parser.parse(str(f))
        assert data.traces[0].width_mm == 0.0

    def test_via_bad_coordinates(self, parser, tmp_path):
        import json
        f = tmp_path / "bad.json"
        f.write_text(json.dumps({
            "canvas": ["VIA~1~1~NET~bad_coord~0.3~0.6"]
        }), encoding="utf-8")
        data = parser.parse(str(f))
        assert data.via_count == 0

    def test_epro_not_zip(self, tmp_path):
        parser = LCEDAProParser()
        f = tmp_path / "fake.epro"
        f.write_text("not a zip file", encoding="utf-8")
        with pytest.raises(PCBParseError):
            parser.parse(str(f))


class TestCheckerEdgeCases:
    @pytest.fixture
    def checker(self):
        return DesignRuleChecker()

    def test_pcb_with_no_traces(self, checker):
        pcb = PCBData(format="lceda_json", layers=["TopLayer"],
                      nets={"VCC": PCBNet(name="VCC")})
        violations = checker.check_all([], {}, pcb_data=pcb)
        assert len(violations) == 0

    def test_power_same_net_different_widths(self, checker):
        """同网络多条走线——应检查最细那条"""
        pcb = PCBData(
            format="lceda_json", layers=["TopLayer"],
            nets={"VCC": PCBNet(name="VCC", pins=["1"])},
            traces=[
                PCBTrace(net_name="VCC", layer="TopLayer", width_mm=1.5),
                PCBTrace(net_name="VCC", layer="TopLayer", width_mm=0.05),
            ],
        )
        violations = checker.check_all([], {}, pcb_data=pcb)
        power_v = [v for v in violations if "电源线" in v.rule_name]
        assert len(power_v) >= 1  # 0.05mm too thin

    def test_analog_only_no_digital(self, checker):
        """全部模拟元件——不触发分离报警"""
        bom = [
            BOMItem(reference="U1", value="", package="SOP-8",
                    part_number="OP07", description="精密运放"),
        ]
        positions = {"U1": {"x": 0, "y": 0}}
        violations = checker.check_all(bom, positions, pcb_data=None)
        ad_v = [v for v in violations if "分离" in v.rule_name]
        assert len(ad_v) == 0
