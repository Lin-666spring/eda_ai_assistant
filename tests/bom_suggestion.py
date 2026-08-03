"""
BOM 建议解析模块 — 将 LLM 自然语言建议转换为结构化 BOM 变更并应用。

用于 Phase B 闭环验证实验。不放入 src/ 因为属于论文实验工具。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

# BOMItem 的有效字段名
_VALID_BOM_FIELDS = {"reference", "value", "package", "part_number", "description", "quantity", "manufacturer"}


@dataclass
class BOMChange:
    """单条 BOM 变更记录，从 LLM JSON 响应中解析。"""
    reference: str          # 位号，如 "C1"
    field: str              # 修改字段: value/package/part_number/description
    old_value: str = ""     # LLM 理解的当前值
    new_value: str = ""     # LLM 建议的新值
    action: str = "replace" # replace / add / remove


@dataclass
class ParseResult:
    """LLM 建议解析结果。"""
    changes: list[BOMChange] = field(default_factory=list)
    raw_json: str = ""
    parse_error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
#  公共 API
# ═══════════════════════════════════════════════════════════════

def build_bom_change_prompt(suggestion: str, bom_items: list) -> str:
    """构建 prompt，要求 LLM 将自然语言建议转换为结构化 JSON。

    Args:
        suggestion: 原始自然语言建议文本
        bom_items: 当前 BOM 列表（用于提供参考上下文）

    Returns:
        完整的 prompt 字符串
    """
    # 构建 BOM 参考表
    bom_lines = ["| 位号 | 当前值 | 封装 |", "|------|--------|------|"]
    for item in bom_items[:50]:
        bom_lines.append(f"| {item.reference} | {item.value} | {item.package} |")

    bom_table = "\n".join(bom_lines)

    prompt = f"""你是一个PCB BOM（物料清单）解析器。请分析以下设计建议，并输出一个JSON格式的BOM变更列表。

## 你要分析的建议
{suggestion}

## 当前BOM参考（仅供参考，帮助确认位号和参数）
{bom_table}

## 输出格式要求
请严格按照以下JSON格式输出，不要添加任何解释文字：

{{
  "changes": [
    {{
      "reference": "C1",
      "field": "value",
      "old_value": "100nF",
      "new_value": "1uF 10V X7R 0603"
    }}
  ]
}}

## 字段说明
- reference: 元件位号，如 R1, C3, U2。注意C1,C2,C3是多个位号合并，请分别列出
- field: 修改的字段，可选 value / package / part_number / description
- old_value: 当前值（从建议描述中推断，如无法推断可为空字符串）
- new_value: 建议的新值

## 规则
1. 只输出JSON，不要输出任何其他文字
2. 如果建议中没有明确的BOM变更（如"检查设计"、"分析电路"等纯分析类建议），返回空的changes数组
3. 值字段（value）请保留原始单位，如"100nF"、"10kΩ"、"4.7μF"
4. 如果建议中提到多个相同变更（如"将C1、C2、C3、C6从100nF改为1μF"），请分别列出每个变更
5. 如果建议中提到移除元件（如"删除C1"），使用 "new_value": "" 并标注 field: "reference"
"""

    return prompt


def parse_llm_bom_changes(llm_response: str) -> ParseResult:
    """从 LLM 响应中提取结构化 BOM 变更。

    三级回退策略：
    1. 直接 json.loads 整个响应
    2. 提取 ```json ... ``` 代码块
    3. 提取第一个 { ... } 块

    Args:
        llm_response: LLM 原始响应文本

    Returns:
        ParseResult 对象
    """
    text = llm_response.strip()
    parsed = None

    # Strategy 1: Direct parse
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from ```json fence
    if parsed is None:
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if fence_match:
            try:
                parsed = json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

    # Strategy 3: Extract first { ... } block
    if parsed is None:
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            try:
                candidate = text[brace_start:brace_end + 1]
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                pass

    if parsed is None:
        return ParseResult(
            changes=[],
            raw_json=text[:500],
            parse_error=f"无法从LLM响应中提取有效JSON。响应前200字: {text[:200]}"
        )

    # Extract changes list
    changes_raw = parsed.get("changes", [])
    if not isinstance(changes_raw, list):
        return ParseResult(
            raw_json=json.dumps(parsed, ensure_ascii=False),
            parse_error=f"changes字段不是列表: {type(changes_raw)}"
        )

    changes = []
    for entry in changes_raw:
        if not isinstance(entry, dict):
            continue
        changes.append(BOMChange(
            reference=str(entry.get("reference", "")).strip(),
            field=str(entry.get("field", "value")).strip(),
            old_value=str(entry.get("old_value", "")).strip(),
            new_value=str(entry.get("new_value", "")).strip(),
            action=str(entry.get("action", "replace")).strip(),
        ))

    return ParseResult(
        changes=changes,
        raw_json=json.dumps(parsed, ensure_ascii=False),
    )


def validate_bom_changes(
    changes: list[BOMChange], bom_items: list
) -> tuple[list[BOMChange], list[str]]:
    """验证解析出的变更是否合法。

    Args:
        changes: LLM 解析出的变更列表
        bom_items: 原始 BOM 列表

    Returns:
        (valid_changes, warnings) 元组
    """
    # 构建位号 → BOMItem 映射
    ref_map: dict[str, object] = {}
    for item in bom_items:
        for ref in item.reference_list:
            ref_map[ref.upper()] = item

    valid = []
    warnings = []

    for change in changes:
        ref_upper = change.reference.upper()

        # 检查字段名
        if change.field not in _VALID_BOM_FIELDS:
            warnings.append(f"{change.reference}: 无效字段 '{change.field}'，跳过")
            continue

        # add 操作额外检查
        if change.action == "add":
            if not change.new_value:
                warnings.append(f"{change.reference}: add操作缺少 new_value，跳过")
                continue
            valid.append(change)
            continue

        # replace / remove 需要引用存在
        if ref_upper not in ref_map:
            warnings.append(f"{change.reference}: 位号不在BOM中，跳过")
            continue

        valid.append(change)

    return valid, warnings


def apply_bom_changes(bom_items: list, changes: list[BOMChange]) -> list:
    """应用结构化变更到 BOM 副本。

    不修改原始 bom_items。使用 dataclasses.replace() 创建新对象。

    Args:
        bom_items: 原始 BOM 列表
        changes: 已通过验证的变更列表

    Returns:
        修改后的 BOM 列表副本
    """
    from dataclasses import replace
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from src.bom.parser import BOMItem

    # Deep copy
    result = [replace(item) for item in bom_items]

    # 构建位号 → 索引映射（注意 BOMItem.reference 可能是 "R1,R2,R3"）
    ref_to_indices: dict[str, list[int]] = {}
    for idx, item in enumerate(result):
        for ref in item.reference_list:
            ref_to_indices.setdefault(ref.upper(), []).append(idx)

    for change in changes:
        ref_upper = change.reference.upper()

        if change.action == "remove":
            indices = ref_to_indices.get(ref_upper, [])
            for idx in indices:
                # 简单处理：清空值标记为已删除
                result[idx] = replace(result[idx], value="[REMOVED]", description="[REMOVED]")
            continue

        if change.action == "add":
            # 添加新元件
            new_item = BOMItem(
                reference=change.reference,
                value=change.new_value if change.field == "value" else "",
                package=change.new_value if change.field == "package" else "",
                part_number=change.new_value if change.field == "part_number" else "",
                description=change.new_value if change.field == "description" else "",
                quantity=1,
            )
            result.append(new_item)
            continue

        # replace action
        indices = ref_to_indices.get(ref_upper, [])
        if not indices:
            continue

        for idx in indices:
            kwargs = {change.field: change.new_value}
            result[idx] = replace(result[idx], **kwargs)

    return result
