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
    # 2026-09-10 新增：模型未按 prompt 约定输出、被归一化纠正的条目数
    # （如用 field="reference" + 空 new_value 代替 action:"remove"）。
    # 用于度量 schema 遵守率，论文附录可披露。
    normalized_removals: int = 0


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

    prompt = f"""你是一个PCB BOM（物料清单）解析器。请把下面的设计建议转换成结构化的 BOM 变更列表。

## 你要分析的建议
{suggestion}

## 当前BOM参考（位号的唯一权威来源：表里没有的位号 = 新元件）
{bom_table}

## 输出格式（只输出一个 JSON 对象，不要任何解释文字）
{{"changes": [ ... ]}}

changes 的每个元素必须且只能描述**一种**操作，具体是哪种由 action 字段决定。
以下三种情况各给一个完整示例，请严格照抄字段名：

（a）修改现有元件的参数 —— action 必须是 "replace"
{{"reference": "C1", "field": "value", "old_value": "100nF", "new_value": "1uF", "action": "replace"}}

（b）删除现有元件 —— action 必须是 "remove"
{{"reference": "C1", "field": "value", "old_value": "100nF", "new_value": "", "action": "remove"}}

（c）新增元件（位号必须是参考表里不存在的新位号）—— action 必须是 "add"
{{"reference": "C101", "field": "value", "old_value": "", "new_value": "100nF", "action": "add"}}

## 硬性规则（违反会导致该条变更被丢弃）
1. 只输出 JSON，不要输出任何解释文字，不要使用 markdown 代码围栏。
2. `action` 必须显式给出，只能是 "replace" / "add" / "remove" 三者之一，不允许省略。
3. `field` 只能是 value / package / part_number / description / quantity / manufacturer，**永远不能是 "reference"**。
   删除元件只能用 action:"remove" 表达，新增元件只能用 action:"add" 表达；
   禁止用 field:"reference"、也禁止用空的 new_value 来暗示删除或新增。
4. 纯分析类建议（"检查设计"、"分析电路"、"确认是否符合规范"等不改变 BOM 的建议）返回 {{"changes": []}}。
   不要为了凑数编造变更。
5. `new_value` 只填纯参数值（"100nF"、"10kΩ"、"4.7μF"），不要填 "100nF 10V X7R 0603" 这类复合规格串。
6. **每个新元件只输出一条 add**：field 固定为 "value"，new_value 填纯参数值。
   不要为同一个新元件再输出一条 field:"package" 的 add —— 规则引擎只解析 value，
   多输出一条会把一个元件变成两个（2026-09-10 实验实测到的缺陷）。
7. 合并位号（"C1,C2,C3"）必须拆成多条，每个位号一条。
8. 新增元件的位号必须**在参考表中不存在**，也不能与参考表中任何位号重复；建议从 C101 / R101 / U101 起编号。
9. 不要用参考表里不存在的位号做 replace —— 需要新元件时用 action:"add"。
"""

    return prompt


def build_correction_prompt(
    suggestion: str,
    current_changes: list[BOMChange],
    new_violations: list,
    original_bom: list,
    baseline_rules: Optional[set] = None,
    baseline_violation_count: Optional[int] = None,
    modified_violation_count: Optional[int] = None,
    baseline_counts_by_rule: Optional[dict] = None,
    modified_counts_by_rule: Optional[dict] = None,
    baseline_score: Optional[float] = None,
    modified_score: Optional[float] = None,
    round_num: int = 1,
    max_rounds: int = 3,
    history: Optional[list] = None,
) -> str:
    """构建修正轮 prompt — 给 LLM 足以收敛的完整反馈。

    相比旧版（只拼规则名+描述），新版提供：
    1. 每条违规的 suggestion 字段（checker.py 生成的修复指引，含参数值）
    2. 同规则恶化对比（去耦检查等基线已有规则在删电容后暴增，旧版不可见）
    3. 全量替换语义 + 撤销授权（危险建议的正确修法是删掉变更条目，而非打补丁）
    4. action: add 文档化（补回被删除的电容是新元件，不是字段修改）
    5. 轮次历史（防止 LLM 重复上一轮已被证明无效的策略）
    6. 评分信号（cw32l010 型"0 新违规但评分下降"用例的可执行反馈）

    Args:
        suggestion: 原始建议文本
        current_changes: 本轮已应用的变更列表（将被整体替换）
        new_violations: 相对基线新出现的 DRC 违规（RuleViolation 列表）
        original_bom: 原始 BOM（供恢复 old_value）
        baseline_rules: 基线已触发的规则名集合（用于区分新规则 vs 恶化规则）
        baseline_violation_count / modified_violation_count: 总违规数对比
        baseline_counts_by_rule / modified_counts_by_rule: 同规则违规数对比
        baseline_score / modified_score: 综合评分对比
        round_num: 当前修正轮次（从 2 开始，1 是首轮）
        max_rounds: 最大轮次
        history: 前几轮摘要 [(轮次, 变更数, 新违规数, 尝试摘要), ...]
    """
    # ── 当前变更表（含 old_value，供恢复原值）──
    # 2026-09-10：改用人类可读的操作标签。此前把 canonical 变更渲染成
    # "字段=value / 操作=replace"，模型看不出自己删了元件，无法作出"撤销"决策。
    _ACTION_LABEL = {"remove": "删除该元件", "add": "新增元件"}

    def _row(c: BOMChange) -> str:
        label = _ACTION_LABEL.get(c.action) or f"修改 {c.field}"
        return (f"| {c.reference} | {label} | {c.old_value or '(见下表)'} | "
                f"{c.new_value or '(空)'} |")
    changes_rows = "\n".join(_row(c) for c in current_changes) or "(无)"
    changes_table = (
        "| 位号 | 你做的操作 | 原值 | 变更后的值 |\n"
        "|------|-----------|------|-----------|\n" + changes_rows
    )

    # ── 原始 BOM 中被变更涉及的元件当前真实值（LLM 恢复原值的依据）──
    ref_set = {c.reference.upper() for c in current_changes}
    original_rows = []
    for item in original_bom[:60]:
        for ref in item.reference_list:
            if ref.upper() in ref_set:
                original_rows.append(f"| {ref} | {item.value or '(空)'} | {item.package} |")
                break
    if not original_rows:
        for item in original_bom[:50]:
            original_rows.append(f"| {item.reference.split(',')[0]} | {item.value or '(空)'} | {item.package} |")
    original_table = (
        "| 位号 | 原始值 | 封装 |\n|------|--------|------|\n"
        + "\n".join(original_rows)
    )

    # ── 新违规明细（含修复指引）──
    def _violation_line(v) -> str:
        sev = v.severity.value if hasattr(v.severity, "value") else str(v.severity)
        loc = f" @ {v.location}" if getattr(v, "location", "") else ""
        fix = f"\n    修法: {v.suggestion}" if getattr(v, "suggestion", "") else ""
        return f"- [{sev}] {v.rule_name}{loc}: {v.description}{fix}"
    violation_desc = "\n".join(_violation_line(v) for v in new_violations[:15]) or "(无)"

    # ── 同规则恶化（基线已有的规则在变更后违规数增加）──
    worsened_lines = []
    if baseline_counts_by_rule and modified_counts_by_rule:
        for rule, cnt in modified_counts_by_rule.items():
            base_cnt = baseline_counts_by_rule.get(rule, 0)
            if cnt > base_cnt:
                worsened_lines.append(f"- {rule}: 基线 {base_cnt} 条 → 现在 {cnt} 条（恶化 +{cnt - base_cnt}）")
    worsened_section = ""
    if worsened_lines:
        worsened_section = (
            "\n## 现有规则恶化（这些规则基线就有，但你的变更使违规数增加）\n"
            + "\n".join(worsened_lines[:10]) + "\n"
        )

    # ── 评分信号 ──
    score_section = ""
    if baseline_score is not None and modified_score is not None and modified_score < baseline_score:
        score_section = (
            f"\n## 综合评分\n"
            f"基线 {baseline_score:.1f} 分 → 变更后 {modified_score:.1f} 分"
            f"（下降 {baseline_score - modified_score:.1f} 分）。"
            f"评分衡量整体设计质量，即使无新规则，恶化也必须修复。\n"
        )

    # ── 轮次历史（防重复无效策略）──
    history_section = ""
    if history:
        hist_lines = []
        for h in history:
            hist_lines.append(
                f"- 第 {h['round']} 轮: {h['changes']} 条变更 → {h['new_violations']} 个新违规"
                + (f"（{h['attempt']}）" if h.get("attempt") else "")
            )
        history_section = (
            "\n## 前几轮尝试（重复已失败策略不会产生不同结果，请换策略）\n"
            + "\n".join(hist_lines) + "\n"
        )

    # ── 决策指引 ──
    parts = []
    if round_num >= max_rounds:
        parts.append(
            f"这是最后一轮修正机会（第 {round_num}/{max_rounds} 轮）。"
            "如果无法通过局部修改消除违规，请直接撤销全部有问题的变更（返回空 changes）。"
        )
    parts.append(
        "修复策略（按优先级）：\n"
        "1. **撤销**：从 changes 中删除导致违规的条目，即恢复该元件原值。变更列表是全量替换语义——"
        "输出不含某条目 = 该元件恢复原状。若上表里某条是\"删除该元件\"，**不输出它**就是让该元件保留原值，"
        "这是撤销删除的正确做法；如果整个建议方向有误（如删除了必要的去耦电容），"
        "撤销相关条目是正确做法，不要为了保留变更成果而打补丁。\n"
        "2. **修正**：按每条违规的'修法'指引调整 new_value（如恢复 100nF、改回耐压足够的型号）。\n"
        "3. **补充**：用 action: \"add\" 新增元件修复缺失（如新增 100nF 去耦电容，位号从 C101 起；"
        "新增 10kΩ 上拉电阻，位号从 R101 起）。add 的 field 填 value，new_value 填完整参数"
        "（如 \"100nF 10V X7R 0603\"）。"
    )
    guidance = "\n".join(parts)

    prompt = f"""你之前提出的 PCB BOM 变更建议经过 DRC 规则引擎检查，发现了问题，需要修正。

## 原始建议
{suggestion}

## 你当前提出的变更（注意：下一轮输出是**全量替换**这份列表，不是追加）
{changes_table}

## 原始 BOM 中相关元件的原始参数（撤销 = 恢复这里的值）
{original_table}

## DRC 检出的新违规（相对变更前基线）
{violation_desc}
{worsened_section}{score_section}{history_section}
## 修正指引
{guidance}

## 输出要求
只输出一个 JSON 对象，格式与之前相同：{{"changes": [...]}}。
- 这是替换语义：输出的 changes 列表就是下一轮的全部变更。要撤销某条变更，就不要输出它。
- 要全部撤销（建议本身有害），输出 {{"changes": []}}，这是合法且推荐的收敛方式。
- 每条变更的 action 必须显式写出（replace / add / remove），field 不能是 "reference"。
- 不要输出任何解释文字。
"""
    return prompt


def _strip_fences(text: str) -> str:
    """去掉 ```json ... ``` markdown 代码围栏（大小写兼容）。"""
    for lang in ("json", "JSON", "jsonl"):
        m = re.search(r"```\s*" + lang + r"\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return text


def _balanced_objects(text: str):
    """yield 顶层均衡的 {...} 子串，正确处理字符串内的引号和转义。"""
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        yield text[i:j + 1]
                        i = j + 1
                        break
            j += 1
        else:
            break


def _try_parse_candidate(cand: str):
    """解析候选 JSON；宽容处理尾逗号。返回 dict/list 或 None。"""
    cand = cand.strip()
    # 优先原样解析；失败则去掉尾逗号后重试
    for variant in (cand, re.sub(r",\s*([}\]])", r"\1", cand)):
        try:
            return json.loads(variant)
        except json.JSONDecodeError:
            continue
    return None


def parse_llm_bom_changes(llm_response: str) -> ParseResult:
    """从 LLM 响应中提取结构化 BOM 变更。

    多级回退，容忍 LLM 在 JSON 外包裹解释文本、markdown 围栏、尾逗号、
    或一次输出多个对象：
    1. 去掉 ```json``` 围栏后整体解析
    2. 整体解析
    3. 按均衡括号依次提取每个 {...} 对象并解析
    优先采用含 "changes" 键的顶层对象。

    Args:
        llm_response: LLM 原始响应文本

    Returns:
        ParseResult 对象
    """
    text = llm_response.strip()

    # 按优先级收集候选 JSON 子串
    candidates = []
    fenced = _strip_fences(text)
    if fenced and fenced != text:
        candidates.append(fenced)
    candidates.append(text)
    candidates.extend(_balanced_objects(text))

    parsed = None
    fallback = None
    for cand in candidates:
        result = _try_parse_candidate(cand)
        if result is None:
            continue
        if isinstance(result, dict):
            if "changes" in result:
                parsed = result
                break
            if fallback is None:
                fallback = result
        else:
            if fallback is None:
                fallback = result
    if parsed is None:
        parsed = fallback

    if parsed is None:
        return ParseResult(
            changes=[],
            raw_json=text[:500],
            parse_error=f"无法从LLM响应中提取有效JSON。响应前200字: {text[:200]}"
        )

    if not isinstance(parsed, dict):
        return ParseResult(
            changes=[],
            raw_json=json.dumps(parsed, ensure_ascii=False),
            parse_error=f"顶层不是对象: {type(parsed)}"
        )

    # Extract changes list
    changes_raw = parsed.get("changes", [])
    if not isinstance(changes_raw, list):
        return ParseResult(
            raw_json=json.dumps(parsed, ensure_ascii=False),
            parse_error=f"changes字段不是列表: {type(changes_raw)}"
        )

    changes = []
    normalized_removals = 0
    for entry in changes_raw:
        if not isinstance(entry, dict):
            continue
        action = str(entry.get("action", "") or "").strip().lower()
        entry_field = str(entry.get("field", "") or "").strip()
        new_value = str(entry.get("new_value", "") or "").strip()
        reference = str(entry.get("reference", "") or "").strip()
        old_value = str(entry.get("old_value", "") or "").strip()

        # ── 归一化 1：删除语义 ──
        # 2026-09-08 实验实测：76/77 条变更由 GLM 输出为
        #   {"field": "reference", "new_value": "", "action": "replace"}
        # 而非 prompt 约定的 action:"remove"。两种写法在此统一为 canonical
        # action="remove" + field="value"，否则修正轮 prompt 会把删除渲染成
        # "字段=reference / 当前值=(空) / 操作=replace"，LLM 根本看不出自己删了元件。
        if action == "remove" or (entry_field == "reference" and not new_value):
            if action != "remove":
                normalized_removals += 1
            changes.append(BOMChange(
                reference=reference,
                field="value",
                old_value=old_value,
                new_value="",
                action="remove",
            ))
            continue

        # ── 归一化 2：action 缺失/非法 → replace（prompt 要求显式给出）──
        if action not in ("replace", "add"):
            action = "replace"

        changes.append(BOMChange(
            reference=reference,
            field=entry_field or "value",
            old_value=old_value,
            new_value=new_value,
            action=action,
        ))

    return ParseResult(
        changes=changes,
        raw_json=json.dumps(parsed, ensure_ascii=False),
        normalized_removals=normalized_removals,
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
            # 2026-09-10：新增位号不得与现有 BOM 冲突，否则会把一个元件变成重复行
            if ref_upper in ref_map:
                warnings.append(
                    f"{change.reference}: add 的位号已存在于BOM中，跳过（避免重复元件）"
                )
                continue
            valid.append(change)
            continue

        # replace / remove 需要引用存在
        if ref_upper not in ref_map:
            # 2026-09-10：区分两种"位号不在 BOM 中"。
            # 带 new_value 的 replace 极可能是模型把"新增元件"写成了 replace
            # （2026-09-08 实验：17/17 条"增加去耦电容"优化建议产出 0 变更，
            # 就是这类条目被静默丢弃，最后被统计成"纯分析建议通过"）。
            if change.new_value:
                warnings.append(
                    f"{change.reference}: 位号不在BOM中且 action≠add"
                    f"（疑似新增元件但未标 action:add），已丢弃"
                )
            else:
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
            # 2026-09-10：同一新元件的多条 add（如先 value 后 package）必须合并到
            # 同一条，而不是各 append 一个 —— 否则一个电容会变成两个残缺元件
            # （16 板实验里 cw32 的 6 个新增电容变成了 12 行）。
            existing = ref_to_indices.get(ref_upper, [])
            if existing:
                idx = existing[0]
                field_name = change.field if change.field in _VALID_BOM_FIELDS else "value"
                result[idx] = replace(result[idx], **{field_name: change.new_value})
                continue

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
            ref_to_indices.setdefault(ref_upper, []).append(len(result) - 1)
            continue

        # replace action
        indices = ref_to_indices.get(ref_upper, [])
        if not indices:
            continue

        for idx in indices:
            if change.field == "reference" and not change.new_value:
                # 删除语义：LLM 按提示用 field=reference + new_value="" 表示移除元件
                result[idx] = replace(result[idx], value="[REMOVED]", description="[REMOVED]")
                continue
            kwargs = {change.field: change.new_value}
            result[idx] = replace(result[idx], **kwargs)

    return result
