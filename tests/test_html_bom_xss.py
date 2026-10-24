"""HTML BOM / Verification Map XSS 注入回归测试（验收报告 A-1）。

修复前：generator 把 json.dumps 结果经模板 |safe 直插 <script>，
BOM 字段值 </script><script>alert(1)</script> 可闭合脚本块执行任意 JS，
生成后还被 main.py 自动 webbrowser.open()。
修复后：模板内 |tojson（转义 <>&' 为 \\uXXXX）。
"""

import pytest

from src.bom.parser import BOMItem
from src.html_bom.generator import HTMLBOMGenerator
from src.html_bom.verification_map import VerificationMapGenerator

PAYLOAD = "</script><script>alert(1)</script>"


def _evil_bom():
    return [BOMItem(
        reference="R1",
        value=PAYLOAD,
        package="0603",
        part_number=PAYLOAD,
        description=PAYLOAD,
    )]


def _positions():
    return {"R1": {"x": 10.0, "y": 20.0, "rotation": 0, "layer": "top"}}


class TestHTMLBOMXSS:
    def test_ibom_script_injection_neutralized(self):
        html = HTMLBOMGenerator().generate(_evil_bom(), _positions())
        # 脚本块不得被闭合：输出中不得出现未转义的 </script><script>
        assert "</script><script>" not in html
        # tojson 转义后 < 为 \u003c
        assert "\\u003c" in html

    def test_ibom_payload_not_executable(self):
        html = HTMLBOMGenerator().generate(_evil_bom(), _positions())
        # 提取 <script> 块内内容，确认 payload 以转义形态存在
        assert PAYLOAD not in html

    def test_verification_map_injection_neutralized(self):
        overlay = {
            "drc_heatmap": {"R1": {"count": 1, "max_severity": "error",
                                   "violations": [{"desc": PAYLOAD}]}},
            "stats": {"total_errors": 1},
        }
        html = VerificationMapGenerator().generate(
            _evil_bom(), _positions(), overlay)
        assert "</script><script>" not in html
        assert PAYLOAD not in html

    def test_normal_content_still_renders(self):
        items = [BOMItem(reference="R1", value="10k", package="0603",
                         part_number="RC0603FR-0710KL")]
        html = HTMLBOMGenerator().generate(items, _positions())
        assert "RC0603FR-0710KL" in html
        assert "10k" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
