---
name: code-style
description: 项目 Python 代码风格规范。编写或修改任何 Python 代码时必须遵守。
---

# EDA AI 助手 — Python 代码风格

## 文件结构

1. 模块首行：简短中文 docstring 说明模块用途
2. 导入顺序：标准库 → 第三方库 → 项目内部，每组之间空行分隔
3. 模块级 `logger = logging.getLogger(__name__)` 放在导入区下方

## 类型标注

- 所有函数/方法必须有类型标注（参数和返回值）
- 可空参数用 `Optional[...]`
- 泛型容器标注详细类型，如 `dict[str, list[BOMItem]]`

## 命名

| 对象 | 风格 | 示例 |
|------|------|------|
| 类名 | PascalCase | `BOMDuplicateChecker` |
| 函数/方法 | snake_case | `get_merge_report` |
| 变量 | snake_case | `ref_to_items` |
| 常量 | UPPER_SNAKE | `_TEXT_FIELDS` |
| 私有方法 | `_` 前缀 | `_group_references` |
| 类级配置 | UPPER_SNAKE 类属性 | `PASSIVE_KEYWORDS` |

## 注释与文档

- **不要**大段 docstring 解释参数/返回值（类型标注已经说明）
- 只在非显而易见的逻辑处加注释（WHY，不是 WHAT）
- 类内方法分组用 `# ── 分组名 ──` 分隔线
- 大块区域用 `# ════════ 区域名 ════════` 分隔

## 代码组织

- 每个类尽量单一职责
- 重复代码立即提取为私有方法，不要写三遍以上
- 多个 if-elif 分支 → 考虑用字典/元组 dispatch table
- dispatch table 用方法名字符串 + `getattr(self, name)`，不要用 lambda（类定义时无法绑定实例）

## 方法设计

- 函数尽量短小（20 行以内）
- 输入校验尽早 return/raise，减少嵌套
- 用 `@staticmethod` 标注无状态工具方法

## 字符串

- 面向用户的报告/消息用中文
- 日志用中文
- 代码标识符用英文

## 示例

```python
"""BOM 元件合并引擎"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .parser import BOMItem
from ..constants import BOM

logger = logging.getLogger(__name__)


class BOMMerger:
    """BOM 同类元件合并引擎"""

    def __init__(self, tolerance: float = BOM.DEFAULT_MERGE_TOLERANCE):
        self.tolerance = tolerance

    def merge(self, items: list[BOMItem]) -> list[MergedBOMItem]:
        if not items:
            raise BOMEmptyError("无法合并空的 BOM 列表")

        groups: dict[tuple[str, str, str], MergedBOMItem] = {}

        for item in items:
            key = self._group_key(item)
            if key in groups:
                existing = groups[key]
                existing.total_quantity += item.quantity
                existing.references.extend(item.reference_list)
            else:
                groups[key] = MergedBOMItem(
                    part_number=item.part_number,
                    package=item.package,
                    value=item.value,
                    total_quantity=item.quantity,
                    references=item.reference_list.copy(),
                    description=item.description,
                    manufacturer=item.manufacturer,
                )

        return sorted(groups.values(), key=lambda m: (m.part_number, m.package))
```
