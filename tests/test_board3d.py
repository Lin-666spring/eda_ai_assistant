"""3D 板卡预览载荷测试 — AppController.get_board_3d_data（2026-10-24）。

锁定的行为：

1. 无工程数据 → ``ok=True`` + ``reason='no_data'``，载荷各字段为空（前端
   据此显示空态提示，不报错）；
2. 有 pcb_data → 板框/元件/走线/过孔序列化完整：坐标 mm 保留 3 位小数、
   ``outline_rings_mm`` 转成 ``board.rings`` 数组、元件带 side/in_bom；
3. 走线段平铺成 ``[x1,y1,x2,y2,...]``，长度恒为 4 的倍数（前端按 4 步长
   重排成 three.js 顶点三元组）；
4. ``rotation=None``（epro2 缺省）落成 0，不让 None 进载荷；
5. 截断上限生效：实例级调小 ``_3D_MAX_SEGMENTS`` / ``_3D_MAX_VIAS`` 后，
   载荷截断且 ``counts`` 里的 truncated 标志置位；
6. 整个载荷可 ``json.dumps``（eel 包装层与 FastAPI 都直接序列化它）。
"""

from __future__ import annotations

import json

from src.core.controller import AppController
from src.pcb.models import PCBData, PCBTrace, PCBVia


def _make_pcb() -> PCBData:
    pcb = PCBData(format="lceda_epro2")
    pcb.layers = ["TopLayer", "BottomLayer"]
    pcb.board_outline = {
        "width_mm": 84.0, "height_mm": 56.2,
        "min_x_mm": 0.0, "min_y_mm": 0.0, "max_x_mm": 84.0, "max_y_mm": 56.2,
        "shape": "polygon", "source": "outline",
        "outline_rings_mm": [[(0.0, 0.0), (84.0, 0.0), (84.0, 56.2), (0.0, 56.2)]],
    }
    pcb.component_positions = {
        "U1": {"x": 10.0, "y": 20.0, "rotation": 90.0, "layer": "TopLayer",
               "side": "T", "footprint_name": "QFN-68_L7.0-W7.0-P0.35",
               "value": "RK3576", "in_bom": True},
        "C1": {"x": 30.5, "y": 40.25, "rotation": None, "layer": "BottomLayer",
               "side": "B", "footprint_name": "C0402", "value": "100nF",
               "in_bom": True},
    }
    pcb.traces = [
        PCBTrace(net_name="VCC", layer="TopLayer", width_mm=0.2,
                 segments=[(0, 0, 1, 1), (1, 1, 2, 2)]),
        PCBTrace(net_name="GND", layer="BottomLayer", width_mm=0.5,
                 segments=[(5, 5, 6, 6)]),
    ]
    pcb.vias = [
        PCBVia(position=(1.0, 2.0), drill_mm=0.3, pad_mm=0.5,
               from_layer="TopLayer", to_layer="BottomLayer", net_name="GND"),
        PCBVia(position=(3.0, 4.0), drill_mm=0.3, pad_mm=0.6,
               from_layer="TopLayer", to_layer="BottomLayer", net_name="VCC"),
    ]
    return pcb


def test_board3d_no_data_reason():
    ctrl = AppController(api_key="")
    out = ctrl.get_board_3d_data()
    assert out["ok"] is True
    assert out["reason"] == "no_data"
    assert out["board"] is None
    assert out["components"] == []
    assert out["counts"] == {}


def test_board3d_payload_shape():
    ctrl = AppController(api_key="")
    ctrl.context.pcb_data = _make_pcb()

    out = ctrl.get_board_3d_data()
    assert out["ok"] is True and out["reason"] == ""
    assert out["format"] == "lceda_epro2"

    # 板框：rings 由 tuple 环转数组，bbox 字段原样带出
    assert out["board"]["rings"] == [[[0.0, 0.0], [84.0, 0.0],
                                      [84.0, 56.2], [0.0, 56.2]]]
    assert out["board"]["width_mm"] == 84.0

    # 元件：side/rotation 保留；rotation=None 归零；坐标保留 3 位小数
    comps = {c["ref"]: c for c in out["components"]}
    assert comps["U1"]["side"] == "T"
    assert comps["U1"]["footprint_name"] == "QFN-68_L7.0-W7.0-P0.35"
    assert comps["C1"]["rotation"] == 0
    assert comps["C1"]["x"] == 30.5 and comps["C1"]["y"] == 40.25

    # 走线：平铺数组长度是 4 的倍数，层名与线宽保留
    top = next(t for t in out["traces"] if t["layer"] == "TopLayer")
    assert len(top["segs"]) == 8          # 2 段 × 4
    assert top["width_mm"] == 0.2
    assert out["counts"]["trace_segments"] == 3

    # 过孔：[x, y, pad]
    assert out["vias"][1] == [3.0, 4.0, 0.6]
    assert out["counts"]["vias"] == 2
    assert out["counts"]["components"] == 2


def test_board3d_truncation_flags():
    ctrl = AppController(api_key="")
    ctrl.context.pcb_data = _make_pcb()
    ctrl._3D_MAX_SEGMENTS = 1            # 第一条走线只有 2 段 → 1 段就截断
    ctrl._3D_MAX_VIAS = 1

    out = ctrl.get_board_3d_data()
    assert out["counts"]["segments_truncated"] is True
    assert out["counts"]["trace_segments"] == 1
    assert out["counts"]["vias_truncated"] is True
    assert len(out["vias"]) == 1


def test_board3d_json_serializable():
    ctrl = AppController(api_key="")
    ctrl.context.pcb_data = _make_pcb()
    out = ctrl.get_board_3d_data()
    text = json.dumps(out, ensure_ascii=False)     # eel / FastAPI 同款路径
    assert '"board3d"' not in text                  # 载荷没混进多余键
    assert "RK3576" in text
