"""P1-16（验收 2026-10-24）.epro2 底层元件焊盘镜像回归。

反面（layerId=2）元件是封装翻面贴装：焊盘相对坐标必须先做 Y 镜像再旋转
定位。旧实现不分层直接「旋转+平移」，非对称封装的底层焊盘绝对位置系统性
偏错（对称封装侥幸重合掩盖）。口径按 78 板实测钉死：底层焊盘与同网底层
走线端点重合数「先镜像后旋转」4754/仅 73 失配，不镜像 3050/7261 失配；
顶层对照组确认顶层保持「旋转+平移不镜像」。
"""

import json
import zipfile

import pytest

from src.pcb.epro2_parser import MIL_TO_MM, Epro2Parser


def _line(meta: dict, atom: dict) -> str:
    return json.dumps(meta, ensure_ascii=False) + "||" + json.dumps(atom, ensure_ascii=False) + "|"


def _dochead(doc_type: str, doc_uuid: str) -> str:
    return _line({"type": "DOCHEAD", "ticket": 1},
                 {"docType": doc_type, "uuid": doc_uuid})


def build_bottom_mirror_epru() -> str:
    """非对称封装（焊盘 1 在原点、焊盘 2 在 (100,50) mil）+ 顶层/底层各一只
    同封装元件（同位置同角度 90°），焊盘挂不同网络。"""
    lines = []
    fp_uuid = "fp-asym"
    lines.append(_dochead("FOOTPRINT", fp_uuid))
    lines.append(_line({"type": "META", "ticket": 2},
                       {"title": "SOT-23-ASYM", "tags": []}))
    # 非对称焊盘：pad1 (0,0)、pad2 (100,50)——y≠0 才能暴露 Y 镜像
    lines.append(_line({"type": "PAD", "ticket": 3, "id": "e14"},
                       {"num": "1", "centerX": 0, "centerY": 0, "layerId": 1}))
    lines.append(_line({"type": "PAD", "ticket": 4, "id": "e15"},
                       {"num": "2", "centerX": 100, "centerY": 50, "layerId": 1}))
    # 对称焊盘（y=0）：镜像不变量，旧实现「侥幸对」的来源
    lines.append(_line({"type": "PAD", "ticket": 5, "id": "e16"},
                       {"num": "3", "centerX": 200, "centerY": 0, "layerId": 1}))

    lines.append(_dochead("PCB", "pcb-0001"))
    for comp_id, ref, layer_id in (("c1", "R1", 1), ("c2", "R2", 2)):
        lines.append(_line({"type": "COMPONENT", "ticket": 10, "id": comp_id}, {
            "layerId": layer_id, "x": 1000, "y": 2000, "angle": 90, "attrs": {}}))
        lines.append(_line({"type": "ATTR", "ticket": 11, "id": f"{comp_id}-a1"}, {
            "parentId": comp_id, "key": "Designator", "value": ref}))
        lines.append(_line({"type": "ATTR", "ticket": 12, "id": f"{comp_id}-a2"}, {
            "parentId": comp_id, "key": "Footprint", "value": fp_uuid}))
    for i, (comp_id, pad_num, pad_elem, net) in enumerate([
        ("c1", "1", "e14", "NA1"), ("c1", "2", "e15", "NB1"), ("c1", "3", "e16", "NC1"),
        ("c2", "1", "e14", "NA2"), ("c2", "2", "e15", "NB2"), ("c2", "3", "e16", "NC2"),
    ]):
        lines.append(_line(
            {"type": "PAD_NET", "ticket": 20 + i,
             "id": json.dumps(["PAD_NET", comp_id, pad_num, pad_elem])},
            {"padNet": net}))
    return "\n".join(lines) + "\n"


@pytest.fixture
def data(tmp_path):
    p = tmp_path / "mirror.epro2"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("project2.json", json.dumps({"title": "mirror"}))
        zf.writestr("mirror.epru", build_bottom_mirror_epru())
    return Epro2Parser().parse(str(p))


def _pad(data, ref: str, num: str) -> dict:
    hits = [p for p in data.pads if p["ref"] == ref and p["num"] == num]
    assert len(hits) == 1, f"{ref}.{num} 应恰好解析出 1 个焊盘"
    return hits[0]


def test_top_pad_unmirrored(data):
    """顶层对照：旋转 90° 不镜像 —— (100,50) → (−50,100) + (1000,2000)。"""
    pad = _pad(data, "R1", "2")
    assert pad["x"] == pytest.approx(950 * MIL_TO_MM, abs=1e-6)
    assert pad["y"] == pytest.approx(2100 * MIL_TO_MM, abs=1e-6)


def test_bottom_pad_y_mirrored(data):
    """缺陷本体：底层同位置同角度元件，pad2 相对坐标必须先 Y 镜像——
    (100,−50) → 旋转 90° → (50,100) + (1000,2000)。
    （不镜像的旧结果是 (950,2100) mil，x 差 100mil=2.54mm）"""
    pad = _pad(data, "R2", "2")
    assert pad["x"] == pytest.approx(1050 * MIL_TO_MM, abs=1e-6)
    assert pad["y"] == pytest.approx(2100 * MIL_TO_MM, abs=1e-6)
    assert pad["x"] != pytest.approx(950 * MIL_TO_MM, abs=0.1)


def test_symmetric_pad_mirror_invariant(data):
    """y=0 的对称焊盘底层与顶层绝对位置一致（对称封装此前侥幸正确的机理）。"""
    top = _pad(data, "R1", "3")
    bottom = _pad(data, "R2", "3")
    assert (bottom["x"], bottom["y"]) == pytest.approx((top["x"], top["y"]))


def test_origin_pad_mirror_invariant(data):
    top = _pad(data, "R1", "1")
    bottom = _pad(data, "R2", "1")
    assert (bottom["x"], bottom["y"]) == pytest.approx((top["x"], top["y"]))
