"""
命令行原型 — Agent + BOM 全链路集成
重构版：策略模式消除 if-else，命令注册表解耦路由
"""

import json
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent.llm_client import LLMClient
from src.agent.prompt_templates import PromptTemplates
from src.bom.parser import BOMParser, BOMItem
from src.bom.merger import BOMMerger
from src.bom.validator import BOMValidator
from src.bom.checker import BOMDuplicateChecker
from src.interfaces.eda_adapter import LCEDAAdapter
from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  策略模式：命令处理 (替代 if-elif 链)
# ══════════════════════════════════════════════════════


@dataclass
class CommandContext:
    """命令执行上下文"""
    bom_items: list[BOMItem] = field(default_factory=list)
    positions: dict = field(default_factory=dict)
    bom_file: str | None = None


class CommandHandler(ABC):
    """命令处理器抽象基类 — 策略接口"""

    @property
    @abstractmethod
    def operation_name(self) -> str:
        """AI 解析出的操作名"""
        ...

    @abstractmethod
    def execute(self, context: CommandContext, params: dict) -> str:
        """执行命令，返回报告"""
        ...

    @property
    def local_keywords(self) -> list[str]:
        """本地匹配关键词"""
        return []

    def matches_local(self, user_input: str) -> bool:
        return _contains_any(user_input, self.local_keywords)


class MergeCommand(CommandHandler):
    @property
    def operation_name(self) -> str:
        return "merge_bom"

    @property
    def local_keywords(self) -> list[str]:
        return ["合并", "merge", "整理"]

    def execute(self, context: CommandContext, params: dict) -> str:
        merger = BOMMerger()
        merged = merger.merge(context.bom_items)
        return merger.get_merge_report(context.bom_items, merged)


class ValidateCommand(CommandHandler):
    @property
    def operation_name(self) -> str:
        return "validate_package"

    @property
    def local_keywords(self) -> list[str]:
        return ["校验", "验证", "封装", "validate"]

    def execute(self, context: CommandContext, params: dict) -> str:
        validator = BOMValidator()
        results = validator.validate(context.bom_items)
        return validator.get_validation_report(results)


class DuplicateCheckCommand(CommandHandler):
    @property
    def operation_name(self) -> str:
        return "check_duplicates"

    @property
    def local_keywords(self) -> list[str]:
        return ["重复", "查重", "duplicate", "位号"]

    def execute(self, context: CommandContext, params: dict) -> str:
        checker = BOMDuplicateChecker()
        duplicates = checker.check(context.bom_items)
        return checker.get_report(duplicates)


class FilterCommand(CommandHandler):
    @property
    def operation_name(self) -> str:
        return "filter_components"

    def execute(self, context: CommandContext, params: dict) -> str:
        keyword = params.get("keyword", "")
        matched = _filter_items(context.bom_items, keyword)
        if not matched:
            return "🔍 未找到匹配项"
        lines = [f"🔍 筛选结果 ({len(matched)} 条):"]
        for item in matched:
            lines.append(
                f"   {item.reference:15s} {item.value:10s} "
                f"{item.package:10s} {item.part_number}"
            )
        return "\n".join(lines)


class RuleCheckCommand(CommandHandler):
    @property
    def operation_name(self) -> str:
        return "check_rule"

    @property
    def local_keywords(self) -> list[str]:
        return ["规则", "rule", "去耦", "信号"]

    def execute(self, context: CommandContext, params: dict) -> str:
        from src.rules.checker import DesignRuleChecker
        checker = DesignRuleChecker()
        violations = checker.check_all(context.bom_items, context.positions)
        return checker.get_report(violations)


class HTMLBOMCommand(CommandHandler):
    @property
    def operation_name(self) -> str:
        return "generate_html_bom"

    def execute(self, context: CommandContext, params: dict) -> str:
        output_path = params.get(
            "output_path", str(PROJECT_ROOT / "output" / "ibom.html")
        )
        from src.html_bom.generator import HTMLBOMGenerator, HTMLBOMConfig

        title = (
            f"BOM — {Path(context.bom_file).stem}"
            if context.bom_file
            else "EDA AI BOM"
        )
        generator = HTMLBOMGenerator(HTMLBOMConfig(title=title))
        generator.generate(context.bom_items, context.positions, output_path)
        return f"🌐 HTML BOM 已生成: {output_path}"


# ── 纯函数工具 ──

def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in keywords)


def _build_search_text(item: BOMItem) -> str:
    return (
        f"{item.reference} {item.value} {item.package} "
        f"{item.part_number} {item.description}"
    ).lower()


def _filter_items(items: list[BOMItem], keyword: str) -> list[BOMItem]:
    keyword_lower = keyword.lower()
    return [item for item in items if keyword_lower in _build_search_text(item)]


def _extract_json(text: str) -> dict | None:
    """从 AI 回复中提取 JSON 块"""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        print(f"\n🤖 AI 回复:\n{text}\n")
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        print(f"\n⚠️ AI 返回格式异常:\n{text}\n")
        return None


# ══════════════════════════════════════════════════════
#  命令注册表 — 替代 if-elif 路由
# ══════════════════════════════════════════════════════


class CommandDispatcher:
    """命令分发器 — 注册表模式"""

    def __init__(self, handlers: list[CommandHandler]):
        self._by_operation: dict[str, CommandHandler] = {
            h.operation_name: h for h in handlers
        }
        self._by_local = [h for h in handlers if h.local_keywords]

    def dispatch_by_operation(
        self, operation: str, context: CommandContext, params: dict
    ) -> str | None:
        """按 AI 操作名分发"""
        handler = self._by_operation.get(operation)
        if handler is None:
            return None
        return self._run_and_format(handler, context, params)

    def dispatch_by_local(
        self, user_input: str, context: CommandContext
    ) -> str | None:
        """按本地关键词分发"""
        for handler in self._by_local:
            if handler.matches_local(user_input):
                return self._run_and_format(handler, context, {})
        return None

    @staticmethod
    def _run_and_format(
        handler: CommandHandler, context: CommandContext, params: dict
    ) -> str:
        separator = "─" * 50
        report = handler.execute(context, params)
        return f"{separator}\n{report}\n{separator}"


# ══════════════════════════════════════════════════════
#  Shell 命令定义
# ══════════════════════════════════════════════════════


@dataclass
class ShellCommand:
    """Shell 命令描述"""
    name: str
    action: Callable[[], bool]  # 返回 True=继续, False=退出
    help_text: str


class CLIPrototype:
    """命令行交互原型"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.llm.api_key
        self.agent = LLMClient(
            api_key=self.api_key,
            base_url=config.llm.base_url,
            model=config.llm.model,
            provider=config.llm.provider,
        ) if self.api_key else None
        self.parser = BOMParser()
        self.eda = LCEDAAdapter()
        self.context = CommandContext()
        self._dispatcher = CommandDispatcher([
            MergeCommand(), ValidateCommand(), DuplicateCheckCommand(),
            FilterCommand(), RuleCheckCommand(), HTMLBOMCommand(),
        ])
        self._shell = self._build_shell()

    # ── 文件加载 ──

    def load_bom(self, file_path: str) -> bool:
        try:
            self.context.bom_items = self.parser.parse(file_path)
            self.context.bom_file = file_path
            print(f"\n✅ 已加载 BOM: {Path(file_path).name}")
            print(f"   共 {len(self.context.bom_items)} 条物料记录\n")
            self._print_bom_summary()
            return True
        except Exception as error:
            print(f"\n❌ 加载失败: {error}\n")
            return False

    def load_positions(self, file_path: str) -> bool:
        try:
            self.context.positions = self.eda.get_positions(file_path)
            print(f"\n✅ 已加载坐标: {Path(file_path).name}")
            print(f"   共 {len(self.context.positions)} 个位号坐标\n")
            return True
        except Exception as error:
            print(f"\n❌ 加载失败: {error}\n")
            return False

    # ── AI 处理 ──

    def process_with_ai(self, user_input: str):
        if not self.agent:
            self._fallback_local(user_input)
            return
        if not self.context.bom_items:
            print("\n⚠️  请先加载 BOM 文件")
            return

        print("\n🤖 AI Agent 思考中...")
        try:
            parsed = self._parse_via_ai(user_input)
            if parsed is None:
                return
            operation = parsed.get("operation", "")
            print(f"\n🤖 AI 理解: {parsed.get('explanation', '')}")
            print(f"   执行操作: {operation}\n")
            report = self._dispatcher.dispatch_by_operation(
                operation, self.context, parsed.get("params", {})
            )
            print(report or f"⚠️  未知操作: {operation}")
        except Exception as error:
            logger.exception("AI 处理失败")
            print(f"\n❌ AI 处理异常: {error}，回退本地...")
            self._fallback_local(user_input)

    def _parse_via_ai(self, user_input: str) -> dict | None:
        system_prompt = PromptTemplates.get_system_prompt("bom")
        prompt = PromptTemplates.COMMAND_PARSE.format(user_command=user_input)
        raw = self.agent.chat(prompt, system_prompt=system_prompt)
        return _extract_json(raw)

    def _fallback_local(self, user_input: str):
        report = self._dispatcher.dispatch_by_local(user_input, self.context)
        print(report or "🤔 无法识别指令，请尝试: 合并BOM / 校验封装 / 检查重复")

    # ── Shell 命令系统 ──

    def _build_shell(self) -> dict[str, ShellCommand]:
        def report_action(operation: str) -> Callable[[], bool]:
            def action() -> bool:
                result = self._dispatcher.dispatch_by_operation(
                    operation, self.context, {}
                )
                print(result or "⚠️  请先加载 BOM 文件")
                return True
            return action

        return {
            "quit":   ShellCommand("quit", lambda: False, "退出程序"),
            "help":   ShellCommand("help", lambda: (self._print_help(), True)[1], "显示帮助"),
            "merge":  ShellCommand("merge",  report_action("merge_bom"),         "合并 BOM"),
            "validate": ShellCommand("validate", report_action("validate_package"), "封装校验"),
            "dup":    ShellCommand("dup",    report_action("check_duplicates"),  "位号查重"),
            "rule":   ShellCommand("rule",   report_action("check_rule"),        "规则检查"),
            "html":   ShellCommand("html",   report_action("generate_html_bom"), "生成HTML BOM"),
            "stat":   ShellCommand("stat",   lambda: (self._print_bom_summary(), True)[1], "元件统计"),
        }

    _PREFIX_COMMANDS = (
        ("load ", lambda self, arg: self.load_bom(arg)),
        ("pos ",  lambda self, arg: self.load_positions(arg)),
        ("list",  lambda self, arg: self._handle_list("list " + arg if arg else "list")),
    )

    def _dispatch_shell_command(self, raw_input: str) -> bool:
        cmd = raw_input.strip()
        if not cmd:
            return True
        lowered = cmd.lower()

        for prefix, handler in self._PREFIX_COMMANDS:
            if lowered.startswith(prefix):
                arg = cmd[len(prefix):].strip()
                return handler(self, arg)

        shell_cmd = self._shell.get(lowered)
        if shell_cmd:
            return shell_cmd.action()

        self.process_with_ai(cmd)
        return True

    def _handle_list(self, raw: str):
        max_display = 10
        parts = raw.split()
        if len(parts) > 1 and parts[1].isdigit():
            max_display = int(parts[1])
        for item in self.context.bom_items[:max_display]:
            print(
                f"  {item.reference:15s} {item.value:10s} "
                f"{item.package:10s} {item.part_number}"
            )

    # ── 辅助 ──

    def _print_bom_summary(self):
        from collections import Counter
        prefixes = Counter(
            "".join(c for c in item.reference.split(",")[0] if c.isalpha())
            for item in self.context.bom_items
        )
        print("   元件分类:")
        for prefix, count in sorted(prefixes.items()):
            print(f"     {prefix}: {count} 个")

    def _print_help(self):
        print("""
╔══════════════════════════════════════════════════╗
║            EDA AI 智能助手 — 使用帮助              ║
╠══════════════════════════════════════════════════╣
║  load bom.csv    加载立创EDA导出的BOM文件         ║
║  pos pos.csv     加载坐标文件(Pick & Place)       ║
║  merge           合并BOM同类元件                  ║
║  validate        校验封装与型号匹配               ║
║  dup             检查重复位号                     ║
║  rule            执行PCB设计规则检查               ║
║  html            生成交互式HTML BOM               ║
║  stat            显示BOM元件分类统计               ║
║  list [N]        列出BOM记录                      ║
║                                                   ║
║  AI 模式:                                          ║
║  "合并BOM中所有10k电阻"  "检查电容封装是否正确"     ║
║  "找出所有运放的位号"    "检查去耦电容是否足够"     ║
╚══════════════════════════════════════════════════╝
""")

    def run_interactive(self):
        self._print_welcome()
        while True:
            try:
                raw = input("\n💬 > ")
                if not self._dispatch_shell_command(raw):
                    print("👋 再见！")
                    break
            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except Exception as error:
                logger.exception("命令执行异常")
                print(f"❌ 出错: {error}")

    def _print_welcome(self):
        print("\n" + "=" * 55)
        print("  🤖 EDA AI 智能助手 — 命令行原型")
        print("=" * 55)
        for cmd in self._shell.values():
            print(f"  {cmd.name:<14s} {cmd.help_text}")
        print("─" * 55)
        if self.agent:
            print(f"✅ {self.agent.provider_label} Agent 已就绪")
        else:
            print("⚠️  未配置 LLM API，使用本地规则引擎。")


def _setup_console():
    """Ensure the Windows console can handle emoji/unicode output."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main():
    _setup_console()

    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("用法: python cli.py [--api-key YOUR_KEY] [bom_file.csv]")
        return

    api_key = None
    bom_to_load = None
    args = iter(sys.argv[1:])
    for arg in args:
        if arg == "--api-key":
            api_key = next(args, None)
        elif arg.endswith((".csv", ".xlsx", ".xls")):
            bom_to_load = arg

    cli = CLIPrototype(api_key)
    if bom_to_load:
        cli.load_bom(bom_to_load)
    cli.run_interactive()


if __name__ == "__main__":
    main()
