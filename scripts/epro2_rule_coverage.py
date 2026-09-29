"""规则覆盖率实验：量化 `.epro2` 相对旧的四种导出数据解锁了多少条设计规则。

**不调用任何 LLM、不联网** —— 只用 `Epro2Parser` + `DesignRuleChecker`。

方法
----
每条 `_check_*` 规则开头都有一个「数据不足就 `return []`」的守卫
（如 `if not pcb or not pcb.traces: return []`）。用 AST 把守卫条件抽出来，
再用真实输入求值，就能精确判断这条规则在给定数据下**是否真的做出了判断**
（evaluable），而不是靠猜。

对每个设计跑三种数据配置：

| 配置 | bom | positions | netlist | pcb_data |
|---|---|---|---|---|
| C1 旧口径（四种导出能给的） | ✓ | ✓ | ✗ | ✗ |
| C2 +PCB 元件/网络（无铜） | ✓ | ✓ | ✗ | 有元件/网络，无走线/过孔/覆铜 |
| C3 全量 .epro2 | ✓ | ✓ | ✓ | 全量（含走线/过孔/覆铜） |

覆盖率的两种口径（都报，避免含糊）:

- **可判定 (evaluable)**: 规则的数据守卫通过 → 它真的对这块板做出了判断
- **有输出 (fired)**: 规则实际产出了 ≥1 条违规

``可判定`` 衡量能力，``有输出`` 衡量活跃度。旧记忆里的「30/71」没有说明口径，
本脚本把两种都算出来以便对账。

用法:
    python scripts/epro2_rule_coverage.py test_data/_incoming_epro2 \
        --out experiment_results/epro2_rule_coverage
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import inspect
import json
import sys
import textwrap
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pcb.epro2_parser import Epro2Parser, bom_rows_to_items  # noqa: E402
from src.rules.checker import DesignRuleChecker, rule_kind  # noqa: E402

CONFIGS = ("C1_old_exports", "C2_pcb_no_copper", "C3_epro2_full")


# ──────────────── 规则守卫抽取 ────────────────

def extract_guards() -> dict[str, str]:
    """抽出每条规则的「数据不足守卫」条件源码。

    取函数体里第一个 `if <cond>: return` / `return []` 语句。
    """
    src = textwrap.dedent(inspect.getsource(DesignRuleChecker))
    tree = ast.parse(src)

    guards: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("_check_"):
            continue
        cond = None
        for stmt in node.body:
            if not isinstance(stmt, ast.If):
                continue
            if len(stmt.body) != 1 or not isinstance(stmt.body[0], ast.Return):
                continue
            ret = stmt.body[0]
            empty_ret = ret.value is None or (
                isinstance(ret.value, (ast.List, ast.Tuple)) and not ret.value.elts
            )
            if empty_ret:
                cond = ast.unparse(stmt.test)
                break
        guards[node.name] = cond
    return guards


def guard_blocks(cond_src: str | None, ns: dict) -> bool | None:
    """守卫条件为真 → 该规则因数据不足被拦下。None 表示无法判定。"""
    if cond_src is None:
        return False  # 没有守卫 → 总会执行
    try:
        return bool(eval(cond_src, {"__builtins__": {}}, ns))  # noqa: S307
    except Exception:  # noqa: BLE001
        return None


# ──────────────── 数据装配 ────────────────

def _fingerprint(pcb) -> str:
    """设计指纹（与 build_epro2_dataset.py 同口径），用于跳过重复工程"""
    import hashlib

    refs = sorted(
        f"{ref}:{v.get('footprint_name', '')}" for ref, v in pcb.component_positions.items()
    )
    payload = "|".join([
        ",".join(refs),
        ",".join(sorted(pcb.nets)),
        f"{pcb.board_outline.get('width_mm')}x{pcb.board_outline.get('height_mm')}",
    ])
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]


def build_inputs(pcb):
    """把 .epro2 解析结果装配成 check_all 期望的三种输入"""
    bom_items = bom_rows_to_items(pcb.bom_items)
    positions = {
        ref: {
            "x": v.get("x", 0),
            "y": v.get("y", 0),
            "rotation": v.get("rotation", 0),
            "layer": v.get("side") or v.get("layer", ""),
            "package": v.get("footprint_name", ""),
        }
        for ref, v in pcb.component_positions.items()
    }
    netlist = {name: list(net.pins) for name, net in pcb.nets.items() if net.pins}

    no_copper = dataclasses.replace(pcb, traces=[], vias=[], copper_pours=[])
    return bom_items, positions, netlist, no_copper


def ns_for(checker, bom_items, positions, netlist, pcb_data) -> dict:
    checker._pcb_data = pcb_data
    return {
        "self": checker,
        "pcb": pcb_data,
        "bom_items": bom_items,
        "positions": positions,
        "netlist": netlist,
    }


# ──────────────── 主流程 ────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default="experiment_results/epro2_rule_coverage")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 个设计（调试用）")
    args = ap.parse_args()

    root = Path(args.path)
    files = sorted(root.rglob("*.epro2")) if root.is_dir() else [root]

    guards = extract_guards()
    rule_names = sorted(guards)
    print(f"规则总数: {len(rule_names)}")
    print(f"带守卫的规则: {sum(1 for v in guards.values() if v)}")

    parser = Epro2Parser()
    checker = DesignRuleChecker()

    # evaluable[config][rule] = 在多少个设计上可判定
    evaluable = {c: Counter() for c in CONFIGS}
    blocked = {c: Counter() for c in CONFIGS}
    unknown = {c: Counter() for c in CONFIGS}
    fired = {c: Counter() for c in CONFIGS}
    violations_by_cfg = {c: Counter() for c in CONFIGS}
    violations_by_rule = {c: Counter() for c in CONFIGS}
    # 规则函数 → 中文 rule_name：从源码取第一个 RuleViolation(rule_name=...)，
    # 不用「首个产出的违规」——同一函数可能产出多个 rule_name（如锐角/直角），
    # 那样标签会随数据漂移。
    rule_label: dict[str, str] = {r: _rule_label(checker, r) for r in rule_names}
    rule_errors = Counter()
    designs = []
    seen_fp: dict[str, str] = {}

    t0 = time.perf_counter()
    for i, f in enumerate(files, 1):
        try:
            pcb = parser.parse(str(f))
        except Exception as e:  # noqa: BLE001
            print(f"[{i}] 解析失败 {f.name}: {e}")
            continue

        fp = _fingerprint(pcb)
        if fp in seen_fp:
            print(f"[{i}] 跳过重复设计 {f.name} (同 {seen_fp[fp]})")
            continue
        seen_fp[fp] = f.name

        bom_items, positions, netlist, no_copper = build_inputs(pcb)

        # 三种数据配置：C1 旧口径 / C2 有 PCB 元件网络无铜 / C3 全量 .epro2
        for cfg, pcb_data, nl in (
            (CONFIGS[0], None, None),
            (CONFIGS[1], no_copper, None),
            (CONFIGS[2], pcb, netlist),
        ):
            ns = ns_for(checker, bom_items, positions, nl, pcb_data)
            for rule in rule_names:
                blocked_flag = guard_blocks(guards[rule], ns)
                if blocked_flag is None:
                    unknown[cfg][rule] += 1
                elif blocked_flag:
                    blocked[cfg][rule] += 1
                    continue
                evaluable[cfg][rule] += 1
                try:
                    res = getattr(checker, rule)(bom_items, positions, nl)
                except Exception as e:  # noqa: BLE001
                    rule_errors[(cfg, rule, type(e).__name__)] += 1
                    continue
                if res:
                    fired[cfg][rule] += 1
                    violations_by_rule[cfg][rule] += len(res)
                    for v in res:
                        violations_by_cfg[cfg][v.rule_name] += 1

        designs.append({
            "file": f.name,
            "title": pcb.metadata.get("title"),
            "components": len(pcb.component_positions),
            "nets": pcb.net_count,
            "traces": pcb.trace_count,
            "vias": pcb.via_count,
            "pours": len(pcb.copper_pours),
            "bom_rows": len(pcb.bom_items),
            "netlist_nets": len(netlist),
        })
        if args.limit and len(designs) >= args.limit:
            break

    elapsed = time.perf_counter() - t0
    n_designs = len(designs)

    def covered(cfg: str) -> list[str]:
        return [r for r in rule_names if evaluable[cfg][r] > 0]

    def rule_kind_of(rule: str) -> str:
        """'detect'（判定类）| 'advise'（提示类）—— 见 checker.ADVISE_RULES。"""
        return rule_kind(rule_label.get(rule, rule))

    def fired_rules(cfg: str, kind: str | None = None) -> list[str]:
        return [r for r in rule_names
                if fired[cfg][r] > 0 and (kind is None or rule_kind_of(r) == kind)]

    def kind_violations(cfg: str, kind: str) -> int:
        return sum(n for r, n in violations_by_rule[cfg].items() if rule_kind_of(r) == kind)

    lines = [
        f"源目录: {root}",
        f"参与实验的设计: {n_designs}（已按 元件/网络/过孔/走线 指纹去重）",
        f"规则总数: {len(rule_names)}（带数据守卫 {sum(1 for v in guards.values() if v)} 条）",
        f"耗时: {elapsed:.1f}s（零 LLM、零网络）",
        "",
        "═══ 口径 A：可判定（守卫通过 = 规则真的做了判断）═══",
    ]
    for cfg, label in zip(CONFIGS, ("C1 旧口径（四种导出）", "C2 +PCB元件/网络（无铜）", "C3 全量 .epro2")):
        c = covered(cfg)
        lines.append(f"  {label}: {len(c)}/{len(rule_names)} = {len(c) / len(rule_names) * 100:.1f}%")
    lines.append("")
    lines.append("═══ 口径 B：有输出（该配置下实际产出 ≥1 条违规的规则）═══")
    for cfg, label in zip(CONFIGS, ("C1 旧口径（四种导出）", "C2 +PCB元件/网络（无铜）", "C3 全量 .epro2")):
        c = fired_rules(cfg)
        lines.append(f"  {label}: {len(c)}/{len(rule_names)} = {len(c) / len(rule_names) * 100:.1f}%"
                     f"（违规总数 {sum(violations_by_cfg[cfg].values())}）")

    # 2026-09-24 抽查结论：13 条「几乎每块板都响」的规则贡献了 63% 的违规数量，
    # 把提示类也算进「有输出」就是虚高。口径 B′ 只统计判定类（checker.rule_kind == detect）。
    n_detect = sum(1 for r in rule_names if rule_kind_of(r) == "detect")
    n_advise = len(rule_names) - n_detect
    lines.append("")
    lines.append(f"═══ 口径 B′：判定类有输出（{n_advise} 条提示类不计入，见 checker.ADVISE_RULES）═══")
    for cfg, label in zip(CONFIGS, ("C1 旧口径（四种导出）", "C2 +PCB元件/网络（无铜）", "C3 全量 .epro2")):
        c = fired_rules(cfg, "detect")
        lines.append(f"  {label}: {len(c)}/{n_detect} = {len(c) / n_detect * 100:.1f}%"
                     f"（判定类违规 {kind_violations(cfg, 'detect')}，"
                     f"提示类 {kind_violations(cfg, 'advise')}）")

    c1, c2, c3 = set(covered(CONFIGS[0])), set(covered(CONFIGS[1])), set(covered(CONFIGS[2]))
    newly_c2 = sorted(c2 - c1)
    newly_c3 = sorted(c3 - c2)
    lines += [
        "",
        f"C2 相对 C1 新解锁: {len(newly_c2)} 条",
        f"C3 相对 C2 新解锁: {len(newly_c3)} 条",
        f"C3 相对 C1 共新解锁: {len(c3 - c1)} 条",
        "",
        "═══ 被 .epro2 解锁的规则（C1 拦截 → C3 可判定）═══",
    ]
    for r in sorted(c3 - c1):
        guard = guards[r] or "(无守卫)"
        stage = "C2" if r in newly_c2 else "C3"
        lines.append(f"  [{stage}] {r}（{rule_label.get(r, r)}）  ← 守卫: {guard}")
        lines.append(f"          可判定 {evaluable[CONFIGS[2]][r]}/{n_designs} 个设计，"
                     f"有输出 {fired[CONFIGS[2]][r]}/{n_designs} 个，"
                     f"违规 {violations_by_rule[CONFIGS[2]][r]} 次")

    still_blocked = sorted(set(rule_names) - c3)
    lines += ["", f"═══ 全量 .epro2 下仍被拦下的规则（{len(still_blocked)} 条）═══"]
    for r in still_blocked:
        why = "守卫仍拦" if blocked[CONFIGS[2]][r] > 0 else "守卫可判但从未产出"
        lines.append(f"  {r}（{rule_label.get(r, r)}）← {why}｜守卫: {guards[r]}")

    if rule_errors:
        lines += ["", "═══ 规则执行异常（需要修）═══"]
        for (cfg, rule, exc), n in rule_errors.most_common(20):
            lines.append(f"  [{cfg}] {rule}: {exc} × {n}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "coverage.json").write_text(json.dumps({
        "designs": n_designs,
        "rules_total": len(rule_names),
        "guards": guards,
        "evaluable_coverage": {c: len(covered(c)) for c in CONFIGS},
        "fired_coverage": {c: len(fired_rules(c)) for c in CONFIGS},
        "fired_coverage_detect": {c: len(fired_rules(c, "detect")) for c in CONFIGS},
        "rules_detect_total": n_detect,
        "rules_advise_total": n_advise,
        "detect_violations": {c: kind_violations(c, "detect") for c in CONFIGS},
        "advise_violations": {c: kind_violations(c, "advise") for c in CONFIGS},
        "rule_kinds": {r: rule_kind_of(r) for r in rule_names},
        "evaluable": {c: dict(evaluable[c]) for c in CONFIGS},
        "fired": {c: dict(fired[c]) for c in CONFIGS},
        "blocked": {c: dict(blocked[c]) for c in CONFIGS},
        "unknown": {c: dict(unknown[c]) for c in CONFIGS},
        "violations": {c: dict(violations_by_cfg[c]) for c in CONFIGS},
        "violations_by_rule": {c: dict(violations_by_rule[c]) for c in CONFIGS},
        "rule_labels": rule_label,
        "rule_errors": {f"{c}:{r}:{e}": v for (c, r, e), v in rule_errors.items()},
        "designs": designs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    text = "\n".join(lines)
    (out / "report.txt").write_text(text, encoding="utf-8")
    print("\n" + text)
    print(f"\nwrote {out}/coverage.json, report.txt")
    return 0


_LABEL_CACHE: dict[str, str] = {}


def _rule_label(checker, rule: str) -> str:
    """规则的 rule_name（中文）—— 从源码里抓第一个 RuleViolation(rule_name=...)。

    仅用于报告里对齐「规则函数 → 中文规则名」。
    """
    if rule in _LABEL_CACHE:
        return _LABEL_CACHE[rule]
    import re
    src = textwrap.dedent(inspect.getsource(getattr(checker, rule)))
    m = re.search(r'rule_name="([^"]+)"', src)
    label = m.group(1) if m else rule
    _LABEL_CACHE[rule] = label
    return label


if __name__ == "__main__":
    raise SystemExit(main())
