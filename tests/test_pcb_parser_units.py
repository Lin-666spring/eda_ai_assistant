"""PCB 解析器单位换算回归测试（验收报告 A-6）。

标准版 .json 与专业版 .epro 的坐标/线宽/孔径以 0.01 inch（=10mil=0.254mm）
为单位。修复前解析器不做换算，10mil 尺度被当 mm 喂给全部下游规则。
"""

import json
import zipfile

import pytest

from src.pcb.parser import LCEDAJsonParser, LCEDAProParser, TEN_MIL_TO_MM


def _write_json(tmp_path, canvas):
    p = tmp_path / "board.json"
    p.write_text(json.dumps({"head": {"docType": "pcb"}, "canvas": canvas}),
                 encoding="utf-8")
    return str(p)


class TestJsonParserUnitConversion:
    def test_track_width_10_units_is_2_54_mm(self, tmp_path):
        # 宽 10 单位 = 100mil = 2.54mm；修复前会被当成 10mm
        p = _write_json(tmp_path, ["TRACK~1~1~GND~10~100 100~200 100"])
        data = LCEDAJsonParser().parse(p)
        assert data.traces[0].width_mm == pytest.approx(2.54)

    def test_track_coordinates_scaled(self, tmp_path):
        p = _write_json(tmp_path, ["TRACK~1~1~GND~10~100 100~200 100"])
        data = LCEDAJsonParser().parse(p)
        seg = data.traces[0].segments[0]
        assert seg[0] == pytest.approx(100 * TEN_MIL_TO_MM)
        assert seg[2] == pytest.approx(200 * TEN_MIL_TO_MM)

    def test_via_drill_and_position_scaled(self, tmp_path):
        # 典型过孔：孔 12 单位 ≈ 30mil ≈ 0.762mm；修复前被当成 12mm
        p = _write_json(tmp_path, ["VIA~1~1~GND~500 400~12~24"])
        data = LCEDAJsonParser().parse(p)
        via = data.vias[0]
        assert via.drill_mm == pytest.approx(12 * TEN_MIL_TO_MM)
        assert via.pad_mm == pytest.approx(24 * TEN_MIL_TO_MM)
        assert via.position[0] == pytest.approx(500 * TEN_MIL_TO_MM)
        assert via.position[1] == pytest.approx(400 * TEN_MIL_TO_MM)

    def test_signal_width_typical_values_in_mm_range(self, tmp_path):
        """换算后常见信号线宽应落在真实 mm 量级（0.1~0.5mm）。"""
        # 6mil 信号线 = 0.6 单位
        p = _write_json(tmp_path, ["TRACK~1~1~SPI~0.6~0 0~10 0"])
        data = LCEDAJsonParser().parse(p)
        assert 0.1 <= data.traces[0].width_mm <= 0.5


class TestEproParserUnitConversion:
    def _write_epro(self, tmp_path, elements):
        p = tmp_path / "board.epro"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr(
                "project.json",
                json.dumps({"name": "t", "version": "3"}),
            )
            zf.writestr(
                "pcb.epcb",
                "\n".join(json.dumps(e, ensure_ascii=False) for e in elements),
            )
        return str(p)

    def test_track_and_via_scaled(self, tmp_path):
        p = self._write_epro(tmp_path, [
            {"type": "TRACK", "net": "GND", "layer": 1, "width": 10,
             "points": [[100, 100], [200, 100]]},
            {"type": "VIA", "net": "GND", "layer": 1,
             "x": 500, "y": 400, "drill": 12, "pad": 24},
        ])
        data = LCEDAProParser().parse(p)
        assert data.traces[0].width_mm == pytest.approx(2.54)
        assert data.traces[0].segments[0][0] == pytest.approx(100 * TEN_MIL_TO_MM)
        assert data.vias[0].drill_mm == pytest.approx(12 * TEN_MIL_TO_MM)
        assert data.vias[0].position[0] == pytest.approx(500 * TEN_MIL_TO_MM)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
