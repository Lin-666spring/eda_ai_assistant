"""本地模型推理基准 — 定位"分析慢"的耗时分布

测量三个本地模型从冷启动到稳定推理的全链路耗时：
  1. import torch 冷导入
  2. 意图 TextCNN：加载 + 热身 + 逐条推理（data/nlu_train_val.json 全量 110 条）
  3. 元件分类 TextCNN：加载 + 逐条推理（data/component_train_val.json 全量 132 条）
  4. 变更风险逻辑回归：加载 + 单次预测
  5. NLUEngine 用户侧真实路径：首次 classify（含懒加载）vs 热身后

用法:
    python scripts/bench_local_models.py            # 全量
    python scripts/bench_local_models.py --rounds 3 # 每样本重复轮数
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def fmt_ms(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.2f} s"
    return f"{ms:.2f} ms"


def stat_line(samples_ms: list[float]) -> str:
    s = sorted(samples_ms)
    p50 = s[len(s) // 2]
    p95 = s[int(len(s) * 0.95)]
    return (f"mean={fmt_ms(statistics.mean(s))}  p50={fmt_ms(p50)}  "
            f"p95={fmt_ms(p95)}  max={fmt_ms(max(s))}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=5,
                        help="热身后每样本重复推理轮数")
    args = parser.parse_args()
    rounds = max(1, args.rounds)

    data_dir = PROJECT_ROOT / "data"

    # ── 1. torch 冷导入 ──
    t0 = time.perf_counter()
    import torch  # noqa: F401
    torch_import_ms = (time.perf_counter() - t0) * 1000
    print(f"[1] import torch（冷）           : {fmt_ms(torch_import_ms)}")

    from src.ml.intent_classifier import IntentClassifier, IntentPredictor
    from src.ml.vocab import PCBVocab

    # ── 2. 意图模型加载 ──
    t0 = time.perf_counter()
    vocab = PCBVocab.load(str(data_dir / "vocab.json"))
    vocab_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    model = IntentClassifier.load(str(data_dir / "intent_model.pt"))
    load_ms = (time.perf_counter() - t0) * 1000
    print(f"[2] 意图模型加载                 : vocab {fmt_ms(vocab_ms)} + 权重 {fmt_ms(load_ms)}")

    predictor = IntentPredictor(model, vocab)

    nlu_samples = json.load(open(data_dir / "nlu_train_val.json", encoding="utf-8"))
    texts = [s["text"] for s in nlu_samples]

    # 热身（首条含 torch 内核懒初始化）
    t0 = time.perf_counter()
    for text in texts:
        predictor.classify(text)
    first_pass_ms = (time.perf_counter() - t0) * 1000
    print(f"[3] 意图推理·首遍 {len(texts)} 条（含热身）: 总 {fmt_ms(first_pass_ms)}，"
          f"均 {fmt_ms(first_pass_ms / len(texts))}/条")

    latencies: list[float] = []
    for _ in range(rounds):
        for text in texts:
            t0 = time.perf_counter()
            predictor.classify(text)
            latencies.append((time.perf_counter() - t0) * 1000)
    print(f"    热身后 {len(latencies)} 次推理          : {stat_line(latencies)}")
    print(f"    吞吐                        : {1000 / statistics.mean(latencies):.0f} 条/秒")

    # 分解：纯 encode vs 纯 forward
    t0 = time.perf_counter()
    for text in texts:
        predictor.vocab.encode(text)
    encode_ms = (time.perf_counter() - t0) * 1000

    batch_ids = [predictor.vocab.encode(t)[:predictor.max_len] for t in texts]
    import torch.nn.functional as F  # noqa: F401
    t0 = time.perf_counter()
    with torch.no_grad():
        for ids in batch_ids:
            ids = ids + [vocab.pad_id] * (predictor.max_len - len(ids))
            x = torch.tensor([ids], dtype=torch.long)
            predictor.model(x)
    forward_ms = (time.perf_counter() - t0) * 1000
    print(f"    分解                        : encode {fmt_ms(encode_ms / len(texts))}/条 "
          f"+ forward {fmt_ms(forward_ms / len(texts))}/条（单条 batch=1）")

    # batch=64 对照
    t0 = time.perf_counter()
    with torch.no_grad():
        for i in range(0, len(batch_ids), 64):
            chunk = batch_ids[i:i + 64]
            padded = [ids + [vocab.pad_id] * (predictor.max_len - len(ids)) for ids in chunk]
            predictor.model(torch.tensor(padded, dtype=torch.long))
    batch_ms = (time.perf_counter() - t0) * 1000
    print(f"    batch=64 对照               : 总 {fmt_ms(batch_ms)}，"
          f"均 {fmt_ms(batch_ms / len(batch_ids))}/条")

    # ── 4. 元件分类模型 ──
    from src.ml.component_classifier import ComponentClassifier, ComponentPredictor

    t0 = time.perf_counter()
    comp_model = ComponentClassifier.load(str(data_dir / "component_model.pt"))
    comp_load_ms = (time.perf_counter() - t0) * 1000
    comp_predictor = ComponentPredictor(comp_model, vocab)

    key_map = {"ref": "reference", "pn": "part_number",
               "pkg": "package", "val": "value", "desc": "description"}
    comp_samples = json.load(open(data_dir / "component_train_val.json", encoding="utf-8"))
    items = []
    for s in comp_samples:
        fields = dict(kv.split(":", 1) for kv in s["text"].split() if ":" in kv)
        items.append({key_map.get(k, k): v for k, v in fields.items()})
    assert items[0].get("reference"), "样本键名映射失败"

    comp_lat: list[float] = []
    t0 = time.perf_counter()
    for item in items:
        t1 = time.perf_counter()
        comp_predictor.classify(item)
        comp_lat.append((time.perf_counter() - t1) * 1000)
    total_ms = (time.perf_counter() - t0) * 1000
    print(f"[4] 元件模型加载                 : {fmt_ms(comp_load_ms)}")
    print(f"    推理 {len(items)} 条               : 总 {fmt_ms(total_ms)}，{stat_line(comp_lat)}")

    # ── 5. 变更风险预测器 ──
    from src.ml.change_predictor import ChangeRiskPredictor

    t0 = time.perf_counter()
    risk_predictor = ChangeRiskPredictor.from_file(str(data_dir / "change_risk_model.json"))
    risk_load_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    risk_predictor.predict({
        "reference": "C12", "field": "value",
        "old_value": "100nF", "new_value": "1uF",
    }, baseline_score=60.0, existing_violations=[], bom_items=[])
    risk_ms = (time.perf_counter() - t0) * 1000
    print(f"[5] 变更风险模型                 : 加载 {fmt_ms(risk_load_ms)}，"
          f"单次预测 {fmt_ms(risk_ms)}")

    # ── 6. NLUEngine 用户侧真实路径 ──
    from src.agent.nlu_engine import NLUEngine

    t0 = time.perf_counter()
    engine = NLUEngine()
    ctor_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    engine.classify(texts[0])  # 首次调用触发懒加载
    first_call_ms = (time.perf_counter() - t0) * 1000

    warm_lat: list[float] = []
    for _ in range(3):
        for text in texts:
            t0 = time.perf_counter()
            engine.classify(text)
            warm_lat.append((time.perf_counter() - t0) * 1000)
    print(f"[6] NLUEngine 真实路径           : 构造 {fmt_ms(ctor_ms)}，"
          f"首次 classify（含懒加载）{fmt_ms(first_call_ms)}")
    print(f"    热身后 {len(warm_lat)} 次              : {stat_line(warm_lat)}")

    # ── 7. BERT 意图模型（2026-10-14 BERT 批；缺产物自动跳过）──
    from pathlib import Path as _Path

    bert_dir = _Path("data/models/intent_bert")
    if (bert_dir / "model.onnx").exists():
        from src.ml.intent_bert import BertIntentPredictor

        t0 = time.perf_counter()
        bert = BertIntentPredictor.from_path(bert_dir)
        bert_load_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        bert.classify(texts[0])  # 首次含 ORT 内核懒初始化
        bert_first_ms = (time.perf_counter() - t0) * 1000

        bert_lat: list[float] = []
        for _ in range(3):
            for text in texts:
                t0 = time.perf_counter()
                bert.classify(text)
                bert_lat.append((time.perf_counter() - t0) * 1000)
        print(f"[7] BERT rbt3 (fp16 ONNX)       : 加载 {fmt_ms(bert_load_ms)}，"
              f"首次推理 {fmt_ms(bert_first_ms)}")
        print(f"    热身后 {len(bert_lat)} 次推理           : {stat_line(bert_lat)}")
        print(f"    吞吐                        : "
              f"{1000 / statistics.mean(bert_lat):.0f} 条/秒")
    else:
        print("[7] BERT 模型产物缺失（data/models/intent_bert/），跳过")

    # 抽样展示分类效果
    print("\n── 抽样分类结果 ──")
    for text in texts[:5]:
        name, conf, debug = engine.classify(text)
        expect = next(s["intent"] for s in nlu_samples if s["text"] == text)
        mark = "OK " if name == expect else "MISS"
        print(f"  [{mark}] {text!r:40s} → {name} ({conf:.2f}) 期望 {expect}")

    print("\n── 结论要点 ──")
    cold_total = torch_import_ms + vocab_ms + load_ms
    print(f"  冷启动合计（import torch + 加载）: {fmt_ms(cold_total)}，"
          f"其中 import torch 占 {torch_import_ms / cold_total * 100:.0f}%")
    print(f"  稳态单条推理: {fmt_ms(statistics.mean(latencies))} —— "
          f"慢如果发生，不在推理本身")
    return 0


if __name__ == "__main__":
    sys.exit(main())
