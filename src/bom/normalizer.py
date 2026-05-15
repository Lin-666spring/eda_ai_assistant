"""
元件参数值归一化工具
将不同格式的参数值（10kΩ / 10K / 10千欧）统一为标准内部表示
独立模块，可被 merger 和 validator 共用
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedValue:
    """归一化后的参数值"""
    raw: str              # 原始输入
    component_type: str   # "R" 电阻 / "C" 电容 / "L" 电感 / "?" 未知
    base_value: float     # 以基本单位表示的数值
    original_unit: str    # 原始单位
    display: str          # 可读形式

    @property
    def category_key(self) -> str:
        """用于分组比较的标准键"""
        if self.component_type == "?":
            return f"?:{self.raw}"
        return f"{self.component_type}:{self.base_value:.4g}"


class ValueNormalizer:
    """元件参数值归一化器

    公共接口 — parser / merger / validator 均可用。
    线程安全（无状态设计）。
    """

    # ── 电阻单位映射 ──
    _RESISTOR_UNITS = {
        "MΩ": 1_000_000, "M": 1_000_000, "兆欧": 1_000_000,
        "KΩ": 1_000, "K": 1_000, "千欧": 1_000,
        "Ω": 1, "R": 1, "欧": 1, "欧姆": 1, "OHM": 1,
    }

    # ── 电容单位映射 ──
    _CAPACITOR_UNITS = {
        "F": 1, "ΜF": 1e-6, "UF": 1e-6,
        "NF": 1e-9, "PF": 1e-12,
    }

    # ── 电感单位映射 ──
    _INDUCTOR_UNITS = {
        "H": 1, "MH": 1e-3, "ΜH": 1e-6, "UH": 1e-6,
        "NH": 1e-9, "PH": 1e-12,
    }

    # 预排序（按 key 长度降序，避免短 key 误匹配长 key）
    _RESISTOR_SORTED: tuple[tuple[str, float], ...] = tuple(
        sorted(_RESISTOR_UNITS.items(), key=lambda kv: -len(kv[0]))
    )
    _CAPACITOR_SORTED: tuple[tuple[str, float], ...] = tuple(
        sorted(_CAPACITOR_UNITS.items(), key=lambda kv: -len(kv[0]))
    )
    _INDUCTOR_SORTED: tuple[tuple[str, float], ...] = tuple(
        sorted(_INDUCTOR_UNITS.items(), key=lambda kv: -len(kv[0]))
    )

    @classmethod
    def normalize(cls, raw_value: str) -> NormalizedValue:
        """
        归一化一个参数值字符串

        Args:
            raw_value: 如 "10kΩ", "100nF", "4.7μH"

        Returns:
            NormalizedValue 对象
        """
        if not raw_value or not raw_value.strip():
            return NormalizedValue(
                raw="", component_type="?", base_value=0,
                original_unit="", display="",
            )

        cleaned = raw_value.strip().upper()

        # 电阻
        result = cls._try_parse(cleaned, cls._RESISTOR_SORTED, "R", "Ω")
        if result:
            return result
        # 电容
        result = cls._try_parse(cleaned, cls._CAPACITOR_SORTED, "C", "F")
        if result:
            return result
        # 电感
        result = cls._try_parse(cleaned, cls._INDUCTOR_SORTED, "L", "H")
        if result:
            return result

        return NormalizedValue(
            raw=raw_value, component_type="?", base_value=0,
            original_unit="", display=raw_value,
        )

    @classmethod
    def are_equivalent(
        cls, value1: str, value2: str, tolerance: float = 0.05
    ) -> bool:
        """判断两个参数值是否在容差范围内等价"""
        nv1 = cls.normalize(value1)
        nv2 = cls.normalize(value2)

        if nv1.category_key == nv2.category_key:
            return True
        if nv1.component_type != nv2.component_type:
            return False
        if nv1.component_type == "?":
            return value1.strip().upper() == value2.strip().upper()

        if nv1.base_value == 0 or nv2.base_value == 0:
            return False
        diff = abs(nv1.base_value - nv2.base_value) / max(nv1.base_value, nv2.base_value)
        return diff <= tolerance

    @classmethod
    def _try_parse(
        cls, cleaned: str, sorted_units: tuple[tuple[str, float], ...],
        component_type: str, base_unit: str,
    ) -> NormalizedValue | None:
        """尝试用指定单位表解析（预排序，按 key 长度降序）"""
        for unit, multiplier in sorted_units:
            pattern = rf"^([\d]+\.?[\d]*)\s*{re.escape(unit)}$"
            m = re.match(pattern, cleaned)
            if m:
                raw_num = m.group(1)
                base_value = float(raw_num) * multiplier
                return NormalizedValue(
                    raw=cleaned,
                    component_type=component_type,
                    base_value=base_value,
                    original_unit=unit,
                    display=f"{raw_num}{base_unit}",
                )
        return None
