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
                PCBTrace(net_name="SPI_SCLK", layer="TopLayer", width_mm=0.08),
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

# P1-21 验收配套（2026-10-24）：indexer 移除嵌入失败回退后，单元测试不得
# 依赖外网嵌入 API（无 SILICONFLOW_API_KEY 时 401、有 Key 时烧配额且结果
# 不可复现）。用确定性的「ASCII 词 + CJK 字符 bigram」词袋向量代替，保留
# 「文本重叠多 → 更相近」的语义，检索类断言不受影响。
class _FakeBagEmbed:
    DIM = 256

    def embed(self, texts):
        import hashlib
        import math
        import re

        out = []
        for t in texts:
            vec = [0.0] * self.DIM
            tokens = re.findall(r"[A-Za-z0-9.]+", t)
            compact = re.sub(r"\s", "", t)
            tokens += [compact[i : i + 2] for i in range(len(compact) - 1)]
            for tok in tokens:
                h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
                vec[h % self.DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


@pytest.fixture(autouse=True)
def _offline_embedding(monkeypatch):
    import src.rag.indexer as indexer_mod

    monkeypatch.setattr(
        indexer_mod, "_SiliconFlowEmbedding", lambda *a, **k: _FakeBagEmbed()
    )


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
        # INFO-level violations about copper pours and testpoints are expected
        # even when no traces exist — they're informational hints for the designer
        errors_and_warnings = [v for v in violations if v.severity != RuleSeverity.INFO]
        assert len(errors_and_warnings) == 0

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


# ══════════════════ RAG Integration ══════════════════


class TestRAGIntegration:
    """RAG 知识库集成测试 — 验证 index_directory、query_knowledge_base 等"""

    @pytest.fixture
    def controller(self):
        """Create a controller without LLM (no API key needed for RAG queries)"""
        from src.core.controller import AppController
        return AppController(api_key=None)

    def test_ensure_rag_indexed_with_md_files(self, tmp_path):
        """index_directory 正确索引目录中的 .md 文件"""
        from src.rag.indexer import RAGIndexer

        rag_dir = tmp_path / "rag_test"
        rag_dir.mkdir()
        test_file = rag_dir / "test_knowledge.md"
        test_file.write_text("## 测试章节\n\n0603封装尺寸为1.6mm x 0.8mm。", encoding="utf-8")

        indexer = RAGIndexer(persist_dir=str(rag_dir))
        stats = indexer.index_directory(str(rag_dir))
        assert stats["indexed"] >= 1
        assert stats["errors"] == []
        assert indexer.chunk_count > 0

    def test_ensure_rag_indexed_skip_unchanged(self, tmp_path):
        """增量索引：未变更文件跳过"""
        from src.rag.indexer import RAGIndexer

        rag_dir = tmp_path / "rag_incr"
        rag_dir.mkdir()
        test_file = rag_dir / "data.md"
        test_file.write_text("## 章节\n\n测试内容。", encoding="utf-8")

        indexer = RAGIndexer(persist_dir=str(rag_dir))
        stats1 = indexer.index_directory(str(rag_dir))
        assert stats1["indexed"] >= 1

        stats2 = indexer.index_directory(str(rag_dir))
        assert stats2["skipped"] >= 1  # 第二轮应跳过
        assert stats2["indexed"] == 0

    def test_ensure_rag_indexed_manifest_cleanup(self, tmp_path):
        """manifest 清理：已删除文件的条目被移除"""
        from src.rag.indexer import RAGIndexer

        rag_dir = tmp_path / "rag_clean"
        rag_dir.mkdir()
        f1 = rag_dir / "keep.md"
        f2 = rag_dir / "delete_me.md"
        f1.write_text("## K1\n\n保留。", encoding="utf-8")
        f2.write_text("## K2\n\n删除。", encoding="utf-8")

        indexer = RAGIndexer(persist_dir=str(rag_dir))
        indexer.index_directory(str(rag_dir))

        # 删除 f2
        import os
        f2.unlink()
        stats = indexer.index_directory(str(rag_dir))

        assert stats["indexed"] == 0  # 无新文件
        assert stats["skipped"] >= 1  # f1 跳过
        # 检查 manifest 中无 delete_me.md
        manifest_path = rag_dir / ".index_manifest.json"
        import json
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "delete_me.md" not in manifest
        assert "keep.md" in manifest

    def test_query_knowledge_base_empty(self, controller):
        """空查询返回帮助文本"""
        result = controller.query_knowledge_base("")
        assert "知识库" in result
        assert "IPC" in result or "DDR" in result or "查询" in result

    def test_query_knowledge_base_with_query(self, controller, tmp_path):
        """带查询参数返回检索结果——使用独立索引"""
        from src.rag.indexer import RAGIndexer
        from src.rag.retriever import RAGRetriever

        rag_dir = tmp_path / "rag_ctrl_test"
        rag_dir.mkdir()
        indexer = RAGIndexer(persist_dir=str(rag_dir))
        indexer.index_text(
            title="封装手册",
            text="## 0603\n\n0603封装尺寸为1.6mm x 0.8mm，功率1/10W。\n\n## 0805\n\n0805封装尺寸为2.0mm x 1.25mm。",
        )

        retriever = RAGRetriever(persist_dir=str(rag_dir))
        results = retriever.query("0603尺寸")
        assert len(results) >= 1
        # 至少一个结果包含关键内容
        content_found = any("0603" in r["content"] or "0603" in r["title"] for r in results)
        assert content_found, f"查询 0603 尺寸应返回相关结果，但得到: {results}"

    def test_query_knowledge_base_not_found(self, tmp_path):
        """查询无匹配内容返回友好提示"""
        from src.rag.indexer import RAGIndexer
        from src.rag.retriever import RAGRetriever

        rag_dir = tmp_path / "rag_nomatch"
        rag_dir.mkdir()
        indexer = RAGIndexer(persist_dir=str(rag_dir))
        indexer.index_text("测试", "## 章节\n\n这是一段测试内容。")

        retriever = RAGRetriever(persist_dir=str(rag_dir))
        ctx = retriever.query_with_context("XYZNotFound99999999")
        # query_with_context 应返回字符串
        assert isinstance(ctx, str)


# ══════════════════ 走线类规则阈值校准（2026-09，76 个真实 .epro2） ══════════════════
# 度量与分布：scripts/calibrate_trace_thresholds.py
#             experiment_results/trace_threshold_calibration/report.txt

def _outline(minx=0.0, miny=0.0, w=50.0, h=50.0, source="outline"):
    return {
        "width_mm": w, "height_mm": h,
        "min_x_mm": minx, "min_y_mm": miny,
        "max_x_mm": minx + w, "max_y_mm": miny + h,
        "shape": "rectangle", "source": source,
    }


class TestCalibratedTraceRules:
    """锁住校准后的走线类阈值，防止无意回退。"""

    @pytest.fixture
    def checker(self):
        return DesignRuleChecker()

    # ── 信号线宽：绝对工艺下限 + 本板主流线宽（上下文感知） ──

    @staticmethod
    def _width_pcb(widths):
        return PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[
                PCBTrace(net_name=f"N{i}", layer="TopLayer", width_mm=w,
                         segments=[(i, 0, i + 1, 0)])
                for i, w in enumerate(widths)
            ],
        )

    def test_signal_width_below_process_floor_fires(self, checker):
        pcb = self._width_pcb([PCB.SIGNAL_TRACE_ABS_MIN_WIDTH_MM - 0.02])
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "信号线宽度" in x.rule_name]
        assert len(v) == 1

    def test_signal_width_neckdown_within_net_ok(self, checker):
        # 2026-10-09 噪声清扫：删除 60% 主流线宽相对条款——焊盘颈口是标准做法。
        # 本板主流 10mil(0.254)，某条网络内部混用 5mil(0.127) 细段 = 颈口，不报
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[
                PCBTrace(net_name="N0", layer="TopLayer", width_mm=0.254,
                         segments=[(0, 0, 1, 0)]),
                PCBTrace(net_name="N1", layer="TopLayer", width_mm=0.254,
                         segments=[(1, 0, 2, 0)]),
                PCBTrace(net_name="N2", layer="TopLayer", width_mm=0.127,
                         segments=[(2, 0, 3, 0)]),
                PCBTrace(net_name="N2", layer="TopLayer", width_mm=0.254,
                         segments=[(3, 0, 4, 0)]),
            ],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "信号线宽度" in x.rule_name]
        assert v == []

    def test_signal_width_uniformly_thin_net_ok(self, checker):
        # 2026-09-24：整条网络统一选细（如阻抗控制网络）属设计意图，不判误设
        pcb = self._width_pcb([0.254, 0.254, 0.254, 0.127])
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "信号线宽度" in x.rule_name]
        assert v == []

    def test_signal_width_fine_process_board_ok(self, checker):
        # 整板统一 4mil(0.1016)：高于工艺下限，且无相对异常 → 不应误报
        pcb = self._width_pcb([0.1016] * 5)
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "信号线宽度" in x.rule_name]
        assert v == []

    # ── 过孔密度：只判定高速网络，电源/地缝合孔不算 ──

    def test_via_density_ignores_power_net(self, checker):
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[PCBTrace(net_name="GND", layer="TopLayer", width_mm=0.3,
                             segments=[(0, 0, 1, 0)])],
            vias=[PCBVia(position=(i, 0), drill_mm=0.3, pad_mm=0.6,
                         from_layer="TopLayer", to_layer="BottomLayer", net_name="GND")
                  for i in range(50)],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "过孔密度" in x.rule_name]
        assert v == []

    def test_via_density_flags_high_speed_net(self, checker):
        n = PCB.VIA_DENSITY_MAX_PER_NET
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[PCBTrace(net_name="DDR_CLK", layer="TopLayer", width_mm=0.2,
                             segments=[(0, 0, 1, 0)])],
            vias=[PCBVia(position=(i, 0), drill_mm=0.3, pad_mm=0.6,
                         from_layer="TopLayer", to_layer="BottomLayer", net_name="DDR_CLK")
                  for i in range(n)],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "过孔密度" in x.rule_name]
        assert len(v) == 1

    # ── 板边间距：按真实板框几何算；铜包围盒时无判定意义 ──

    def test_edge_clearance_uses_real_outline(self, checker):
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            board_outline=_outline(0, 0, 50, 50),
            traces=[PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                             segments=[(0.1, 25, 10, 25)])],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "板边间距" in x.rule_name]
        assert len(v) == 1

    def test_edge_clearance_ok_when_far(self, checker):
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            board_outline=_outline(0, 0, 50, 50),
            traces=[PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                             segments=[(10, 25, 30, 25)])],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "板边间距" in x.rule_name]
        assert v == []

    def test_edge_clearance_skipped_for_copper_bbox(self, checker):
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            board_outline=_outline(0, 0, 50, 50, source="copper"),
            traces=[PCBTrace(net_name="SIG", layer="TopLayer", width_mm=0.2,
                             segments=[(0.0, 25, 10, 25)])],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "板边间距" in x.rule_name]
        assert v == []

    # ── 差分对：用工程 NET 规则 (ground truth)，不靠名字猜 ──

    @staticmethod
    def _pair_pcb(mismatch):
        return PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            differential_pairs=[
                {"net": "USB_DP", "differential": "DP1", "equal_length_group": None},
                {"net": "USB_DM", "differential": "DP1", "equal_length_group": None},
            ],
            traces=[
                PCBTrace(net_name="USB_DP", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0, 10, 0)]),
                PCBTrace(net_name="USB_DM", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0.4, 10 + mismatch, 0.4)]),
            ],
        )

    def test_diff_pair_length_within_tolerance_ok(self, checker):
        v = [x for x in checker.check_all([], {}, pcb_data=self._pair_pcb(0.1))
             if "差分对等长" in x.rule_name]
        assert v == []

    def test_diff_pair_length_exceeds_tolerance_fires(self, checker):
        # 2026-09-24：门限由「>0.5mm 一刀切」改为「≥2mm 或 ≥10% 组内平均长」，
        # 故用 2.5mm 失配触发（10mm 走线，2.5mm 同时满足两条量则）
        pcb = self._pair_pcb(2.5)
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "差分对等长" in x.rule_name]
        assert len(v) == 1

    def test_diff_pair_small_skew_ok(self, checker):
        # USB2.0 位周期 2083ps（≈3.25mm），0.7mm 失配 ≈4.7ps，属正常范围
        pcb = self._pair_pcb(PCB.DIFF_PAIR_MAX_SKEW_MM + 0.2)
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "差分对等长" in x.rule_name]
        assert v == []

    @staticmethod
    def _spacing_pcb(gap):
        return PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            differential_pairs=[
                {"net": "USB_DP", "differential": "DP1", "equal_length_group": None},
                {"net": "USB_DM", "differential": "DP1", "equal_length_group": None},
            ],
            traces=[
                PCBTrace(net_name="USB_DP", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0, 10, 0)]),
                PCBTrace(net_name="USB_DM", layer="TopLayer", width_mm=0.2,
                         segments=[(0, gap, 10, gap)]),
            ],
        )

    def test_diff_pair_spacing_loose_coupling_fires(self, checker):
        pcb = self._spacing_pcb(1.0)  # 5W > 3W
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "差分对间距" in x.rule_name]
        assert len(v) == 1

    def test_diff_pair_spacing_tight_coupling_ok(self, checker):
        v = [x for x in checker.check_all([], {}, pcb_data=self._spacing_pcb(0.4))
             if "差分对间距" in x.rule_name]
        assert v == []

    # ── 3W 串扰：交叉/短平行不算，长平行且间距 <3W 才算 ──

    def test_crosstalk_parallel_close_run_fires(self, checker):
        # 2026-09-24：3W 只对高速/时钟/差分网络有意义，故用高速网络名
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[
                PCBTrace(net_name="USB_DP", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0, 20, 0)]),
                PCBTrace(net_name="USB_DM", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0.4, 20, 0.4)]),  # 2W 间距、平行 20mm
            ],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "串扰" in x.rule_name]
        assert len(v) == 1

    def test_crosstalk_low_speed_pair_ok(self, checker):
        """按键/GPIO 这类低速线对不套 3W 准则（抽样里 5/5 都是这类误报）。"""
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[
                PCBTrace(net_name="KEY_IN", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0, 20, 0)]),
                PCBTrace(net_name="GPIO1", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0.4, 20, 0.4)]),
            ],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "串扰" in x.rule_name]
        assert v == []

    def test_crosstalk_crossing_traces_ok(self, checker):
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[
                PCBTrace(net_name="USB_DP", layer="TopLayer", width_mm=0.2,
                         segments=[(-10, 0, 10, 0)]),
                PCBTrace(net_name="USB_DM", layer="TopLayer", width_mm=0.2,
                         segments=[(0, -10, 0, 10)]),  # 垂直交叉
            ],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "串扰" in x.rule_name]
        assert v == []

    def test_crosstalk_short_parallel_run_ok(self, checker):
        pcb = PCBData(
            format="lceda_epro2", layers=["TopLayer"],
            traces=[
                PCBTrace(net_name="USB_DP", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0, 2, 0)]),
                PCBTrace(net_name="USB_DM", layer="TopLayer", width_mm=0.2,
                         segments=[(0, 0.4, 2, 0.4)]),  # 平行仅 2mm < 5mm
            ],
        )
        v = [x for x in checker.check_all([], {}, pcb_data=pcb) if "串扰" in x.rule_name]
        assert v == []

