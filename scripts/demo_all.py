"""
功能演示脚本 — 展示所有已实现功能
"""
import sys
import io
from pathlib import Path

# Fix Windows GBK encoding for emoji output
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

# 2026-10-10 依赖批：绝对路径 C:\Users\lin\... 换机即崩 —— 改从本文件反推项目根；
# 同日仓库治理批：cli_prototype 随本脚本自 tests/ 挪到 scripts/（同目录直接导入）
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli_prototype import (
    CLIPrototype, CommandDispatcher, CommandContext,
    MergeCommand, ValidateCommand, DuplicateCheckCommand,
    RuleCheckCommand, HTMLBOMCommand,
)

def separator(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print("="*55)

# 初始化
cli = CLIPrototype()
bom_path = str(_PROJECT_ROOT / "tests" / "sample_bom.csv")
pos_path = str(_PROJECT_ROOT / "tests" / "sample_positions.csv")

# 1. 加载 BOM
separator("1⃣  加载 BOM 文件")
cli.load_bom(bom_path)

# 2. 加载坐标
separator("2⃣  加载坐标文件")
cli.load_positions(pos_path)

# 3. BOM 合并
separator("3⃣  BOM 同类元件合并")
dispatcher = CommandDispatcher([MergeCommand()])
print(dispatcher.dispatch_by_operation("merge_bom", cli.context, {}))

# 4. 封装校验
separator("4⃣  封装与型号校验")
dispatcher = CommandDispatcher([ValidateCommand()])
print(dispatcher.dispatch_by_operation("validate_package", cli.context, {}))

# 5. 位号查重
separator("5⃣  位号查重")
dispatcher = CommandDispatcher([DuplicateCheckCommand()])
print(dispatcher.dispatch_by_operation("check_duplicates", cli.context, {}))

# 6. 设计规则检查
separator("6⃣  设计规则检查")
dispatcher = CommandDispatcher([RuleCheckCommand()])
print(dispatcher.dispatch_by_operation("check_rule", cli.context, {}))

# 7. HTML BOM 生成
separator("7⃣  生成交互式 HTML BOM")
dispatcher = CommandDispatcher([HTMLBOMCommand()])
print(dispatcher.dispatch_by_operation("generate_html_bom", cli.context, {}))

# 8. 本地关键词匹配
separator("8⃣  自然语言关键词匹配")
all_handlers = [MergeCommand(), ValidateCommand(), DuplicateCheckCommand(), RuleCheckCommand()]
dispatcher = CommandDispatcher(all_handlers)
for cmd in ["合并", "校验封装", "检查重复", "查看规则"]:
    result = dispatcher.dispatch_by_local(cmd, cli.context)
    status = "已匹配" if result else "未匹配"
    print(f"  {status}  \"{cmd}\"")

# 9. BOM 统计
separator("9⃣  BOM 元件分类统计")
cli._print_bom_summary()

print(f"\n{'='*55}")
print("  全部功能演示完毕！")
print("="*55)
