"""
BOM 文件解析器
支持立创EDA导出的 CSV / Excel 格式 BOM 文件
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from ..constants import BOM, SupportedFormat

logger = logging.getLogger(__name__)


@dataclass
class BOMItem:
    """BOM 单行数据"""

    reference: str       # 位号，如 "R1,R2,R3"
    value: str           # 参数值，如 "10kΩ", "100nF"
    package: str         # 封装，如 "0603", "SOP-8"
    part_number: str     # 型号/产品编号
    description: str = ""  # 描述
    quantity: int = 1    # 数量
    manufacturer: str = ""  # 制造商

    def __post_init__(self):
        self.quantity = int(self.quantity) if self.quantity is not None else 1

    @property
    def reference_list(self) -> list[str]:
        """将位号字符串拆分为列表，如 'R1,R2,R3' -> ['R1','R2','R3']"""
        return [r.strip() for r in self.reference.split(",") if r.strip()]


class BOMParser:
    """BOM 文件解析器 — 支持立创EDA导出的 CSV / Excel 格式"""

    # 立创EDA常见列名映射
    _COLUMN_ALIASES = {
        "reference":  ["位号", "Designator", "Reference", "Ref", "编号"],
        "value":      ["参数", "Value", "阻值/容值", "规格"],
        "package":    ["封装", "Package", "Footprint", "封装类型"],
        "part_number":["产品编号", "Part Number", "型号", "MPN", "LCSC Part #", "商品编号"],
        "description":["描述", "Description", "说明"],
        "quantity":   ["数量", "Quantity", "Qty"],
        "manufacturer":["制造商", "Manufacturer", "品牌"],
    }

    def parse(self, file_path: str) -> list[BOMItem]:
        """
        解析 BOM 文件，返回 BOMItem 列表

        Args:
            file_path: BOM 文件路径（支持 .csv / .xlsx / .xls）

        Returns:
            解析后的 BOMItem 列表
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if not SupportedFormat.is_supported(suffix):
            raise ValueError(
                f"不支持的 BOM 文件格式: {suffix}（仅支持 "
                f"{', '.join(SupportedFormat.all_extensions())}）"
            )

        if not path.exists():
            raise FileNotFoundError(f"BOM 文件不存在: {file_path}")

        if suffix == ".csv":
            df = self._read_csv(file_path)
        else:
            df = self._read_excel(file_path)

        return self._parse_dataframe(df)

    def _read_csv(self, file_path: str) -> pd.DataFrame:
        """读取 CSV 文件，自动检测编码和分隔符"""
        detected_encoding = "utf-8"

        # 单次读取探测编码和分隔符
        for encoding in BOM.CSV_ENCODINGS:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    first_line = f.readline()
                detected_encoding = encoding
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        else:
            # 所有已知编码均失败，用 utf-8 + 容错模式兜底
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    first_line = f.readline()
                detected_encoding = "utf-8"
            except Exception:
                first_line = ""
                detected_encoding = "utf-8"

        sep = "\t" if "\t" in first_line else ","
        return pd.read_csv(file_path, encoding=detected_encoding, sep=sep, dtype=str).fillna("")

    def _read_excel(self, file_path: str) -> pd.DataFrame:
        """读取 Excel 文件"""
        return pd.read_excel(file_path, dtype=str).fillna("")

    def _parse_dataframe(self, df: pd.DataFrame) -> list[BOMItem]:
        """将 DataFrame 映射为 BOMItem 列表"""
        col_map = self._map_columns(df)
        items = []

        ref_col = col_map.get("reference", "")
        val_col = col_map.get("value", "")
        pkg_col = col_map.get("package", "")
        pn_col = col_map.get("part_number", "")
        desc_col = col_map.get("description", "")
        qty_col = col_map.get("quantity", "")
        mfr_col = col_map.get("manufacturer", "")

        for row in df.itertuples(index=False):
            ref = str(getattr(row, ref_col, "")) if ref_col else ""
            if not ref or ref == "nan":
                continue
            item = BOMItem(
                reference=ref,
                value=str(getattr(row, val_col, "")) if val_col else "",
                package=str(getattr(row, pkg_col, "")) if pkg_col else "",
                part_number=str(getattr(row, pn_col, "")) if pn_col else "",
                description=str(getattr(row, desc_col, "")) if desc_col else "",
                quantity=int(getattr(row, qty_col, 1) or 1) if qty_col else 1,
                manufacturer=str(getattr(row, mfr_col, "")) if mfr_col else "",
            )
            items.append(item)

        logger.info(f"解析完成：共 {len(items)} 条 BOM 记录")
        return items

    def _map_columns(self, df: pd.DataFrame) -> dict[str, str]:
        """自动映射 DataFrame 列名到标准字段名"""
        col_map = {}
        df_cols_lower = {c.lower(): c for c in df.columns}

        for field, aliases in self._COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in df.columns:
                    col_map[field] = alias
                    break
                if alias.lower() in df_cols_lower:
                    col_map[field] = df_cols_lower[alias.lower()]
                    break

        logger.debug(f"列名映射: {col_map}")
        return col_map

    def to_dataframe(self, items: list[BOMItem]) -> pd.DataFrame:
        """将 BOMItem 列表转回 DataFrame（用于导出）"""
        return pd.DataFrame([{
            "位号": item.reference,
            "参数": item.value,
            "封装": item.package,
            "型号": item.part_number,
            "描述": item.description,
            "数量": item.quantity,
            "制造商": item.manufacturer,
        } for item in items])
