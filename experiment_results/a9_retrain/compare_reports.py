# -*- coding: utf-8 -*-
"""A-9 重训前后指标对比（主代理数据分析用）

读取 experiment_results/a9_retrain/baseline/ 下旧（泄漏数据）报告与 data/ 下新（无泄漏数据）
报告，输出同口径对比。用法：
    python experiment_results/a9_retrain/compare_reports.py
"""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
B = ROOT / "experiment_results" / "a9_retrain" / "baseline"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def fmt(x, nd=4):
    return "—" if x is None else f"{x:.{nd}f}"


def textcnn(tag, report_path):
    d = load(report_path)
    t, r = d["training"], d["results"]
    hist = d.get("history", {})
    pc = r.get("per_class", {})
    weakest = sorted(pc.items(), key=lambda kv: kv[1]["accuracy"])[:3]
    ev = r.get("eval_set") or {}
    print(f"[{tag}] TextCNN  样本 {t['train_samples']}/{t['val_samples']}  "
          f"best_epoch {t['best_epoch']}  best_val_acc {t['best_val_acc']:.4f}  "
          f"final {r['val_acc_final']:.4f}")
    if ev:
        print(f"    eval-set(84句): {ev.get('accuracy', '—')}  ({ev.get('correct')}/{ev.get('total')})")
    else:
        print("    eval-set: —")
    print(f"    最弱三类: {[(k, v['accuracy']) for k, v in weakest]}")
    if hist:
        accs = hist.get("val_acc", [])
        print(f"    末5轮 val_acc: {accs[-5:]}")
    return d


def bert(tag, report_path):
    d = load(report_path)
    hist = d["training"].get("history", [])
    best = max(hist, key=lambda e: e["val_acc"]) if hist else {}
    r = d.get("results", {})
    c = d.get("calibration", {})
    a = d.get("artifacts", {})
    par = a.get("parity", {})
    print(f"[{tag}] BERT(rbt3)  epochs_run {len(hist)}  best_epoch {best.get('epoch')}  "
          f"best_val_acc {best.get('val_acc')}  val_acc {r.get('val_acc')}")
    print(f"    eval-set: {r.get('eval_acc')} ({r.get('eval_total')}句)")
    print(f"    校准: T={c.get('temperature')} ECE {c.get('ece_before')}→{c.get('ece_after')}")
    print(f"    ONNX parity: argmax一致 {par.get('argmax_agreement')} max_prob_diff {par.get('max_prob_diff')}")
    pc = r.get("per_class", {})
    wrong = {k: v for k, v in pc.items() if v["correct"] < v["total"]}
    print(f"    per_class 有错类别: {wrong if wrong else '无'}")
    return d


print("=" * 70)
print("旧基线（A-9 泄漏数据，2026-10 备份）")
print("=" * 70)
textcnn("OLD", B / "nlu_train_report.json")
bert("OLD", B / "intent_bert_train_report.json")
textcnn("OLD", B / "component_train_report.json")

print()
print("=" * 70)
print("新结果（A-9 模板级无泄漏数据重训）")
print("=" * 70)
textcnn("NEW", ROOT / "data" / "nlu_train_report.json")
bert("NEW", ROOT / "data" / "intent_bert_train_report.json")
textcnn("NEW", ROOT / "data" / "component_train_report.json")
