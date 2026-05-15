"""
BOM 封装与型号校验器 — 支持动态注册封装规则
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .parser import BOMItem
from ..constants import BOM

logger = logging.getLogger(__name__)


# ══════════════════ 内置封装规则（可扩展） ══════════════════

_BUILTIN_PACKAGE_RULES: dict[str, list[str]] = {
    "STM32F103C8T6":  ["LQFP-48"],   "STM32F103CBT6":  ["LQFP-48"],
    "STM32F103RCT6":  ["LQFP-64"],   "STM32F407VGT6":  ["LQFP-100"],
    "STM32F103C6T6":  ["LQFP-48"],   "ATmega328P":     ["TQFP-32", "DIP-28"],
    "ESP32":          ["QFN-48"],     "ESP8266":        ["QFN-32"],
    "Raspberry Pi Pico": ["DIP-40 模块"],
    "LM358":          ["SOP-8", "DIP-8", "MSOP-8"],
    "LM324":          ["SOP-14", "DIP-14"],
    "TL084":          ["SOP-14", "DIP-14"],
    "OP07":           ["SOP-8", "DIP-8"],
    "AD620":          ["SOP-8", "DIP-8"],
    "INA128":         ["SOP-8", "DIP-8"],
    "AMS1117-3.3":    ["SOT-223"],    "AMS1117-5.0":    ["SOT-223"],
    "LM7805":         ["TO-220"],     "LM2596":         ["TO-220", "TO-263"],
    "MP1584":         ["SOP-8"],      "TPS5430":        ["SOP-8"],
    "CH340G":         ["SOP-16"],     "CH340C":         ["SOP-16"],
    "CP2102":         ["QFN-28"],     "MAX3232":        ["SOP-16", "TSSOP-16"],
    "SN65HVD230":     ["SOP-8"],      "SP3485":         ["SOP-8"],
    "MPU6050":        ["QFN-24"],     "BMP280":         ["LGA-8"],
    "DHT11":          ["DIP-4 模块"], "DS18B20":        ["TO-92"],
}

_BUILTIN_PACKAGE_ALIASES: dict[str, list[str]] = {
    "0603":    ["0603", "0603(1608)", "1608"],
    "0805":    ["0805", "0805(2012)", "2012"],
    "1206":    ["1206", "1206(3216)", "3216"],
    "SOT-23":  ["SOT-23", "SOT23", "SOT-23-3"],
    "SOT-223": ["SOT-223", "SOT223"],
    "SOP-8":   ["SOP-8", "SOIC-8", "SO-8", "SOP8"],
    "SOP-16":  ["SOP-16", "SOIC-16", "SO-16"],
    "LQFP-48": ["LQFP-48", "LQFP48"],
    "LQFP-64": ["LQFP-64", "LQFP64"],
    "TO-220":  ["TO-220", "TO220"],
    "TO-92":   ["TO-92", "TO92"],
}


@dataclass
class ValidationResult:
    """单条校验结果"""
    item: BOMItem
    is_valid: bool
    expected_package: str = ""
    suggestion: str = ""
    severity: str = "info"


class BOMValidator:
    """BOM 封装与型号匹配校验器 — 支持运行时扩展"""

    PASSIVE_KEYWORDS = [kw.lower() for kw in BOM.PASSIVE_KEYWORDS]

    # 类级别规则注册表（跨实例共享）
    _rules: dict[str, list[str]] = {}
    _aliases: dict[str, list[str]] = {}
    _reverse_aliases: dict[str, str] = {}  # alias → canonical
    _loaded: bool = False

    def __init__(self):
        BOMValidator._load_builtins()

    # ── 扩展点：运行时注册规则 ──

    @classmethod
    def register_package_rule(cls, part_number: str, expected_packages: list[str]):
        """动态注册封装规则。

        示例:
            BOMValidator.register_package_rule("ESP32-S3", ["QFN-56"])
        """
        cls._rules[part_number.upper()] = [p.strip().upper() for p in expected_packages]

    @classmethod
    def register_package_alias(cls, canonical: str, aliases: list[str]):
        """动态注册封装别名。

        示例:
            BOMValidator.register_package_alias("QFN-56", ["QFN56", "QFN56EP"])
        """
        cls._aliases[canonical.upper()] = [a.strip().upper() for a in aliases]

    @classmethod
    def _load_builtins(cls):
        if cls._loaded:
            return
        cls._loaded = True
        for pn, pkgs in _BUILTIN_PACKAGE_RULES.items():
            cls._rules[pn.upper()] = [p.upper() for p in pkgs]
        for canonical, als in _BUILTIN_PACKAGE_ALIASES.items():
            canonical_upper = canonical.upper()
            aliases_upper = [a.upper() for a in als]
            cls._aliases[canonical_upper] = aliases_upper
            for alias in aliases_upper:
                cls._reverse_aliases[alias] = canonical_upper

    # ── 公共接口 ──

    def validate(self, items: list[BOMItem]) -> list[ValidationResult]:
        if not items:
            return []
        results = [self._validate_item(item) for item in items]
        valid = sum(1 for r in results if r.is_valid)
        logger.info("校验完成: %d/%d 通过 (%.1f%%)", valid, len(results),
                     valid / len(results) * 100 if results else 0)
        return results

    # ── 内部方法 ──

    def _validate_item(self, item: BOMItem) -> ValidationResult:
        if self._is_passive(item):
            return ValidationResult(item=item, is_valid=True)

        expected = self._lookup_package(item.part_number)
        if expected is None:
            return self._build_unknown_result(item)
        if self._package_matches(item.package, expected):
            return ValidationResult(item=item, is_valid=True)
        return self._build_mismatch_result(item, expected)

    def _is_passive(self, item: BOMItem) -> bool:
        search = f"{item.description}".lower()
        return any(kw in search for kw in self.PASSIVE_KEYWORDS)

    def _lookup_package(self, part_number: str) -> Optional[list[str]]:
        upper = part_number.upper()
        if upper in self._rules:
            return self._rules[upper]
        for key, pkgs in self._rules.items():
            if upper.startswith(key):
                return pkgs
        return None

    def _build_unknown_result(self, item: BOMItem) -> ValidationResult:
        return ValidationResult(
            item=item, is_valid=True,
            suggestion=f"型号 {item.part_number} 未在封装库中，请手动确认",
            severity="info",
        )

    def _build_mismatch_result(self, item: BOMItem, expected: list[str]) -> ValidationResult:
        joined = " / ".join(expected)
        return ValidationResult(
            item=item, is_valid=False, expected_package=joined,
            suggestion=f"位号 {item.reference}：型号 {item.part_number} 的封装应为 {joined}，当前为 {item.package}",
            severity="error",
        )

    def _package_matches(self, actual: str, expected_list: list[str]) -> bool:
        actual_norm = actual.strip().upper()
        return actual_norm in self._expand_aliases(expected_list)

    def _expand_aliases(self, package_list: list[str]) -> set[str]:
        result: set[str] = set()
        for pkg in package_list:
            pkg_norm = pkg.strip().upper()
            result.add(pkg_norm)
            # 通过反向映射展开别名
            canonical = self._reverse_aliases.get(pkg_norm)
            if canonical is not None:
                result.update(self._aliases.get(canonical, ()))
        return result

    # ── 报告 ──

    def get_validation_report(self, results: list[ValidationResult]) -> str:
        if not results:
            return f"{BOM.REPORT_DOUBLE_SEP}\n  无 BOM 数据可校验\n{BOM.REPORT_DOUBLE_SEP}"

        errors = [r for r in results if r.severity == "error"]
        warnings = [r for r in results if r.severity == "warning"]

        lines = [
            BOM.REPORT_DOUBLE_SEP,
            "        BOM 封装校验报告",
            BOM.REPORT_DOUBLE_SEP,
            f"校验总数：{len(results)}",
            f"✅ 通过：{sum(1 for r in results if r.is_valid)}",
            f"❌ 错误：{len(errors)}",
            f"⚠️  警告：{len(warnings)}",
            BOM.REPORT_SEPARATOR,
        ]

        for severity, emoji, items in [
            ("error", "❌", errors),
            ("warning", "⚠️ ", warnings),
        ]:
            if items:
                lines.append(f"\n【{severity}项】")
                for r in items:
                    lines.append(f"  {emoji} {r.suggestion}")

        lines.append(BOM.REPORT_DOUBLE_SEP)
        return "\n".join(lines)
