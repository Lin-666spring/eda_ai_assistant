"""
EDA 工具适配器接口
统一不同 EDA 工具（立创EDA、KiCad、Altium）的数据获取方式
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class PCBData:
    """PCB 数据容器"""

    bom_items: list           # BOM 物料列表
    component_positions: dict  # 位号 → (x, y, rotation, layer)
    board_outline: dict        # 板框信息
    layers: list[str]          # 层列表


class EDAAdapter(ABC):
    """EDA 工具适配器抽象基类

    封装不同 EDA 工具的数据获取差异，向上层提供统一接口。
    支持未来扩展至 KiCad、Altium Designer 等工具。
    """

    @abstractmethod
    def get_bom(self, project_path: str) -> list:
        """获取 BOM 数据"""
        ...

    @abstractmethod
    def get_positions(self, project_path: str) -> dict:
        """获取元件坐标 (Pick & Place)"""
        ...

    @abstractmethod
    def get_project_info(self, project_path: str) -> dict:
        """获取项目基本信息"""
        ...

    @property
    @abstractmethod
    def tool_name(self) -> str:
        """工具名称"""
        ...


class LCEDAAdapter(EDAAdapter):
    """立创EDA（LCEDA）适配器

    支持：
    - 立创EDA专业版 (.epro 项目文件)
    - 立创EDA标准版导出的 BOM CSV / Excel
    - 坐标文件 (Pick & Place CSV)
    """

    @property
    def tool_name(self) -> str:
        return "立创EDA (LCEDA)"

    def get_bom(self, project_path: str) -> list:
        """
        获取 BOM 数据

        立创EDA 通常通过以下方式导出 BOM：
        1. 菜单 → 制造 → BOM 表 → 导出 CSV/Excel
        2. 本项目直接解析导出的文件
        """
        # 委托给 BOM 解析模块
        from ..bom.parser import BOMParser

        parser = BOMParser()
        return parser.parse(project_path)

    def get_positions(self, project_path: str) -> dict:
        """
        获取元件坐标数据

        立创EDA 导出坐标文件步骤：
        菜单 → 制造 → 坐标文件 → 导出 CSV
        格式：Designator, Footprint, Mid X, Mid Y, Layer, Rotation
        """
        import csv
        from pathlib import Path

        path = Path(project_path)
        positions = {}

        if path.suffix.lower() != ".csv":
            return positions

        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ref = row.get("Designator", row.get("位号", ""))
                if not ref:
                    continue
                positions[ref] = {
                    "x": float(row.get("Mid X", row.get("X", 0))),
                    "y": float(row.get("Mid Y", row.get("Y", 0))),
                    "rotation": float(row.get("Rotation", row.get("旋转", 0))),
                    "layer": row.get("Layer", row.get("层", "Top")),
                    "package": row.get("Footprint", row.get("封装", "")),
                }

        return positions

    def get_project_info(self, project_path: str) -> dict:
        """获取项目基本信息"""
        return {
            "tool": self.tool_name,
            "project_path": project_path,
            "supported_formats": [".csv", ".xlsx", ".xls"],
        }
