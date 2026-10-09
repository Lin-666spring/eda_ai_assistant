"""覆铜几何 / 焊盘重建 / orphan 焊盘保留 —— 2026-10-09 数据补全批次回归

背景：copper_pours 此前只有网络名+环数，铜皮连接规则恒报「未包含铜皮
数据」；orphan 焊盘记录整条丢弃，两脚网络被看成单针浮空网（天线规则
误报）。本文件用独立的最小合成 .epro2（mm 单位、scale=1）锁定：

1. R 矩形模式 X/Y 是左上角、高度向下延伸（规范口径）——万兆板整版
   GND 铜落到板外 170~340mm 的病根
2. 带网络 FILL/POLY 铜形入 copper_pours 并带环几何
3. orphan PAD_NET 保留引脚 + 记录 orphan_nets
4. 元件焊盘绝对坐标重建（封装相对坐标 + 元件位置/旋转）
5. 铜皮连接规则：孤岛判定、网格铜经相邻铜形传递接入
"""

import json
import zipfile
from pathlib import Path

import pytest

from src.pcb.epro2_parser import Epro2Parser, _rect_corners
from src.pcb.models import PCBData, PCBVia
from src.pcb.geometry import point_in_polygon, segment_touches_polygon


# ══════════════════ 合成最小工程 ══════════════════

def _line(meta: dict, atom: dict) -> str:
    return json.dumps(meta, ensure_ascii=False) + "||" + json.dumps(atom, ensure_ascii=False) + "|"


def _dochead(doc_type: str, uuid: str) -> str:
    return _line({"type": "DOCHEAD", "ticket": 1},
                 {"docType": doc_type, "uuid": uuid})


def build_geo_epru(*, pour_path=None, fills=(), polys=(),
                   pad_nets=(), comp_rotation=0.0):
    """最小工程：GND 网络 + 一条走线 + 一个过孔 + 可选铜形/焊盘关联

    unit=mm、过孔 0.3/0.6 → scale=1，测试里坐标即 mm。
    默认内容：
    - LINE  GND layer1 (5,5)-(15,5)
    - VIA   GND (10,10)
    - POUR  GND layer2（pour_path 未给时用点列 0,0..30,30）
    - FOOTPRINT：焊盘 e14「1」@(10,0)、e15「2」@(20,0)
    - COMPONENT c1 @(100,100) 旋转 comp_rotation，位号 R1
    """
    lines = []
    lines.append(_dochead("FOOTPRINT", "fp-1"))
    lines.append(_line({"type": "META", "ticket": 1}, {"title": "SOT23", "tags": []}))
    lines.append(_line({"type": "PAD", "ticket": 2, "id": "e14"},
                       {"num": "1", "centerX": 10, "centerY": 0, "layerId": 1}))
    lines.append(_line({"type": "PAD", "ticket": 3, "id": "e15"},
                       {"num": "2", "centerX": 20, "centerY": 0, "layerId": 1}))

    lines.append(_dochead("PCB", "pcb-1"))
    lines.append(_line({"type": "CANVAS", "ticket": 4},
                       {"originX": 0, "originY": 0, "unit": "mm"}))
    lines.append(_line({"type": "LAYER", "ticket": 5, "id": '["LAYER",1]'},
                       {"layerType": "TOP", "layerName": "Top Layer", "use": True}))
    lines.append(_line({"type": "LAYER", "ticket": 6, "id": '["LAYER",2]'},
                       {"layerType": "BOTTOM", "layerName": "Bottom Layer", "use": True}))
    lines.append(_line({"type": "NET", "ticket": 7, "id": '["NET","GND"]'},
                       {"differentialName": None, "equalLengthGroupName": None}))
    lines.append(_line({"type": "LINE", "ticket": 8, "id": "e1"}, {
        "netName": "GND", "layerId": 1, "startX": 5, "startY": 5,
        "endX": 15, "endY": 5, "width": 1}))
    lines.append(_line({"type": "VIA", "ticket": 9, "id": "e2"}, {
        "netName": "GND", "centerX": 10, "centerY": 10,
        "holeDiameter": 0.3, "viaDiameter": 0.6, "viaType": "NORMAL"}))
    if pour_path is None:
        pour_path = [[0, 0, "L", 30, 0, 30, 30, 0, 30, 0, 0]]
    lines.append(_line({"type": "POUR", "ticket": 10, "id": "e3"}, {
        "netName": "GND", "layerId": 2, "name": "P1", "path": pour_path}))
    for i, (net, layer_id, path) in enumerate(fills):
        lines.append(_line({"type": "FILL", "ticket": 20 + i, "id": f"f{i}"}, {
            "netName": net, "layerId": layer_id, "fillStyle": "SOLID",
            "path": path, "networkList": [], "refs": []}))
    for i, (net, layer_id, path) in enumerate(polys):
        lines.append(_line({"type": "POLY", "ticket": 40 + i, "id": f"p{i}"}, {
            "netName": net, "layerId": layer_id, "width": 0.2,
            "path": path, "polyType": "NORMAL"}))
    lines.append(_line({"type": "COMPONENT", "ticket": 60, "id": "c1"}, {
        "layerId": 1, "x": 100, "y": 100, "angle": comp_rotation, "attrs": {}}))
    lines.append(_line({"type": "ATTR", "ticket": 61, "id": "c1-a1"}, {
        "parentId": "c1", "key": "Designator", "value": "R1"}))
    lines.append(_line({"type": "ATTR", "ticket": 62, "id": "c1-a2"}, {
        "parentId": "c1", "key": "Device", "value": "dev-x"}))
    lines.append(_line({"type": "ATTR", "ticket": 63, "id": "c1-a3"}, {
        "parentId": "c1", "key": "Footprint", "value": "fp-1"}))
    for i, (pad_num, pad_elem, net) in enumerate(pad_nets):
        lines.append(_line(
            {"type": "PAD_NET", "ticket": 70 + i,
             "id": json.dumps(["PAD_NET", "c1", pad_num, pad_elem])},
            {"padNet": net}))
    return "\n".join(lines) + "\n"


def parse_epru(tmp_path, **kwargs):
    p = tmp_path / "geo.epro2"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("project2.json", json.dumps({"title": "t"}, ensure_ascii=False))
        zf.writestr("t.epru", build_geo_epru(**kwargs))
    return Epro2Parser().parse(str(p))


# ══════════════════ R 矩形模式 ══════════════════

def test_r_rect_is_top_left_downward():
    """规范口径：R X Y W H → 矩形跨 y ∈ [Y−H, Y]（X/Y 左上角）"""
    pts = _rect_corners(17, 6692.9, 3937.0, 6692.9, 0)
    ys = [y for _, y in pts]
    xs = [x for x, _ in pts]
    assert min(ys) == pytest.approx(0.0)
    assert max(ys) == pytest.approx(6692.9)
    assert min(xs) == pytest.approx(17.0)
    assert max(xs) == pytest.approx(17.0 + 3937.0)


def test_pour_r_rect_lands_inside_board(tmp_path):
    """万兆板病根回归：R 模式整版 GND 铜不再翻到板外"""
    pcb = parse_epru(tmp_path, pour_path=[["R", 0, 100, 200, 100, 0, 0]])
    pour = pcb.copper_pours[0]
    assert pour["source"] == "POUR"
    ys = [y for _, y in pour["outer"]]
    assert min(ys) == pytest.approx(0.0)
    assert max(ys) == pytest.approx(100.0)


# ══════════════════ FILL / POLY 铜形 ══════════════════

def test_netted_fill_parsed_with_geometry(tmp_path):
    pcb = parse_epru(tmp_path, fills=[
        ("GND", 1, [["R", 20, 30, 10, 10, 0, 0]]),   # 铜层带网 → 入表
        ("", 1, [["R", 40, 30, 10, 10, 0, 0]]),      # 无网 → 图形，不入表
        ("GND", 12, [["R", 40, 60, 10, 10, 0, 0]]),  # 文档层 → 不算铜
    ])
    fills = [p for p in pcb.copper_pours if p.get("source") == "FILL"]
    assert len(fills) == 1
    assert fills[0]["net_name"] == "GND"
    xs = [x for x, _ in fills[0]["outer"]]
    ys = [y for _, y in fills[0]["outer"]]
    assert (min(xs), min(ys), max(xs), max(ys)) == pytest.approx((20, 20, 30, 30))


def test_netted_fill_circle_subpath(tmp_path):
    pcb = parse_epru(tmp_path, fills=[("GND", 2, [["CIRCLE", 10, 10, 2, 0]])])
    fills = [p for p in pcb.copper_pours if p.get("source") == "FILL"]
    assert len(fills) == 1
    # 24 边形近似：所有顶点距圆心 ≈ r
    for x, y in fills[0]["outer"]:
        assert (x - 10) ** 2 + (y - 10) ** 2 == pytest.approx(4.0, rel=0.2)


def test_netted_poly_parsed(tmp_path):
    pcb = parse_epru(tmp_path, polys=[("GND", 1, [0, 40, "L", 10, 40, 10, 50, 0, 50, 0, 40])])
    polys = [p for p in pcb.copper_pours if p.get("source") == "POLY"]
    assert len(polys) == 1
    assert len(polys[0]["outer"]) >= 4


# ══════════════════ orphan 焊盘保留 ══════════════════

def test_orphan_pad_kept_not_dropped(tmp_path):
    """封装文档缺失的陈旧焊盘记录：保留引脚（引脚计数真实性优先）"""
    pcb = parse_epru(tmp_path, pad_nets=[
        ("1", "e14", "GND"),     # 封装里有 → 正常解析
        ("2", "e99", "SIG"),     # 封装里没有 → 旧版丢弃，现在保留
    ])
    assert pcb.nets["SIG"].pins == ["R1.2"]
    assert "R1.1" in pcb.nets["GND"].pins
    assert pcb.metadata["orphan_pad_nets"] == 1
    assert pcb.metadata["orphan_nets"] == ["SIG"]


# ══════════════════ 焊盘绝对坐标重建 ══════════════════

def test_pads_reconstructed_with_rotation(tmp_path):
    """封装相对坐标 + 元件位置/旋转 = 绝对坐标；(10,0) 转 90° → (0,10)"""
    pcb = parse_epru(tmp_path, comp_rotation=90.0, pad_nets=[("1", "e14", "GND")])
    assert len(pcb.pads) == 1
    pad = pcb.pads[0]
    assert pad["ref"] == "R1"
    assert pad["net"] == "GND"
    assert pad["thru"] is False
    assert pad["x"] == pytest.approx(100.0)
    assert pad["y"] == pytest.approx(110.0)


# ══════════════════ 几何工具 ══════════════════

RECT = [(0, 0), (10, 0), (10, 10), (0, 10)]


def test_point_in_polygon_basic():
    assert point_in_polygon((5, 5), RECT)
    assert not point_in_polygon((15, 5), RECT)
    assert point_in_polygon((5, 0), RECT)        # 边界视为内
    assert not point_in_polygon((5, 5), RECT, voids=[[(4, 4), (6, 4), (6, 6), (4, 6)]])


def test_segment_touches_polygon():
    assert segment_touches_polygon((5, -2), (5, 12), RECT)   # 穿越
    assert segment_touches_polygon((12, 12), (20, 20), RECT) is False
    assert segment_touches_polygon((-5, 5), (-1, 5), RECT) is False


# ══════════════════ 铜皮连接规则 ══════════════════

def _checker():
    from src.rules.checker import DesignRuleChecker
    return DesignRuleChecker()


def test_island_rule_floating_pour_reported(tmp_path):
    """孤铜（无过孔/焊盘/走线接入）→ 报；旁边有接入的铜 → 不报"""
    pcb = parse_epru(tmp_path)   # 大 Pour 覆盖 (10,10) 的 GND 过孔 → 接入
    pcb.copper_pours.append({
        "net_name": "SIG", "layer": "Top Layer", "layer_id": 1, "name": "",
        "rings": 1, "source": "FILL", "outer": [(50, 50), (60, 50), (60, 60), (50, 60)],
        "voids": [],
    })
    v = _checker().check_all([], {}, {}, pcb_data=pcb)
    copper = [x for x in v if x.rule_name == "铜皮连接检查"]
    assert len(copper) == 1
    assert "SIG" in copper[0].description


def test_island_rule_grid_tiles_pass_via_neighbor(tmp_path):
    """网格铜：孤tile自身无证据但与已接入tile相触 → 传递接入，不报"""
    pcb = PCBData(format="lceda_epro2")
    # tile A 上有 GND 过孔；tile B 只与 A 相触
    for i, (x0, y0) in enumerate([(0, 0), (10, 0)]):
        pcb.copper_pours.append({
            "net_name": "GND", "layer": "Top Layer", "layer_id": 1, "name": "",
            "rings": 1, "source": "FILL",
            "outer": [(x0, y0), (x0 + 10.01, y0), (x0 + 10.01, y0 + 10), (x0, y0 + 10)],
            "voids": [],
        })
    pcb.vias.append(PCBVia(position=(5, 5), drill_mm=0.3, pad_mm=0.6,
                           from_layer="Top Layer", to_layer="Bottom Layer",
                           net_name="GND"))
    v = _checker().check_all([], {}, {}, pcb_data=pcb)
    assert [x for x in v if x.rule_name == "铜皮连接检查"] == []


def test_island_rule_no_shapes_missing_data_message(tmp_path):
    """完全没有铜形 → 保留「未包含铜皮数据」可证伪提示"""
    pcb = PCBData(format="lceda_epro2")
    v = _checker().check_all([], {}, {}, pcb_data=pcb)
    copper = [x for x in v if x.rule_name == "铜皮连接检查"]
    assert len(copper) == 1
    assert "未包含铜皮数据" in copper[0].description


def test_island_rule_orphan_net_not_judged(tmp_path):
    """orphan 网络的铜片：无法验证不判"""
    pcb = PCBData(format="lceda_epro2")
    pcb.copper_pours.append({
        "net_name": "SIG", "layer": "Top Layer", "layer_id": 1, "name": "",
        "rings": 1, "source": "POUR", "outer": [(0, 0), (10, 0), (10, 10), (0, 10)],
        "voids": [],
    })
    pcb.metadata["orphan_nets"] = ["SIG"]
    v = _checker().check_all([], {}, {}, pcb_data=pcb)
    assert [x for x in v if x.rule_name == "铜皮连接检查"] == []
