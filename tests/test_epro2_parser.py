"""`src/pcb/epro2_parser.py` — 立创 EDA V3 .epro2 解析器测试

用**合成**的 .epro2 包做确定性测试（真实 78 个工程在 test_data/ 下，不入库）。
"""

import json
import shutil
import uuid
import zipfile
from pathlib import Path

import pytest

from src.pcb import create_parser
from src.pcb.epro2_parser import (
    MIL_TO_MM,
    Epro2Parser,
    _polygon_points,
    bom_rows_to_items,
    load_epro2_bom_items,
)
from src.exceptions import PCBParseError


@pytest.fixture
def workdir(request):
    """写临时 .epro2 的目录。

    优先用 pytest 的 ``workdir``；在某些受限/沙箱环境里 ``workdir`` 无法
    创建（pytest 在 Windows 上要用符号链接锁），此时退回工作区内的
    ``output/pytest_epro2/<uuid>``。
    """
    try:
        return request.getfixturevalue("workdir")
    except Exception:  # noqa: BLE001 — workdir 不可用时退回工作区目录
        d = Path("output") / "pytest_epro2" / uuid.uuid4().hex
        d.mkdir(parents=True, exist_ok=True)
        request.addfinalizer(lambda: shutil.rmtree(d, ignore_errors=True))
        return d


# ══════════════════ 合成 .epro2 构造 ══════════════════

def _line(meta: dict, atom: dict) -> str:
    """.epru 一行：{meta}||{atom}|"""
    return json.dumps(meta, ensure_ascii=False) + "||" + json.dumps(atom, ensure_ascii=False) + "|"


def _dochead(doc_type: str, uuid: str) -> str:
    return _line({"type": "DOCHEAD", "ticket": 1},
                 {"docType": doc_type, "uuid": uuid})


def build_epru(*, unit="mm", via_hole=11.811, via_pad=19.685, pad_num="A1",
               outline="poly"):
    """构造一个包含 PCB + FOOTPRINT + DEVICE 文档的最小工程日志

    outline: poly       → 点列模式板框 0,0 - 200,400
             rect_ok    → R 矩形模式，能装下铜
             rect_far   → R 矩形模式，落点偏出铜范围（触发退回铜包围盒）
    """
    lines = []

    # ---- FOOTPRINT 文档：焊盘号在这里 ----
    fp_uuid = "fp-0001"
    lines.append(_dochead("FOOTPRINT", fp_uuid))
    lines.append(_line({"type": "META", "ticket": 1},
                       {"title": "R0402", "tags": []}))
    lines.append(_line({"type": "PAD", "ticket": 2, "id": "e14"},
                       {"num": pad_num, "centerX": 0, "centerY": 0, "layerId": 1}))
    # 一个没有编号的焊盘（散热盘）→ 不应出现在引脚里
    lines.append(_line({"type": "PAD", "ticket": 3, "id": "e15"},
                       {"num": "", "centerX": 0, "centerY": 0, "layerId": 1}))

    # ---- DEVICE 文档：BOM 字段 ----
    dev_uuid = "dev-0001"
    lines.append(_dochead("DEVICE", dev_uuid))
    lines.append(_line({"type": "META", "ticket": 4}, {
        "title": "0402WGF1001TCE",
        "attributes": {
            "Supplier Part": "C11702",
            "Manufacturer Part": "0402WGF1001TCE",
            "Manufacturer": "UNI-ROYAL",
            "Value": "1kΩ",
            "Supplier Footprint": "0402",
            "LCSC Part Name": "1kΩ ±1%",
            "Add into BOM": "yes",
        },
    }))
    # 一个被排除出 BOM 的器件
    lines.append(_dochead("DEVICE", "dev-nobom"))
    lines.append(_line({"type": "META", "ticket": 5}, {
        "title": "MOUNT",
        "attributes": {"Add into BOM": "no", "Value": "MH"},
    }))

    # ---- PCB 文档 ----
    lines.append(_dochead("PCB", "pcb-0001"))
    lines.append(_line({"type": "CANVAS", "ticket": 6},
                       {"originX": 0, "originY": 0, "unit": unit}))
    lines.append(_line({"type": "LAYER", "ticket": 7, "id": '["LAYER",1]'},
                       {"layerType": "TOP", "layerName": "Top Layer", "use": True}))
    lines.append(_line({"type": "LAYER", "ticket": 8, "id": '["LAYER",2]'},
                       {"layerType": "BOTTOM", "layerName": "Bottom Layer", "use": True}))
    # 一个未被使用的层，不应出现在 pcb.layers
    lines.append(_line({"type": "LAYER", "ticket": 9, "id": '["LAYER",91]'},
                       {"layerType": "CUSTOM", "layerName": "Custom99", "use": False}))

    lines.append(_line({"type": "NET", "ticket": 10, "id": '["NET",""]'}, {"netType": None}))
    lines.append(_line({"type": "NET", "ticket": 11, "id": '["NET","VCC"]'},
                       {"differentialName": None, "equalLengthGroupName": None}))
    lines.append(_line({"type": "NET", "ticket": 12, "id": '["NET","USB_DP"]'},
                       {"differentialName": "USB", "equalLengthGroupName": "USB_EL"}))

    # 同一网络 2 段 → 应聚合为 1 条折线（2 段）
    lines.append(_line({"type": "LINE", "ticket": 13, "id": "e1"}, {
        "netName": "VCC", "layerId": 1, "startX": 0, "startY": 0,
        "endX": 100, "endY": 0, "width": 10}))
    lines.append(_line({"type": "LINE", "ticket": 14, "id": "e2"}, {
        "netName": "VCC", "layerId": 1, "startX": 100, "startY": 0,
        "endX": 100, "endY": 100, "width": 10}))
    # 无网络的线（不应计入走线）
    lines.append(_line({"type": "LINE", "ticket": 15, "id": "e3"}, {
        "netName": "", "layerId": 1, "startX": 0, "startY": 0,
        "endX": 1, "endY": 1, "width": 6}))

    lines.append(_line({"type": "VIA", "ticket": 16, "id": "e4"}, {
        "netName": "VCC", "centerX": 100, "centerY": 100,
        "holeDiameter": via_hole, "viaDiameter": via_pad, "viaType": "NORMAL"}))

    lines.append(_line({"type": "POUR", "ticket": 17, "id": "e5"}, {
        "netName": "GND", "layerId": 2, "name": "POUR1", "path": [[0, 0, "L", 10, 0, 10, 10, 0, 10, 0, 0]]}))

    # 元件：位置 + ATTR 子元素
    lines.append(_line({"type": "COMPONENT", "ticket": 18, "id": "c1"}, {
        "layerId": 1, "x": 100, "y": 200, "angle": 90, "attrs": {}}))
    lines.append(_line({"type": "ATTR", "ticket": 19, "id": "c1-a1"}, {
        "parentId": "c1", "key": "Designator", "value": "R1"}))
    lines.append(_line({"type": "ATTR", "ticket": 20, "id": "c1-a2"}, {
        "parentId": "c1", "key": "Device", "value": dev_uuid}))
    lines.append(_line({"type": "ATTR", "ticket": 21, "id": "c1-a3"}, {
        "parentId": "c1", "key": "Footprint", "value": fp_uuid}))

    # 只挂在不进 BOM 的器件上的元件（库属性 Add into BOM=no）
    lines.append(_line({"type": "COMPONENT", "ticket": 22, "id": "c2"}, {
        "layerId": 2, "x": 0, "y": 0, "angle": 0, "attrs": {}}))
    lines.append(_line({"type": "ATTR", "ticket": 23, "id": "c2-a1"}, {
        "parentId": "c2", "key": "Designator", "value": "MH1"}))
    lines.append(_line({"type": "ATTR", "ticket": 24, "id": "c2-a2"}, {
        "parentId": "c2", "key": "Device", "value": "dev-nobom"}))
    lines.append(_line({"type": "ATTR", "ticket": 25, "id": "c2-a3"}, {
        "parentId": "c2", "key": "Footprint", "value": fp_uuid}))

    # 器件库属性说进 BOM，但**实例属性**逐件取消了 → 也必须排除
    # （立创把逐件取消写在这里；只看库属性会多算，实测 3M 多算 62 个位号）
    lines.append(_line({"type": "COMPONENT", "ticket": 29, "id": "c3"}, {
        "layerId": 1, "x": 5, "y": 5, "angle": 0,
        "attrs": {"Unique ID": "gge9", "Add into BOM": "no"}}))
    lines.append(_line({"type": "ATTR", "ticket": 30, "id": "c3-a1"}, {
        "parentId": "c3", "key": "Designator", "value": "R99"}))
    lines.append(_line({"type": "ATTR", "ticket": 31, "id": "c3-a2"}, {
        "parentId": "c3", "key": "Device", "value": dev_uuid}))
    lines.append(_line({"type": "ATTR", "ticket": 32, "id": "c3-a3"}, {
        "parentId": "c3", "key": "Footprint", "value": fp_uuid}))

    # 板框
    if outline == "rect_ok":
        # R X Y width height rot round —— X/Y 是左上角、高度向下延伸
        # （规范口径），顶边 y=400、向下 400 → 覆盖 y∈[0,400]，能装下全部铜
        path = ["R", 0, 400, 200, 400, 0, 0]
    elif outline == "rect_far":
        # 同样的尺寸，但顶边 y=5000，矩形整体落在 y∈[4600,5000]，
        # 偏出 y ∈ [0,100] 的铜范围
        path = ["R", 0, 5000, 200, 400, 0, 0]
    else:
        path = [0, 0, "L", 200, 0, 200, 400, 0, 400, 0, 0]
    lines.append(_line({"type": "POLY", "ticket": 26, "id": "e6"}, {
        "polyType": "BOARD_OUTLINE", "layerId": 11, "path": path}))

    # 焊盘-网络关联：第 4 段是封装里的焊盘元素 id
    lines.append(_line({"type": "PAD_NET", "ticket": 27, "id": '["PAD_NET","c1","1","e14"]'},
                       {"padNet": "VCC"}))
    # 无编号焊盘 → 应被跳过
    lines.append(_line({"type": "PAD_NET", "ticket": 28, "id": '["PAD_NET","c1","e15","e15"]'},
                       {"padNet": "VCC"}))

    return "\n".join(lines) + "\n"


def write_epro2(path, **kwargs):
    """把合成工程写成一个 .epro2（ZIP）"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project2.json", json.dumps({
            "title": "测试工程", "editorVersion": "3.2.186", "tags": [],
        }, ensure_ascii=False))
        zf.writestr("测试工程.epru", build_epru(**kwargs))
        zf.writestr("IMAGE/", "")
    return str(path)


# ══════════════════ 工厂 & 错误处理 ══════════════════

class TestFactoryAndErrors:
    def test_create_parser_returns_epro2(self):
        assert isinstance(create_parser("board.epro2"), Epro2Parser)

    def test_case_insensitive_suffix(self):
        assert isinstance(create_parser("BOARD.EPRO2"), Epro2Parser)

    def test_missing_file(self, workdir):
        with pytest.raises(PCBParseError):
            Epro2Parser().parse(str(workdir / "nope.epro2"))

    def test_wrong_suffix(self, workdir):
        f = workdir / "x.epro"
        f.write_text("x", encoding="utf-8")
        with pytest.raises(PCBParseError):
            Epro2Parser().parse(str(f))

    def test_not_a_zip(self, workdir):
        f = workdir / "bad.epro2"
        f.write_text("not a zip", encoding="utf-8")
        with pytest.raises(PCBParseError):
            Epro2Parser().parse(str(f))

    def test_zip_without_epru(self, workdir):
        f = workdir / "no_epru.epro2"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("project2.json", "{}")
        with pytest.raises(PCBParseError):
            Epro2Parser().parse(str(f))


# ══════════════════ 解析结果 ══════════════════

class TestEpro2Parsing:
    @pytest.fixture
    def data(self, workdir):
        return Epro2Parser().parse(write_epro2(workdir / "t.epro2"))

    def test_format_and_metadata(self, data):
        assert data.format == "lceda_epro2"
        assert data.metadata["title"] == "测试工程"
        assert data.metadata["editor_version"] == "3.2.186"
        assert data.metadata["line_elements"] == 3

    def test_units_converted_from_mil(self, data):
        """几何数值是 mil，必须换算成 mm"""
        assert data.metadata["unit"] == "mil"
        via = data.vias[0]
        # 11.811 mil = 0.3mm 钻孔；19.685 mil = 0.5mm 盘（立创默认过孔）
        assert via.drill_mm == pytest.approx(0.3, abs=1e-3)
        assert via.pad_mm == pytest.approx(0.5, abs=1e-3)
        # 元件坐标同样换算
        assert data.component_positions["R1"]["x"] == pytest.approx(100 * MIL_TO_MM)

    def test_mm_stored_file_not_scaled(self, workdir):
        """已是 mm 存储的工程（钻孔 <2）不再换算"""
        d = Epro2Parser().parse(
            write_epro2(workdir / "mm.epro2", via_hole=0.3, via_pad=0.6)
        )
        assert d.metadata["scale_to_mm"] == 1.0
        assert d.vias[0].drill_mm == pytest.approx(0.3)

    def test_traces_grouped_by_net_and_layer(self, data):
        """同网络同层的多段 LINE 聚合成一条折线；无网络线被丢弃"""
        assert data.trace_count == 1
        t = data.traces[0]
        assert t.net_name == "VCC"
        assert t.layer == "Top Layer"
        assert len(t.segments) == 2
        assert t.width_mm == pytest.approx(10 * MIL_TO_MM)

    def test_trace_segments_are_mm(self, data):
        seg = data.traces[0].segments[0]
        assert seg == pytest.approx((0.0, 0.0, 100 * MIL_TO_MM, 0.0))

    def test_vias(self, data):
        assert data.via_count == 1
        v = data.vias[0]
        assert v.net_name == "VCC"
        assert v.position == pytest.approx((100 * MIL_TO_MM, 100 * MIL_TO_MM))
        assert v.from_layer == "Top Layer"
        assert v.to_layer == "Bottom Layer"

    def test_only_used_layers(self, data):
        assert data.layers == ["Top Layer", "Bottom Layer"]

    def test_nets_and_pin_reconstruction(self, data):
        """引脚来自 PAD_NET，且焊盘号用封装里的真实编号（不是元素 id）"""
        assert "VCC" in data.nets
        assert data.nets["VCC"].pins == ["R1.A1"]
        # 焊盘号退化成元素 id 时也能还原
        assert data.nets["VCC"].trace_count == 1
        assert data.nets["VCC"].total_length_mm == pytest.approx(
            (100 + 100) * MIL_TO_MM, abs=1e-6
        )

    def test_empty_net_dropped(self, data):
        assert "" not in data.nets

    def test_pads_from_pcb_document(self, data):
        assert data.component_positions["R1"]["side"] == "T"
        assert data.component_positions["MH1"]["side"] == "B"

    def test_copper_pours(self, data):
        assert len(data.copper_pours) == 1
        assert data.copper_pours[0]["net_name"] == "GND"
        assert data.copper_pours[0]["layer"] == "Bottom Layer"
        assert data.copper_pours[0]["rings"] == 1

    def test_canvas_unit_is_recorded_but_not_trusted(self, data):
        """CANVAS.unit 只是显示偏好；存储单位一律按 mil 处理"""
        assert data.metadata["canvas_unit"] == "mm"   # 合成文件写的是 mm
        assert data.metadata["unit"] == "mil"          # 但实际按 mil 换算
        assert data.metadata["scale_to_mm"] == MIL_TO_MM

    def test_board_outline(self, data):
        assert data.board_outline["width_mm"] == pytest.approx(200 * MIL_TO_MM, abs=1e-3)
        assert data.board_outline["height_mm"] == pytest.approx(400 * MIL_TO_MM, abs=1e-3)
        assert data.board_outline["shape"] == "polygon"
        assert data.board_outline["source"] == "outline"

    def test_board_outline_falls_back_to_copper(self, workdir):
        """板框装不下铜时（实测泰山派 3M 的 R 矩形 Y 偏移）退回铜包围盒"""
        d = Epro2Parser().parse(write_epro2(workdir / "rect.epro2", outline="rect_far"))
        assert d.board_outline["source"] == "copper"
        # 铜的范围：x 0..100mil，y 0..100mil
        assert d.board_outline["width_mm"] == pytest.approx(100 * MIL_TO_MM, abs=1e-3)

    def test_rect_outline_parsed_when_consistent(self, workdir):
        """R 矩形落点能装下铜时，用它作板框（矩形模式）"""
        d = Epro2Parser().parse(write_epro2(workdir / "rect2.epro2", outline="rect_ok"))
        assert d.board_outline["source"] == "outline"
        assert d.board_outline["shape"] == "rectangle"
        assert d.board_outline["width_mm"] == pytest.approx(200 * MIL_TO_MM, abs=1e-3)

    def test_differential_pairs(self, data):
        assert any(p["net"] == "USB_DP" and p["differential"] == "USB"
                   for p in data.differential_pairs)

    def test_footprint_name_resolved(self, data):
        assert data.component_positions["R1"]["footprint_name"] == "R0402"


# ══════════════════ 路径（多边形）解析 ══════════════════

class TestPolygonPoints:
    """按 V3 规范解析 POLY/REGION/POUR 的 path 数组"""

    def test_point_list_with_L(self):
        pts = _polygon_points([0, 0, "L", 10, 0, 10, 20, 0, 20, 0, 0])
        assert pts == [(0.0, 0.0), (10.0, 0.0), (10.0, 20.0), (0.0, 20.0), (0.0, 0.0)]

    def test_arc_takes_endpoint(self):
        """ARC angle endX endY → 取末两数作为端点"""
        pts = _polygon_points([1961.4961, 868.8549, "ARC", 90, 1882.7559, 947.5951])
        assert pts == [(1961.4961, 868.8549), (1882.7559, 947.5951)]

    def test_bezier_takes_last_control_point(self):
        """C x2 y2 x3 y3 x4 y4 → 末点为终点"""
        pts = _polygon_points([0, 0, "C", 1, 1, 2, 2, 3, 5])
        assert pts == [(0.0, 0.0), (3.0, 5.0)]

    def test_mixed_commands(self):
        pts = _polygon_points([0, 0, "L", 10, 0, "ARC", 90, 10, 10])
        assert pts == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]

    def test_rect_mode_with_rotation(self):
        """R X Y width height rot round；rot=90 时长宽互换"""
        pts = _polygon_points(["R", 0, 0, 100, 50, 90, 0])
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        assert pytest.approx(max(xs) - min(xs)) == 50
        assert pytest.approx(max(ys) - min(ys)) == 100

    def test_circle_mode(self):
        pts = _polygon_points(["CIRCLE", 100, 200, 5, 1])
        assert pts == [(95.0, 195.0), (105.0, 205.0)]

    def test_empty(self):
        assert _polygon_points([]) == []


class TestRingCount:
    """覆铜/区域的环数（复杂多边形 = 外框 + 内洞）"""

    def test_simple_polygon_is_one_ring(self):
        from src.pcb.epro2_parser import _ring_count

        assert _ring_count([[0, 0, "L", 10, 0, 10, 10]]) == 1

    def test_flat_path_is_one_ring(self):
        from src.pcb.epro2_parser import _ring_count

        assert _ring_count([0, 0, "L", 10, 0, 10, 10]) == 1

    def test_complex_polygon_counts_rings(self):
        from src.pcb.epro2_parser import _ring_count

        assert _ring_count([[0, 0, "L", 10, 0], [2, 2, "L", 4, 2]]) == 2

    def test_empty(self):
        from src.pcb.epro2_parser import _ring_count

        assert _ring_count(None) == 0
        assert _ring_count([]) == 0


# ══════════════════ BOM 重建 ══════════════════

class TestEpro2BOM:
    @pytest.fixture
    def data(self, workdir):
        return Epro2Parser().parse(write_epro2(workdir / "t.epro2"))

    def test_bom_fields(self, data):
        assert len(data.bom_items) == 1
        row = data.bom_items[0]
        assert row["reference"] == "R1"
        assert row["value"] == "1kΩ"
        assert row["supplier_part"] == "C11702"
        assert row["part_number"] == "0402WGF1001TCE"
        assert row["manufacturer"] == "UNI-ROYAL"
        assert row["quantity"] == 1
        # 封装名取 FOOTPRINT 文档 title，而不是 JLCPCB 的 0402
        assert row["package"] == "R0402"

    def test_add_into_bom_no_excluded(self, data):
        refs = {r["reference"] for r in data.bom_items}
        assert "MH1" not in refs          # 器件库属性 Add into BOM=no
        assert "R99" not in refs          # 实例属性 Add into BOM=no（库属性是 yes）

    def test_in_bom_flag_on_components(self, data):
        """实例级「加入 BOM」状态要能逐个位号读到"""
        assert data.component_positions["R1"]["in_bom"] is True
        assert data.component_positions["R99"]["in_bom"] is False
        assert data.component_positions["MH1"]["in_bom"] is False
        # 不进 BOM 的元件仍然在位号表里（板上确实有它）
        assert "R99" in data.component_positions

    def test_load_bom_items_dataclass(self, workdir):
        """load_epro2_bom_items 产出 BOMItem（延迟导入 pandas 依赖）"""
        path = write_epro2(workdir / "t.epro2")
        items = load_epro2_bom_items(path)
        assert len(items) == 1
        assert items[0].reference == "R1"
        assert items[0].package == "R0402"
        assert items[0].quantity == 1
