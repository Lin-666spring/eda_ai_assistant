"""规则抽查 · 生成判读用的紧凑预览（避免控制台编码问题，落成 UTF-8 文本）。

走线类：给出判读所需的几何证据（拐角角度/腿长/地标距离、串扰线对、差分对长度…）
其它规则：给出描述 + 设计上下文，够判断「这是对本板的判定还是通用提示」

用法: python scripts/rule_spotcheck_preview.py
输出: experiment_results/rule_spotcheck/sample_preview.txt（+ sample_preview_short.txt）
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("experiment_results/rule_spotcheck")
ANGLE_KEYS = ("ang", "leg_min", "w", "near_via_mm", "near_comp_mm", "edge_mm")


def trim_list(items, keys=None, n=4):
    out = []
    for it in items[:n]:
        if keys and isinstance(it, dict):
            out.append({k: it[k] for k in keys if k in it})
        else:
            out.append(it)
    if len(items) > n:
        out.append("...+" + str(len(items) - n))
    return out


def ev_full(r):
    ev = dict(r.get("evidence") or {})
    name = r["rule_name"]
    if "锐角" in name:
        ev["flagged"] = trim_list(ev.pop("acute", []), ANGLE_KEYS, 4)
        ev.pop("right", None)
        ev.pop("worst6", None)
        ev.pop("degenerate_below_leg_gate", None)
    elif "直角" in name:
        ev["flagged"] = trim_list(ev.pop("right", []), ANGLE_KEYS, 4)
        ev.pop("acute", None)
        ev.pop("worst6", None)
        ev.pop("degenerate_below_leg_gate", None)
    if "group_lengths_all" in ev:
        ev.pop("net_lengths", None)
        ev.pop("group_members_all", None)
        ev.pop("meta_rows", None)
    if "pairs" in ev:
        ev["pairs"] = trim_list(ev["pairs"], None, 4)
    parts = []
    for k, v in ev.items():
        if isinstance(v, dict) and len(v) > 8:
            v = dict(list(v.items())[:8])
        parts.append(k + "=" + json.dumps(v, ensure_ascii=False))
    return " ; ".join(parts)


def ev_short(r):
    ev = dict(r.get("evidence") or {})
    keep = {}
    ctx = r["design"]["ctx"]
    for k in ("net", "group", "pair", "layer", "count", "single_pin_nets", "vs",
              "est_net_current_a", "ipc_capacity_a", "rule_is_inner_flag",
              "board_rule_is_inner_flag",
              "capacity_outer_a", "capacity_inner_a", "board_layers_n"):
        if k in ev:
            keep[k] = ev[k]
    keep["design"] = r["design"]["file"].replace("ProPrj_", "")[:34]
    keep["ctx"] = {k: ctx[k] for k in ("components", "nets", "traces", "vias", "pours")}
    return "; ".join(k + "=" + json.dumps(v, ensure_ascii=False) for k, v in keep.items())


def main() -> int:
    recs = [json.loads(l) for l in (ROOT / "sample.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    full, short = [], []
    for r in recs:
        head = "[%s] %s | %s | %s\n    %s\n" % (
            r["id"], r["design"]["file"].replace("ProPrj_", "")[:40], r["rule_name"],
            r["severity"], r["description"])
        if r.get("is_trace_family"):
            full.append(head + "    ev: " + ev_full(r) + "\n")
        else:
            short.append(head + "    ev: " + ev_short(r) + "\n")
    (ROOT / "sample_preview_trace.txt").write_text("\n".join(full), encoding="utf-8")
    (ROOT / "sample_preview_other.txt").write_text("\n".join(short), encoding="utf-8")
    print("trace items:", len(full), "other items:", len(short))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
