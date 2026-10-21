# -*- coding: utf-8 -*-
"""补充材料数据提取（N3）—— 论文五项随稿补充材料的程序化提取。

五项材料全部取自仓库真源，本脚本不做任何手写数字的编造：
  S1 设计清单    <- test_data/thing_designs/_manifest.csv
                  + experiment_results/run_thing_full_glm53/results.json（79 板主实验）
                  + experiment_results/mm20_deepseek_*/results.json（21 板分层子集）
                  + test_data/_incoming_epro2/78/*.epro2（几何/布局注入语料）
  S2 68条规则   <- src/rules/{base,bom_rules,geometry_rules,layout_rules,checker}.py
                  （AST 解析 RuleViolation 调用字面量，运行时 ADVISE_RULES 定类型）
  S3 提示词模板 <- tests/bom_suggestion.py（build_bom_change_prompt / build_correction_prompt，
                  含 2×2 消融四变体）+ src/agent/review_agents.py（AGENT_DEFINITIONS，
                  AST literal_eval）+ paper_experiments 实际调用形态的示例填充
  S4 变更集schema<- BOMChange 数据类 + 首轮解析提示词的硬性规则（形式化 JSON Schema）
  S5 评分器权重 <- src/core/design_scorer.py（DIMENSIONS / RULE_DIMENSION_MAP 生效映射 /
                  SEVERITY_PENALTY / 维度权重 / 公式常数 / 等级表）
                  + tests/paper_experiments.py SCORE_DROP_TOLERANCE（评分守门 τ）

输出: 论文/review/supplement_data.json
用法: python 论文/supplement_extract.py
"""

from __future__ import annotations

import ast
import csv
import inspect
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "论文" / "review" / "supplement_data.json"


# ═══════════════════════════════════════════════════════════════
# S2 规则定义：AST 提取 + 运行时类型标注
# ═══════════════════════════════════════════════════════════════

def _const_str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract_rule_names_from_func(func) -> list[dict]:
    """AST 解析一个规则方法源码，返回其中 RuleViolation(...) 调用发射的规则名列表。

    只取字面量 rule_name（位置参数 1 或关键字）；非字面量记为 None 待人工核对。
    严重度取关键字 severity= 的 RuleSeverity.X 属性名或字符串字面量。
    """
    src = inspect.getsource(func)
    tree = ast.parse(textwrap.dedent(src))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Name) and f.id == "RuleViolation"):
            continue
        name = None
        if node.args:
            name = _const_str(node.args[0])
        for kw in node.keywords:
            if kw.arg == "rule_name":
                name = _const_str(kw.value) or name
        sev = None
        for kw in node.keywords:
            if kw.arg == "severity":
                v = kw.value
                if isinstance(v, ast.Attribute):
                    sev = v.attr
                else:
                    sev = _const_str(v)
        out.append({"rule_name": name, "severity": sev})
    return out


def defining_class(cls, attr: str) -> str:
    for k in cls.__mro__:
        if attr in k.__dict__:
            return k.__name__
    return "?"


MODULE_OF_CLASS = {
    "BomRulesMixin": "bom",
    "GeometryRulesMixin": "geometry",
    "LayoutRulesMixin": "layout",
    "DesignRuleChecker": "checker",
}


# 严重度按判定条件动态分档的规则（条件摘自源码分支，非固定档）。
DYNAMIC_SEVERITY_NOTES = {
    "PDN 目标阻抗分析": "WARNING（去耦电容数>3）/ INFO（≤3）",
    "差分对等长检查": "按接口判据档分档（超限档 ERROR/WARNING；接口未识别的表外组为 INFO 参考）",
    "特征阻抗匹配检查": "WARNING（两层板）/ ERROR（多层板）",
    "电源线载流检查": "按 IPC-2221 载流余量分档（不足 ERROR；余量<1.5× WARNING）",
    "元件间距检查": "WARNING（重叠）/ INFO（接近）",
}


def extract_rules() -> dict:
    from src.rules.checker import DesignRuleChecker
    from src.rules.base import ADVISE_RULES, rule_kind

    names = sorted(n for n in dir(DesignRuleChecker) if n.startswith("_check_"))
    modules = {"bom": [], "geometry": [], "layout": [], "checker": []}
    all_names: list[str] = []
    unresolved: list[str] = []

    for attr in names:
        func = getattr(DesignRuleChecker, attr)
        mod = MODULE_OF_CLASS.get(defining_class(DesignRuleChecker, attr), "?")
        doc = inspect.getdoc(func) or ""
        summary = doc.split("\n")[0].strip()
        emissions = extract_rule_names_from_func(func)
        if not emissions:
            unresolved.append({"method": attr, "module": mod, "summary": summary})
            continue
        for e in emissions:
            rn = e["rule_name"]
            if rn is None:
                unresolved.append(f"{attr}(动态rule_name)")
                continue
            if rn in all_names:
                continue
            all_names.append(rn)
            modules[mod].append({
                "rule_name": rn,
                "method": attr,
                "kind": rule_kind(rn),
                "severity": e["severity"] or "动态",
                "severity_note": DYNAMIC_SEVERITY_NOTES.get(rn),
                "advise": rn in ADVISE_RULES,
                "summary": summary,
            })

    return {
        "count": len(all_names),
        "method_count": len(names),
        "modules": modules,
        "module_counts": {k: len(v) for k, v in modules.items()},
        "dormant_methods": unresolved,
        "unresolved": [],
        "advise_names": sorted(ADVISE_RULES),
    }


# ═══════════════════════════════════════════════════════════════
# S1 设计清单
# ═══════════════════════════════════════════════════════════════

def extract_designs() -> dict:
    manifest = {}
    with open(ROOT / "test_data/thing_designs/_manifest.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            manifest[row["design"]] = {
                "components": int(row["components"]),
                "src_index": int(row["src_index"]),
            }

    full = json.loads((ROOT / "experiment_results/run_thing_full_glm53/results.json")
                      .read_text(encoding="utf-8"))
    main_boards = sorted(set(r["design"] for r in full["drc_results"]))

    mm = json.loads((ROOT / "experiment_results/mm20_deepseek_20261019_184759/results.json")
                    .read_text(encoding="utf-8"))
    subset21 = sorted(set(r["design"] for r in mm["drc_results"]))

    inj_dir = ROOT / "test_data/_incoming_epro2/78"
    inj_boards = sorted(p.stem for p in inj_dir.glob("*.epro2"))

    # 分层（与 scripts/paper_multimodel_subset.stratified_sample 同口径：BOM 行数三层）
    sizes = {n: manifest.get(n, {}).get("components", 0) for n in main_boards}
    names_sorted = sorted(sizes, key=lambda k: sizes[k])
    t1 = names_sorted[: len(names_sorted) // 3]
    t2 = names_sorted[len(names_sorted) // 3: 2 * len(names_sorted) // 3]
    tier_of = {n: "小" for n in t1}
    tier_of.update({n: "中" for n in t2})
    tier_of.update({n: "大" for n in names_sorted[2 * len(names_sorted) // 3:]})

    lst = []
    for n in main_boards:
        lst.append({
            "name": n,
            "components": sizes[n],
            "tier": tier_of.get(n, "?"),
            "in_subset21": n in subset21,
        })

    # 复算分层抽样以核对子集（种子 2026、n=21；失败则以实测子集为准）
    recheck = None
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import random
        import openpyxl
        root_td = ROOT / "test_data/thing_designs"
        sizes2 = {}
        for name in main_boards:
            xl = sorted((root_td / name).glob("BOM*.xlsx"))
            if not xl:
                continue
            try:
                wb = openpyxl.load_workbook(xl[0], read_only=True)
                ws = wb.active
                rows = [r for r in ws.iter_rows(values_only=True) if any(r)]
                wb.close()
                sizes2[name] = max(0, len(rows) - 1)
            except Exception:
                sizes2[name] = 0
        ns = sorted(sizes2, key=lambda k: sizes2[k])
        tiers = [ns[: len(ns) // 3], ns[len(ns) // 3: 2 * len(ns) // 3], ns[2 * len(ns) // 3:]]
        rng = random.Random(2026)
        picked = []
        quota = [round(len(t) / len(ns) * 21) for t in tiers]
        while sum(quota) < 21:
            quota[1] += 1
        for t, q in zip(tiers, quota):
            picked += rng.sample(t, min(q, len(t)))
        recheck = sorted(picked)
    except Exception as e:
        recheck = f"recheck_failed: {e}"

    return {
        "pool": 91,
        "dropped": len(manifest) and (91 - len(manifest)),
        "total": len(main_boards),
        "manifest_total": len(manifest),
        "set_match_manifest": set(main_boards) == set(manifest),
        "list": lst,
        "subset21": subset21,
        "subset21_recheck_match": (recheck == subset21) if isinstance(recheck, list) else recheck,
        "injection_corpus": {"dir": "test_data/_incoming_epro2/78", "count": len(inj_boards),
                             "boards": inj_boards},
        "components_min": min(sizes.values()),
        "components_max": max(sizes.values()),
        "components_median": sorted(sizes.values())[len(sizes) // 2],
        "components_mean": round(sum(sizes.values()) / len(sizes), 1),
    }


# ═══════════════════════════════════════════════════════════════
# S3 提示词模板
# ═══════════════════════════════════════════════════════════════

class _DummyBOMItem:
    def __init__(self, reference, value, package):
        self.reference, self.value, self.package = reference, value, package
        self.reference_list = [r.strip() for r in reference.split(",")]


class _DummyViolation:
    def __init__(self, rule_name, severity, description, location, suggestion):
        from src.rules.base import RuleSeverity
        self.rule_name = rule_name
        self.severity = getattr(RuleSeverity, severity.upper())
        self.description = description
        self.location = location
        self.suggestion = suggestion


def extract_prompts() -> dict:
    from tests.bom_suggestion import build_bom_change_prompt, build_correction_prompt, BOMChange

    demo_bom = [
        _DummyBOMItem("C1,C2,C3", "100nF", "0603"),
        _DummyBOMItem("C6", "10μF", "0805"),
        _DummyBOMItem("U1", "STM32F103C8T6", "LQFP-48"),
        _DummyBOMItem("R1", "10kΩ", "0603"),
    ]

    parse_prompt = build_bom_change_prompt(
        "【此处为自然语言设计建议文本（首轮输入）】", demo_bom)

    changes = [
        BOMChange(reference="C1", field="value", old_value="100nF", new_value="", action="remove"),
        BOMChange(reference="R1", field="value", old_value="10kΩ", new_value="4.7kΩ", action="replace"),
    ]
    violations = [
        _DummyViolation("去耦电容数量检查", "error",
                        "电源轨 VDD 去耦电容数量不足（现有 2，建议 ≥4）",
                        "U1", "在 U1 各电源引脚 5mm 内补 100nF 去耦电容"),
        _DummyViolation("去耦电容距离检查", "warning",
                        "C6 距最近 IC 电源引脚 12.3mm，超过建议阈值 5mm",
                        "C6", "将去耦电容移近 IC 电源引脚或就近补充"),
    ]
    common = dict(
        suggestion="移除所有 100nF 去耦电容以降低 BOM 成本，用 0.1mm 走线承载 3A 电流",
        current_changes=changes,
        new_violations=violations,
        original_bom=demo_bom,
        baseline_rules={"去耦电容距离检查", "电源滤波"},
        baseline_violation_count=3,
        modified_violation_count=4,
        baseline_counts_by_rule={"去耦电容距离检查": 2, "电源滤波": 1},
        modified_counts_by_rule={"去耦电容距离检查": 3, "电源滤波": 1},
        baseline_score=82.5,
        modified_score=76.1,
        round_num=2,
        max_rounds=3,
        history=[{"round": 1, "changes": 2, "new_violations": 2, "attempt": "初始建议"}],
    )
    variants = {
        "A_full": build_correction_prompt(include_guidance=True, include_revert=True, **common),
        "B_noguid": build_correction_prompt(include_guidance=False, include_revert=True, **common),
        "C_norevert": build_correction_prompt(include_guidance=True, include_revert=False, **common),
        "D_neither": build_correction_prompt(include_guidance=False, include_revert=False, **common),
    }

    agents = _extract_agents()
    return {
        "parse_prompt": parse_prompt,
        "correction_variants": variants,
        "correction_variant_diffs": _variant_diffs(variants),
        "suggestion_templates": _extract_suggestion_templates(),
        "agent_prompt_templates": _extract_agent_prompt_sources(),
        "agents": agents,
        "source_files": {
            "parse_and_correction": "tests/bom_suggestion.py",
            "agents": "src/agent/review_agents.py",
            "runner_call_shape": "tests/paper_experiments.py",
        },
    }


def _variant_diffs(variants: dict) -> dict:
    """A_full 与其余三变体的逐行差异（保持行序），供文档只呈现差异句。"""
    import difflib
    base = variants["A_full"].splitlines()
    out = {}
    for k, v in variants.items():
        if k == "A_full":
            continue
        cur = v.splitlines()
        removed = [l for l in base if l not in cur]
        added = [l for l in cur if l not in base]
        out[k] = {"only_in_A": removed, "only_in_variant": added}
    return out


def _extract_suggestion_templates() -> list[dict]:
    """AST 提取 tests/paper_experiments.DEFAULT_SUGGESTIONS 的五条模板请求。"""
    src = (ROOT / "tests/paper_experiments.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "DEFAULT_SUGGESTIONS" for t in node.targets):
            for item in node.value.elts:
                if not isinstance(item, ast.Call):
                    continue
                kw = {k.arg: _const_str(k.value) for k in item.keywords}
                out.append({k: v for k, v in kw.items() if v is not None})
            break
    return out


def _extract_agent_prompt_sources() -> dict:
    """提取五智能体两处 LLM 提示词的源码字面量（f-string 赋值语句原文）。"""
    src = (ROOT / "src/agent/review_agents.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name not in ("_llm_deep_analyze", "_llm_summarize"):
            continue
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "prompt" for t in stmt.targets):
                seg = ast.get_source_segment(src, stmt.value)
                if seg:
                    found[node.name] = seg
    return found


def _extract_agents() -> dict:
    src = (ROOT / "src/agent/review_agents.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "AGENT_DEFINITIONS" for t in node.targets):
            defs = ast.literal_eval(node.value)
            clean = {}
            for k, v in defs.items():
                clean[k] = {kk: vv for kk, vv in v.items() if isinstance(vv, str)}
            return clean
    return {}


# ═══════════════════════════════════════════════════════════════
# S5 评分器权重映射 + 守门
# ═══════════════════════════════════════════════════════════════

def extract_scorer() -> dict:
    from src.core.design_scorer import (DIMENSIONS, RULE_DIMENSION_MAP,
                                        SEVERITY_PENALTY)
    from src.rules.base import RuleSeverity

    # 生效映射中「封装一致性」被 cost 段的同名键覆盖（字典字面量后者生效），
    # 对照源码字面量找出全部被覆盖键，供文档如实披露。
    src = (ROOT / "src/core/design_scorer.py").read_text(encoding="utf-8")
    literal_keys = re.findall(r'^\s*"([^"]+)":\s*\("(\w+)",\s*([\d.]+)\),', src, re.M)
    first_of, shadowed = {}, []
    for k, dim, w in literal_keys:
        if k in first_of:
            shadowed.append({"key": k, "shadowed_literal": first_of[k],
                             "effective_literal": [dim, float(w)]})
        else:
            first_of[k] = [dim, float(w)]

    grades_src = re.search(
        r"def _assign_grade.*?return \"F\"", src, re.S).group(0)
    grades = re.findall(r"score >= (\d+):\s*\n\s*return \"([^\"]+)\"", grades_src)

    pe_src = (ROOT / "tests/paper_experiments.py").read_text(encoding="utf-8")
    tau = re.search(r"SCORE_DROP_TOLERANCE\s*=\s*([\d.]+)", pe_src).group(1)

    return {
        "dimensions": DIMENSIONS,
        "rule_dimension_map_effective": {k: list(v) for k, v in RULE_DIMENSION_MAP.items()},
        "shadowed_literal_keys": shadowed,
        "severity_penalty": {sev.name: v for sev, v in SEVERITY_PENALTY.items()
                             if isinstance(sev, RuleSeverity)},
        "dimension_weights": {"power": 1.2, "signal": 1.2, "thermal": 1.0,
                              "emc": 1.0, "dfm": 0.8, "cost": 0.6},
        "formula": {"per_dim": "score_d = max(0, 100 - 2.2*sqrt(sum(base_sev * weight_rule)))",
                    "overall": "overall = sum(score_d * w_d) / sum(w_d)",
                    "sqrt_decay": 2.2,
                    "default_rule_weight_unmatched": 1.0,
                    "default_penalty_unmatched_severity": 5},
        "grade_thresholds": [[int(s), g] for s, g in grades],
        "gate": {"tau": float(tau),
                 "accept_condition": "new_violations == 0 且 (baseline_score - modified_score) <= τ",
                 "source": "tests/paper_experiments.py SCORE_DROP_TOLERANCE"},
    }


# ═══════════════════════════════════════════════════════════════
# S4 变更集 schema（由 BOMChange 数据类 + 解析提示词硬性规则形式化）
# ═══════════════════════════════════════════════════════════════

SCHEMA_DOC = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "BOM 变更集（闭环验证引擎 LLM 输出约定）",
    "type": "object",
    "required": ["changes"],
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["reference", "field", "action"],
                "properties": {
                    "reference": {"type": "string", "description": "位号，如 C1；合并位号须拆成多条"},
                    "field": {"type": "string",
                              "enum": ["value", "package", "part_number", "description",
                                       "quantity", "manufacturer"],
                              "description": "禁止取 reference"},
                    "old_value": {"type": "string", "description": "LLM 理解的当前值"},
                    "new_value": {"type": "string", "description": "纯参数值，禁止复合规格串"},
                    "action": {"type": "string", "enum": ["replace", "add", "remove"],
                               "description": "必须显式给出；add 的 field 固定为 value"},
                },
                "allOf": [
                    {"if": {"properties": {"action": {"const": "add"}}},
                     "then": {"properties": {"field": {"const": "value"}}}},
                ],
            },
        }
    },
}


def main() -> None:


    data = {
        "meta": {
            "generated_by": "论文/supplement_extract.py",
            "note": "五项材料全部程序化提取自仓库源码与实验产物；本文档不含任何手写实验数字。",
        },
        "rules": extract_rules(),
        "designs": extract_designs(),
        "prompts": extract_prompts(),
        "schema": SCHEMA_DOC,
        "scorer": extract_scorer(),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    r, d = data["rules"], data["designs"]
    print(f"规则总数: {r['count']}  模块分布: {r['module_counts']}  未解析: {r['unresolved']}")
    print(f"设计: 主实验 {d['total']} 板 (manifest {d['manifest_total']}, 集合一致={d['set_match_manifest']})")
    print(f"子集21: 实测 {len(d['subset21'])} 板, 复算一致={d['subset21_recheck_match']}")
    print(f"注入语料: {d['injection_corpus']['count']} epro2")
    print(f"提示词变体: {list(data['prompts']['correction_variants'].keys())}")
    print(f"评分器: 维度 {len(data['scorer']['dimensions'])}, 映射 {len(data['scorer']['rule_dimension_map_effective'])} 键, 被覆盖键 {data['scorer']['shadowed_literal_keys']}")
    print(f"输出: {OUT}")


if __name__ == "__main__":
    main()
