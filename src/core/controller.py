"""
Application controller — UI-agnostic orchestration layer.

All business logic lives here. GUI and CLI consume this single API,
so feature parity is guaranteed across interfaces.
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.agent.llm_client import LLMClient
from src.agent.prompt_templates import PromptTemplates
from src.bom.checker import BOMDuplicateChecker
from src.bom.merger import BOMMerger
from src.bom.parser import BOMItem, BOMParser
from src.bom.validator import BOMValidator
from src.config import config
from src.html_bom.generator import HTMLBOMConfig, HTMLBOMGenerator
from src.interfaces.eda_adapter import LCEDAAdapter
from src.rules.checker import DesignRuleChecker

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════
#  Shared context — single source of truth for session state
# ══════════════════════════════════════════════════════


@dataclass
class CommandContext:
    """Mutable session state shared across all operations."""

    bom_items: list = field(default_factory=list)
    positions: dict = field(default_factory=dict)
    bom_file: Optional[str] = None

    @property
    def has_data(self) -> bool:
        return bool(self.bom_items)


# ══════════════════════════════════════════════════════
#  Controller
# ══════════════════════════════════════════════════════


class AppController:
    """Core controller — pure logic, zero UI dependencies.

    Both ``MainWindow`` (GUI) and ``CLIPrototype`` (CLI) consume this class,
    guaranteeing identical behaviour regardless of the interface.
    """

    # ── Lifecycle ──

    def __init__(self, api_key: Optional[str] = None):
        resolved = api_key or config.llm.api_key
        self.agent = LLMClient(
            api_key=resolved,
            base_url=config.llm.base_url,
            model=config.llm.model,
            provider=config.llm.provider,
        ) if self._key_valid(resolved) else None
        self.parser = BOMParser()
        self.eda = LCEDAAdapter()
        self.context = CommandContext()

    @staticmethod
    def _key_valid(key: Optional[str]) -> bool:
        return bool(key and key not in ("", "your_api_key_here", "sk-"))

    # ══════════════════════════════════════════════════
    #  File I/O
    # ══════════════════════════════════════════════════

    def load_bom(self, file_path: str) -> tuple[int, str]:
        """Parse a BOM file, populate context, return (count, message)."""
        self.context.bom_items = self.parser.parse(file_path)
        self.context.bom_file = file_path
        name = Path(file_path).name
        n = len(self.context.bom_items)
        logger.info("BOM loaded: %s (%d items)", name, n)
        return n, f"✅ 已加载 BOM: {name}\n共 {n} 条物料记录"

    def load_positions(self, file_path: str) -> tuple[int, str]:
        """Parse a Pick & Place file, return (count, message)."""
        self.context.positions = self.eda.get_positions(file_path)
        name = Path(file_path).name
        n = len(self.context.positions)
        logger.info("Positions loaded: %s (%d entries)", name, n)
        return n, f"✅ 已加载坐标: {name}\n共 {n} 个位号坐标"

    # ══════════════════════════════════════════════════
    #  BOM operations — each returns a formatted report
    # ══════════════════════════════════════════════════

    def merge_bom(self) -> str:
        merger = BOMMerger()
        merged = merger.merge(self.context.bom_items)
        return merger.get_merge_report(self.context.bom_items, merged)

    def validate_packages(self) -> str:
        validator = BOMValidator()
        results = validator.validate(self.context.bom_items)
        return validator.get_validation_report(results)

    def check_duplicates(self) -> str:
        checker = BOMDuplicateChecker()
        duplicates = checker.check(self.context.bom_items)
        return checker.get_report(duplicates)

    def generate_html_bom(self, output_path: Optional[str] = None) -> str:
        if output_path is None:
            out_dir = Path(__file__).parent.parent.parent / "output"
            out_dir.mkdir(exist_ok=True)
            output_path = str(out_dir / "ibom.html")

        title = (
            f"BOM — {Path(self.context.bom_file).stem}"
            if self.context.bom_file
            else "EDA AI BOM"
        )
        generator = HTMLBOMGenerator(HTMLBOMConfig(title=title))
        generator.generate(self.context.bom_items, self.context.positions, output_path)
        logger.info("HTML BOM generated: %s", output_path)
        return f"🌐 HTML BOM 已生成:\n{output_path}"

    def check_design_rules(self) -> str:
        checker = DesignRuleChecker()
        violations = checker.check_all(self.context.bom_items, self.context.positions)
        return checker.get_report(violations)

    def get_bom_summary(self) -> dict:
        """Return per-prefix component statistics."""
        prefixes: dict[str, int] = {}
        for item in self.context.bom_items:
            ref0 = item.reference.split(",")[0].strip()
            pfx = "".join(c for c in ref0 if c.isalpha())
            prefixes[pfx] = prefixes.get(pfx, 0) + 1
        return {"total": len(self.context.bom_items), "by_prefix": dict(sorted(prefixes.items()))}

    # ══════════════════════════════════════════════════
    #  Natural-language processing
    # ══════════════════════════════════════════════════

    def is_agent_available(self) -> bool:
        return self.agent is not None

    def process_input(self, user_input: str) -> str:
        """Entry point for user messages.  Tries AI first, falls back to local keywords."""
        if not self.context.has_data:
            return "⚠️ 请先导入 BOM 文件再输入指令。"

        if self.is_agent_available():
            result = self._try_ai(user_input)
            if result is not None:
                return result

        return self._local_fallback(user_input)

    def process_input_stream(
        self, user_input: str, on_token: Callable[[str], None]
    ) -> str:
        """Streaming variant — ``on_token`` receives each token as it arrives."""
        if not self.context.has_data:
            return "⚠️ 请先导入 BOM 文件再输入指令。"

        if self.is_agent_available():
            result = self._try_ai_stream(user_input, on_token)
            if result is not None:
                return result

        return self._local_fallback(user_input)

    # ── AI helpers ──

    def _try_ai(self, user_input: str) -> Optional[str]:
        try:
            parsed = self._parse_via_ai(user_input)
            if parsed is None:
                return None
            return self._execute_operation(parsed)
        except Exception:
            logger.exception("AI processing failed, falling back to local")
            return None

    def _try_ai_stream(
        self, user_input: str, on_token: Callable[[str], None]
    ) -> Optional[str]:
        try:
            system = PromptTemplates.get_system_prompt("bom")
            prompt = PromptTemplates.COMMAND_PARSE.format(user_command=user_input)
            raw = self.agent.chat_stream(prompt, system_prompt=system, on_token=on_token)
            parsed = self._extract_json(raw)
            if parsed is None:
                return None
            return self._execute_operation(parsed)
        except Exception:
            logger.exception("AI streaming failed, falling back to local")
            return None

    def _parse_via_ai(self, user_input: str) -> Optional[dict]:
        system = PromptTemplates.get_system_prompt("bom")
        prompt = PromptTemplates.COMMAND_PARSE.format(user_command=user_input)
        raw = self.agent.chat(prompt, system_prompt=system)
        return self._extract_json(raw)

    def _execute_operation(self, parsed: dict) -> str:
        operation = parsed.get("operation", "")
        params = parsed.get("params", {})
        explanation = parsed.get("explanation", "")

        op_map = {
            "merge_bom": self.merge_bom,
            "validate_package": self.validate_packages,
            "check_duplicates": self.check_duplicates,
            "generate_html_bom": lambda: self.generate_html_bom(
                params.get("output_path")
            ),
            "check_rule": self.check_design_rules,
            "filter_components": lambda: self._filter_components(params),
        }

        handler = op_map.get(operation)
        if handler is None:
            return (
                f"🤔 无法识别操作「{operation}」\n\n"
                "可用操作：合并BOM / 校验封装 / 检查重复 / 生成HTML BOM / 设计规则检查"
            )

        prefix = f"🤖 AI 理解: {explanation}\n\n" if explanation else ""
        return prefix + handler()

    def _filter_components(self, params: dict) -> str:
        keyword = (params.get("keyword") or "").lower()
        if not keyword:
            return "🔍 请指定筛选关键词"
        matched = [
            item for item in self.context.bom_items
            if keyword in f"{item.reference} {item.value} {item.package} {item.part_number} {item.description}".lower()
        ]
        if not matched:
            return f"🔍 未找到包含「{keyword}」的元件"
        lines = [f"🔍 筛选结果 ({len(matched)} 条):"]
        for item in matched:
            lines.append(
                f"   {item.reference:15s} {item.value:10s} "
                f"{item.package:10s} {item.part_number}"
            )
        return "\n".join(lines)

    # ── Local keyword fallback ──

    def _local_fallback(self, user_input: str) -> str:
        lowered = user_input.lower()

        checks = [
            (["合并", "merge", "整理"], self.merge_bom),
            (["校验", "验证", "封装", "validate"], self.validate_packages),
            (["重复", "查重", "duplicate", "位号"], self.check_duplicates),
            (["html", "网页"], self.generate_html_bom),
            (["规则", "rule", "去耦", "信号"], self.check_design_rules),
            (["统计", "概览", "summary"], self._summary_report),
        ]

        for keywords, handler in checks:
            if any(kw in lowered for kw in keywords):
                return handler()

        return (
            "🤔 无法识别指令。请尝试:\n"
            "• 合并 BOM  — 合并同类元件\n"
            "• 校验封装   — 检查封装型号匹配\n"
            "• 检查重复   — 检测重复位号\n"
            "• 生成 HTML  — 导出交互式 BOM\n"
            "• 设计规则   — PCB 规则检查"
        )

    def _summary_report(self) -> str:
        s = self.get_bom_summary()
        lines = [
            "=" * 50,
            "        BOM 元件统计",
            "=" * 50,
            f"总元件数：{s['total']}",
            "-" * 50,
        ]
        for pfx, count in s["by_prefix"].items():
            lines.append(f"  {pfx}: {count} 个")
        lines.append("=" * 50)
        return "\n".join(lines)

    # ── Static utility ──

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            return None
