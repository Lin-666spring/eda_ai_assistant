"""int8 量化配置对比实验 — 一次性实验脚本（BERT 批调参用）

对同一微调权重导出 fp32 ONNX 后尝试多组 quantize_dynamic 配置，
在 val+eval（244 句）上对比与 torch 侧的 argmax 一致率 / 最大概率差，
并计算量化后 84 句评估集准确率。选出 parity 达标（一致率≥0.99 且
评估集准确率与 torch 持平）的配置回填 train_intent_bert.py。

用法: python scripts/exp_quant_configs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ml.intent_classifier import INTENT_CLASSES
from src.ml.train_intent_bert import (
    FINETUNED_DIR, OUTPUT_DIR, PRETRAINED_DIR,
    BertTextEncoder, _OnnxWrapper, collect_logits, eval_logits_accuracy,
)

TEMPERATURE = 0.8465


def torch_probs(model, encoder, samples, device="cpu", batch=32):
    logits, labels = collect_logits(model, encoder, samples, device)
    return F.softmax(logits / TEMPERATURE, dim=1).numpy(), labels.numpy()


def onnx_probs(onnx_path, encoder, samples, batch=32):
    import onnxruntime as ort
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    names = {i.name for i in sess.get_inputs()}
    chunks = []
    for i in range(0, len(samples), batch):
        enc = encoder.encode_batch([s["text"] for s in samples[i:i + batch]])
        inputs = {"input_ids": np.array(enc["input_ids"]),
                  "attention_mask": np.array(enc["attention_mask"])}
        if "token_type_ids" in names:
            inputs["token_type_ids"] = np.array(enc["token_type_ids"])
        chunks.append(sess.run(["logits"], inputs)[0])
    logits = np.concatenate(chunks)
    return F.softmax(torch.from_numpy(logits) / TEMPERATURE, dim=1).numpy()


def try_quantize(tag, fp32_path, out_path, **kwargs):
    from onnxruntime.quantization import quantize_dynamic
    quantize_dynamic(str(fp32_path), str(out_path), **kwargs)
    size_mb = out_path.stat().st_size / 1e6
    return tag, out_path, size_mb


def main() -> int:
    from transformers import AutoModelForSequenceClassification

    model = AutoModelForSequenceClassification.from_pretrained(FINETUNED_DIR)
    model.eval()
    encoder = BertTextEncoder(PRETRAINED_DIR / "vocab.txt", 32)

    val = json.load(open(PROJECT_ROOT / "data/nlu_train_val.json", encoding="utf-8"))
    ev = json.load(open(PROJECT_ROOT / "data/nlu_eval.json", encoding="utf-8"))
    all_samples = val + ev

    tp, labels = torch_probs(model, encoder, all_samples)
    eval_tp, eval_labels = torch_probs(model, encoder, ev)
    torch_eval_correct = int((eval_tp.argmax(1) == eval_labels).sum())
    print(f"torch 基线：val+eval argmax 集 84句正确 {torch_eval_correct}/84")

    # fp32 ONNX
    fp32_path = OUTPUT_DIR / "exp_fp32.onnx"
    wrapper = _OnnxWrapper(model).eval()
    dummy = encoder.encode_batch([s["text"] for s in val[:1]])
    torch.onnx.export(
        wrapper,
        (torch.from_numpy(dummy["input_ids"]), torch.from_numpy(dummy["attention_mask"]),
         torch.from_numpy(dummy["token_type_ids"])),
        str(fp32_path),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["logits"],
        dynamic_axes={"input_ids": {0: "batch"}, "attention_mask": {0: "batch"},
                      "token_type_ids": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17, dynamo=False,
    )
    op = onnx_probs(fp32_path, encoder, all_samples)
    print(f"fp32 ONNX: argmax一致 {np.mean(op.argmax(1) == tp.argmax(1)):.4f} "
          f"maxdiff {np.abs(op - tp).max():.6f}")

    from onnxruntime.quantization import QuantType

    configs = [
        ("A default", dict(weight_type=QuantType.QInt8)),
        ("B per_channel", dict(per_channel=True, weight_type=QuantType.QInt8)),
        ("C pc+reduce_range", dict(per_channel=True, weight_type=QuantType.QInt8,
                                   reduce_range=True)),
        ("D pc+rr+sym+matmul/gemm", dict(per_channel=True, weight_type=QuantType.QInt8,
                                         reduce_range=True,
                                         op_types_to_quantize=["MatMul", "Gemm"],
                                         extra_options={"WeightSymmetric": True})),
        ("E QUInt8 pc", dict(per_channel=True, weight_type=QuantType.QUInt8)),
    ]

    results = []
    for tag, kwargs in configs:
        out = OUTPUT_DIR / f"exp_{tag.split()[0]}.onnx"
        try:
            try_quantize(tag, fp32_path, out, **kwargs)
            qp = onnx_probs(out, encoder, all_samples)
            agree = float(np.mean(qp.argmax(1) == tp.argmax(1)))
            maxdiff = float(np.abs(qp - tp).max())
            eq = qp[len(val):]
            eval_correct = int((eq.argmax(1) == eval_labels).sum())
            print(f"{tag:26s}: argmax一致 {agree:.4f}  maxdiff {maxdiff:.4f}  "
                  f"eval {eval_correct}/84  {out.stat().st_size/1e6:.1f}MB")
            results.append((agree, maxdiff, eval_correct, tag))
        except Exception as e:
            print(f"{tag:26s}: 失败 {type(e).__name__}: {e}")

    print("\ntorch 84句正确:", torch_eval_correct)
    for f in OUTPUT_DIR.glob("exp_*.onnx"):
        f.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
