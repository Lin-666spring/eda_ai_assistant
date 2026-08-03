"""
交互式 HTML BOM 生成器
基于 PCB 元件坐标数据，生成可交互的 Web 页面
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from .shared import prepare_component_data, calculate_board_stats

logger = logging.getLogger(__name__)


@dataclass
class HTMLBOMConfig:
    """HTML BOM 生成配置"""

    title: str = "Interactive HTML BOM"
    dark_mode: bool = False
    show_3d_view: bool = False
    highlight_missing: bool = True
    default_layer: str = "Top"
    board_color: str = "#2c3e50"
    language: str = "zh-CN"


class HTMLBOMGenerator:
    """交互式 HTML BOM 生成器"""

    def __init__(self, config: Optional[HTMLBOMConfig] = None):
        self.config = config or HTMLBOMConfig()

        # Jinja2 模板引擎
        template_dir = Path(__file__).parent / "templates"
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
        )

    def generate(
        self,
        bom_items: list,
        positions: dict,
        output_path: Optional[str] = None,
    ) -> str:
        """
        生成交互式 HTML BOM

        Args:
            bom_items:  BOM 物料列表
            positions:  元件坐标 {"R1": {"x":..., "y":..., "rotation":..., "layer":...}, ...}
            output_path: 输出文件路径（可选，不提供则返回 HTML 字符串）

        Returns:
            HTML 字符串
        """
        # 准备数据（委托到 shared.py）
        components = prepare_component_data(bom_items, positions)
        board_stats = calculate_board_stats(positions)

        # 渲染模板
        template = self._env.get_template("ibom.html")
        html = template.render(
            config=self.config,
            components=components,
            board_stats=board_stats,
            components_json=json.dumps(components, ensure_ascii=False),
        )

        # 保存文件
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding="utf-8")
            logger.info(f"HTML BOM 已生成: {output_path}")

        return html

    # _prepare_component_data() and _calculate_board_stats() have been
    # extracted to src/html_bom/shared.py — imported at the top of this module.
