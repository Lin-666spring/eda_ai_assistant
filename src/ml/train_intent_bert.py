"""NLU 意图分类 BERT 训练管线 — rbt3 微调 + 温度校准 + ONNX 导出

2026-10-14 BERT 批：意图底座由字符级 TextCNN 换为 hfl/rbt3（3 层中文
RoBERTa-wwm-ext，~38M 参数）。本脚本是一条龙管线：

    微调（LLRD 分层学习率 + best-epoch 早停）→ 验证集温度校准（LBFGS，
    同 calibrate.py 数学）→ 分布外评估集评估 → ONNX 导出（fp32 → ORT
    transformer 图融合 → fp16，parity 复验；--int8 可选动态量化）→ 产物落盘

导出格式默认 **fp16 融合图**：244 句上与 torch 一致率 1.0、概率差 ~1e-3、
77MB、CPU 单条 ~3ms。int8 动态量化虽 39MB/1.5ms，但实测 argmax 一致率仅
97.4%（评估集 74→72），对本应用 0.9/0.8 置信门语义损伤过大，降为可选项。

产物 data/models/intent_bert/：
    model.onnx          fp16 融合推理图（不入库，.gitignore）
    vocab.txt           BERT WordPiece 词表（入库，运行时唯一分词依赖）
    intent_config.json  标签序/温度/max_len/tokenizer 规格（入库）
    calibration.json    校准报告 ECE before/after（入库，小体积）

运行时只依赖 onnxruntime + tokenizers（requirements.txt），torch/
transformers 留在 dev 清单 ——「torch 不进 exe」红线不变。

用法:
    python src/ml/train_intent_bert.py                  # 全流程
    python src/ml/train_intent_bert.py --skip-train     # 复用已微调权重，只走校准+导出
    python src/ml/train_intent_bert.py --int8           # int8 动态量化（更快更小，掉精度）
前置:
    python scripts/download_rbt3.py                     # 拉取预训练底座
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ml.intent_classifier import INTENT_CLASSES, NUM_CLASSES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 产物路径 ──
PRETRAINED_DIR = PROJECT_ROOT / "data" / "models" / "rbt3_pretrained"
FINETUNED_DIR = PROJECT_ROOT / "data" / "models" / "rbt3_finetuned"
OUTPUT_DIR = PROJECT_ROOT / "data" / "models" / "intent_bert"
TRAIN_REPORT_PATH = PROJECT_ROOT / "data" / "intent_bert_train_report.json"


# ── 数据 ──

def load_json(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class BertTextEncoder:
    """rbt3 分词与编码 —— 训练/导出侧与运行时共用同一套规格。

    用 tokenizers 的 BertWordPieceTokenizer 直接加载 vocab.txt（rbt3 预训练
    同款，do_lower_case=True 语义由 BertNormalizer 等价实现），训练与推理
    （src/ml/intent_bert.py）走完全相同的编码路径，杜绝两侧漂移。
    """

    def __init__(self, vocab_file: str | Path, max_len: int):
        from tokenizers import BertWordPieceTokenizer

        self.tokenizer = BertWordPieceTokenizer(str(vocab_file), lowercase=True)
        self.tokenizer.enable_truncation(max_length=max_len)
        self.tokenizer.enable_padding(length=max_len, pad_id=0, pad_token="[PAD]")
        self.max_len = max_len

    def encode_batch(self, texts: list[str]) -> dict[str, np.ndarray]:
        encodings = self.tokenizer.encode_batch(texts)
        return {
            "input_ids": np.array([e.ids for e in encodings], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in encodings], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in encodings], dtype=np.int64),
        }


# ── 温度校准（与 calibrate.py 同数学，logits 级解耦实现）──

def compute_ece(confidences: np.ndarray, accuracies: np.ndarray, n_bins: int = 10) -> dict:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_results = []
    total = len(confidences)
    ece_sum = 0.0
    mce = 0.0
    for i in range(n_bins):
        mask = (confidences >= bins[i]) & (confidences < bins[i + 1])
        if i == n_bins - 1:
            mask = (confidences >= bins[i]) & (confidences <= bins[i + 1])
        count = int(mask.sum())
        if count == 0:
            bin_results.append({"bin_start": round(float(bins[i]), 2),
                                "bin_end": round(float(bins[i + 1]), 2),
                                "count": 0, "acc": None, "conf": None, "gap": None})
            continue
        bin_acc = float(accuracies[mask].mean())
        bin_conf = float(confidences[mask].mean())
        gap = abs(bin_acc - bin_conf)
        ece_sum += (count / total) * gap
        mce = max(mce, gap)
        bin_results.append({"bin_start": round(float(bins[i]), 2),
                            "bin_end": round(float(bins[i + 1]), 2),
                            "count": count, "acc": round(bin_acc, 4),
                            "conf": round(bin_conf, 4), "gap": round(float(gap), 4)})
    return {"ece": round(float(ece_sum), 4), "mce": round(float(mce), 4),
            "n_bins": n_bins, "n_samples": total, "bins": bin_results}


def forward_logits(model, batch_np: dict[str, np.ndarray], device: str) -> torch.Tensor:
    inputs = {k: torch.from_numpy(v).to(device) for k, v in batch_np.items()}
    with torch.no_grad():
        return model(**inputs).logits


def collect_logits(model, encoder, samples: list[dict], device: str,
                   batch_size: int = 32) -> tuple[torch.Tensor, torch.Tensor]:
    """全量预取 logits 与标签（校准/评估共用；样本量小，一次装得下）"""
    texts = [s["text"] for s in samples]
    labels = torch.tensor([INTENT_CLASSES.index(s["intent"]) for s in samples],
                          dtype=torch.long)
    logits_chunks = []
    for i in range(0, len(texts), batch_size):
        batch = encoder.encode_batch(texts[i:i + batch_size])
        logits_chunks.append(forward_logits(model, batch, device).cpu())
    return torch.cat(logits_chunks), labels


def learn_temperature(all_logits: torch.Tensor, all_labels: torch.Tensor,
                      lr: float = 0.01, max_iter: int = 200) -> tuple[float, float]:
    """验证集 NLL 最小化学温度。

    主路 LBFGS（与 calibrate.py 同口径，起点 1.5）；但尖锐 logits 上固定
    步长 LBFGS 可能过冲发散（第 3 轮训练曾给出 T=-34250，负温度把 softmax
    排名整个反转、val_acc 归零）——一维问题直接网格精扫兜底，在「T>0 且
    NLL 最小」中取最优，结果确定性可复现。
    """
    temperature = torch.nn.Parameter(torch.tensor(1.5))
    optimizer = torch.optim.LBFGS([temperature], lr=lr, max_iter=max_iter)
    nll = torch.nn.CrossEntropyLoss()

    def closure():
        optimizer.zero_grad()
        loss = nll(all_logits / temperature, all_labels)
        loss.backward()
        return loss

    optimizer.step(closure)
    t = float(temperature.item())

    best_t, best_nll = 1.0, float("inf")
    if t > 0:
        best_t, best_nll = t, float(nll(all_logits / t, all_labels).item())
    grid = np.concatenate([np.arange(0.10, 2.0, 0.05), np.arange(2.0, 10.25, 0.25)])
    for cand in grid:
        cand_nll = float(nll(all_logits / float(cand), all_labels).item())
        if cand_nll < best_nll:
            best_t, best_nll = float(cand), cand_nll

    logger.info("温度：LBFGS=%.4f → 网格校正=%.4f (NLL=%.4f)", t, best_t, best_nll)
    return best_t, best_nll


def eval_logits_accuracy(all_logits: torch.Tensor, all_labels: torch.Tensor,
                         temperature: float = 1.0) -> tuple[np.ndarray, np.ndarray, float]:
    """返回 (置信度, 正确性, 总准确率)；softmax(logits/T)"""
    probs = F.softmax(all_logits / temperature, dim=1)
    confs, preds = probs.max(dim=1)
    correct = (preds == all_labels).numpy().astype(float)
    return confs.numpy(), correct, float(correct.mean())


# ── 微调 ──

def build_llrd_param_groups(model, lr: float, decay: float) -> list[dict]:
    """分层学习率衰减（Layer-wise LR Decay）。

    小数据微调 BERT 的标准做法：分类头全量 lr，越靠近输入的层越小
    （rbt3 三层：head 1.0 → L2 0.7 → L1 0.49 → L0 0.34 → embed 0.24），
    避免底层表示被 790 条模板数据冲垮。
    """
    groups: list[dict] = [
        {"params": list(model.classifier.parameters()), "lr": lr},
    ]
    bert = model.bert
    if getattr(bert, "pooler", None) is not None:
        groups.append({"params": list(bert.pooler.parameters()),
                       "lr": lr * decay ** 0.5})
    n_layers = len(bert.encoder.layer)
    for i, layer in enumerate(bert.encoder.layer):
        groups.append({"params": list(layer.parameters()),
                       "lr": lr * decay ** (n_layers - i)})
    groups.append({"params": list(bert.embeddings.parameters()),
                   "lr": lr * decay ** (n_layers + 1)})
    return groups


def finetune(model, encoder, train_samples, val_samples, device: str,
             epochs: int, batch_size: int, lr: float, weight_decay: float,
             patience: int, seed: int, llrd_decay: float) -> dict:
    """标准 torch 循环微调，best-epoch 权重就地保留在模型上（早停）"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    param_groups = build_llrd_param_groups(model, lr, llrd_decay)
    optimizer = torch.optim.AdamW(param_groups, lr=lr, weight_decay=weight_decay)
    criterion = torch.nn.CrossEntropyLoss()
    total_steps = max(1, (len(train_samples) // batch_size) * epochs)
    warmup_steps = max(1, int(total_steps * 0.1))

    def lr_lambda(step):
        if step < warmup_steps:
            return step / warmup_steps
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return max(0.05, 0.5 * (1 + np.cos(np.pi * progress)))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    history = []
    best_val_acc = -1.0
    best_epoch = 0
    best_state = None
    stale = 0

    for epoch in range(1, epochs + 1):
        model.train()
        order = list(range(len(train_samples)))
        random.shuffle(order)
        losses = []
        for i in range(0, len(order), batch_size):
            batch_samples = [train_samples[j] for j in order[i:i + batch_size]]
            inputs = encoder.encode_batch([s["text"] for s in batch_samples])
            labels = torch.tensor([INTENT_CLASSES.index(s["intent"]) for s in batch_samples],
                                  dtype=torch.long, device=device)
            inputs = {k: torch.from_numpy(v).to(device) for k, v in inputs.items()}
            optimizer.zero_grad()
            loss = criterion(model(**inputs).logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            losses.append(loss.item())

        model.eval()
        val_logits, val_labels = collect_logits(model, encoder, val_samples, device)
        _, _, val_acc = eval_logits_accuracy(val_logits, val_labels)
        val_loss = float(torch.nn.functional.cross_entropy(val_logits, val_labels).item())
        history.append({"epoch": epoch, "train_loss": round(float(np.mean(losses)), 4),
                        "val_loss": round(val_loss, 4), "val_acc": round(val_acc, 4)})

        mark = ""
        if val_acc > best_val_acc:
            best_val_acc, best_epoch, stale = val_acc, epoch, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            mark = " *best"
        else:
            stale += 1
        logger.info("epoch %d/%d  train_loss=%.4f  val_loss=%.4f  val_acc=%.4f%s",
                    epoch, epochs, history[-1]["train_loss"], val_loss, val_acc, mark)

        if stale >= patience:
            logger.info("早停：连续 %d 轮无提升（best epoch=%d, val_acc=%.4f）",
                        patience, best_epoch, best_val_acc)
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    return {"history": history, "best_epoch": best_epoch, "best_val_acc": round(best_val_acc, 4),
            "stopped_early": stale >= patience}


# ── ONNX 导出 ──

class _OnnxWrapper(torch.nn.Module):
    """只暴露 logits 输出、显式三输入的包装（BertModel 的 ModelOutput 不利导出）"""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask, token_type_ids):
        return self.model(input_ids=input_ids, attention_mask=attention_mask,
                          token_type_ids=token_type_ids).logits


def export_onnx(model, encoder, wrapper_samples: dict[str, np.ndarray],
                out_final: Path, precision: str) -> dict:
    """导出 fp32 → ORT transformer 图融合 → fp16/int8 → 图检查。

    precision: "fp16"（默认，数值无损）或 "int8"（动态量化，更快更小但
    实测有 ~2.5% argmax 翻转，仅在对延迟敏感、对精度宽容时使用）。
    """
    import onnx

    model.eval()
    wrapper = _OnnxWrapper(model).eval()
    dummy = {k: torch.from_numpy(v)[:1] for k, v in wrapper_samples.items()}
    fp32_path = out_final.parent / "model_fp32_tmp.onnx"

    torch.onnx.export(
        wrapper,
        (dummy["input_ids"], dummy["attention_mask"], dummy["token_type_ids"]),
        str(fp32_path),
        input_names=["input_ids", "attention_mask", "token_type_ids"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch"}, "attention_mask": {0: "batch"},
            "token_type_ids": {0: "batch"}, "logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )
    onnx.checker.check_model(onnx.load(str(fp32_path)))

    # ORT transformer 图融合（LayerNorm/Gelu 等合并为单算子，提速并稳定量化）
    from onnxruntime.transformers import optimizer

    cfg = json.loads((PRETRAINED_DIR / "config.json").read_text(encoding="utf-8"))
    fused_path = out_final.parent / "model_fused_tmp.onnx"
    opt = optimizer.optimize_model(
        str(fp32_path), model_type=cfg.get("model_type", "bert"),
        num_heads=cfg.get("num_attention_heads", 12),
        hidden_size=cfg.get("hidden_size", 768),
    )
    opt.save_model_to_file(str(fused_path))
    logger.info("fp32 导出+图融合完成（%.1f MB）", fused_path.stat().st_size / 1e6)

    if precision == "int8":
        from onnxruntime.quantization import quantize_dynamic, QuantType

        quantize_dynamic(str(fused_path), str(out_final), per_channel=True,
                         weight_type=QuantType.QInt8,
                         extra_options={"DefaultTensorType": onnx.TensorProto.FLOAT})
    elif precision == "fp16":
        import onnxconverter_common.float16 as float16

        m16 = float16.convert_float_to_float16(onnx.load(str(fused_path)),
                                               keep_io_types=True)
        onnx.save(m16, str(out_final))
    elif precision == "fp32":
        shutil.copyfile(fused_path, out_final)
    else:
        raise ValueError(f"未知 precision: {precision}")
    logger.info("%s 导出完成：%s（%.1f MB）", precision, out_final.name,
                out_final.stat().st_size / 1e6)

    fp32_path.unlink()
    fused_path.unlink()
    return {"precision": precision, "fused": True,
            "size_mb": round(out_final.stat().st_size / 1e6, 1)}


def onnx_parity_check(onnx_path: Path, encoder, samples: list[dict],
                      torch_model, device: str, precision: str,
                      batch_size: int = 32) -> dict:
    """ONNX 与 torch 的一致性复验：argmax 一致率 + 概率最大绝对差"""
    import onnxruntime as ort

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    texts = [s["text"] for s in samples]
    argmax_agree, max_diff = 0, 0.0
    for i in range(0, len(texts), batch_size):
        batch = encoder.encode_batch(texts[i:i + batch_size])
        torch_probs = F.softmax(forward_logits(torch_model, batch, device), dim=1).numpy()
        onnx_logits = sess.run(["logits"], {
            "input_ids": batch["input_ids"],
            "attention_mask": batch["attention_mask"],
            "token_type_ids": batch["token_type_ids"],
        })[0]
        onnx_probs = F.softmax(torch.from_numpy(onnx_logits), dim=1).numpy()
        argmax_agree += int((torch_probs.argmax(1) == onnx_probs.argmax(1)).sum())
        max_diff = max(max_diff, float(np.abs(torch_probs - onnx_probs).max()))

    n = len(samples)
    return {"n_samples": n, "argmax_agreement": round(argmax_agree / n, 4),
            "max_prob_diff": round(max_diff, 6), "precision": precision}


# ── 主流程 ──

def main() -> int:
    parser = argparse.ArgumentParser(description="rbt3 意图分类微调 + 校准 + ONNX 导出")
    parser.add_argument("--train-data", default="data/nlu_train_train.json")
    parser.add_argument("--val-data", default="data/nlu_train_val.json")
    parser.add_argument("--eval-set", default="data/nlu_eval.json")
    parser.add_argument("--pretrained", default=str(PRETRAINED_DIR))
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--llrd-decay", type=float, default=0.7,
                        help="分层学习率衰减系数（每深一层乘它）")
    parser.add_argument("--patience", type=int, default=4, help="早停容忍轮数")
    parser.add_argument("--max-len", type=int, default=32,
                        help="语料最长 21 字符，32 token 覆盖 [CLS]+文本+[SEP]")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--skip-train", action="store_true",
                        help="复用 FINETUNED_DIR 已有权重，只走校准+导出")
    parser.add_argument("--precision", choices=["fp16", "int8", "fp32"],
                        default="fp16",
                        help="导出精度：fp16 默认（无损）；int8 更快更小但有翻转")
    args = parser.parse_args()

    for path in (args.train_data, args.val_data, args.eval_set):
        if not Path(path).exists():
            logger.error("缺少数据文件：%s", path)
            return 1
    if not Path(args.pretrained, "config.json").exists():
        logger.error("预训练底座缺失 %s，先跑 scripts/download_rbt3.py", args.pretrained)
        return 1

    train_samples = load_json(args.train_data)
    val_samples = load_json(args.val_data)
    eval_samples = load_json(args.eval_set)
    logger.info("数据：train=%d val=%d eval=%d", len(train_samples), len(val_samples),
                len(eval_samples))

    # ── 加载/微调 ──
    from transformers import AutoModelForSequenceClassification

    label2id = {name: i for i, name in enumerate(INTENT_CLASSES)}
    id2label = {i: name for i, name in enumerate(INTENT_CLASSES)}

    if args.skip_train:
        logger.info("跳过训练，加载已微调权重 %s", FINETUNED_DIR)
        model = AutoModelForSequenceClassification.from_pretrained(FINETUNED_DIR)
        finetune_info = {"skipped": True}
    else:
        model = AutoModelForSequenceClassification.from_pretrained(
            args.pretrained, num_labels=NUM_CLASSES, label2id=label2id, id2label=id2label,
        )
    model.to(args.device)

    encoder = BertTextEncoder(Path(args.pretrained) / "vocab.txt", args.max_len)

    if not args.skip_train:
        finetune_info = finetune(
            model, encoder, train_samples, val_samples, args.device,
            epochs=args.epochs, batch_size=args.batch_size, lr=args.lr,
            weight_decay=args.weight_decay, patience=args.patience, seed=args.seed,
            llrd_decay=args.llrd_decay,
        )
        FINETUNED_DIR.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(FINETUNED_DIR)
        shutil.copyfile(Path(args.pretrained) / "vocab.txt", FINETUNED_DIR / "vocab.txt")
        logger.info("微调权重已保存：%s（best epoch=%d, val_acc=%.4f）",
                    FINETUNED_DIR, finetune_info["best_epoch"], finetune_info["best_val_acc"])

    # ── 温度校准（验证集）──
    model.eval()
    val_logits, val_labels = collect_logits(model, encoder, val_samples, args.device)
    confs_before, accs_before, _ = eval_logits_accuracy(val_logits, val_labels, 1.0)
    ece_before = compute_ece(confs_before, accs_before)
    temperature, final_nll = learn_temperature(val_logits, val_labels)
    confs_after, accs_after, val_acc = eval_logits_accuracy(val_logits, val_labels, temperature)
    ece_after = compute_ece(confs_after, accs_after)
    logger.info("校准：T=%.4f  ECE %.4f→%.4f  val_acc=%.4f",
                temperature, ece_before["ece"], ece_after["ece"], val_acc)
    # 温度只许平滑置信度，不许破坏排序（负/极端 T 曾让 val_acc 归零）
    if val_acc < accs_before.mean() - 0.02:
        logger.error("温度校准后 val_acc 崩塌（%.4f → %.4f），T=%s 异常",
                     accs_before.mean(), val_acc, temperature)
        return 1

    # ── 分布外评估集 ──
    eval_logits, eval_labels = collect_logits(model, encoder, eval_samples, args.device)
    _, _, eval_acc = eval_logits_accuracy(eval_logits, eval_labels, temperature)
    per_class = {}
    errors = []
    probs = F.softmax(eval_logits / temperature, dim=1)
    preds = probs.argmax(dim=1)
    for idx, s in enumerate(eval_samples):
        ok = int(preds[idx]) == INTENT_CLASSES.index(s["intent"])
        per_class.setdefault(s["intent"], [0, 0])
        per_class[s["intent"]][1] += 1
        per_class[s["intent"]][0] += ok
        if not ok:
            errors.append({"text": s["text"], "expected": s["intent"],
                           "predicted": INTENT_CLASSES[int(preds[idx])],
                           "confidence": round(float(probs[idx].max()), 4)})
    logger.info("评估集：%d/%d = %.4f", int(preds.eq(eval_labels).sum()), len(eval_samples),
                eval_acc)
    for e in errors:
        logger.info("  错例 %r → %s (conf=%.2f, 期望 %s)",
                    e["text"], e["predicted"], e["confidence"], e["expected"])

    # ── ONNX 导出 + parity ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_final = OUTPUT_DIR / "model.onnx"
    export_info = export_onnx(model, encoder,
                              encoder.encode_batch([s["text"] for s in val_samples[:2]]),
                              out_final, args.precision)
    parity = onnx_parity_check(out_final, encoder, val_samples + eval_samples,
                               model, args.device, args.precision)
    logger.info("ONNX parity：argmax 一致 %s，最大概率差 %s",
                parity["argmax_agreement"], parity["max_prob_diff"])
    if args.precision == "fp16" and (parity["argmax_agreement"] < 0.995
                                     or parity["max_prob_diff"] > 0.01):
        logger.error("fp16 parity 不达标（应≈1.0/~1e-3），产物不可信，请排查")
        return 1

    # ── 产物落盘 ──
    shutil.copyfile(Path(args.pretrained) / "vocab.txt", OUTPUT_DIR / "vocab.txt")

    intent_config = {
        "model_type": "rbt3-onnx",
        "base": "hfl/rbt3",
        "precision": args.precision,
        "export_info": export_info,
        "labels": INTENT_CLASSES,
        "max_len": args.max_len,
        "temperature": round(temperature, 4),
        "tokenizer": {"type": "bert-wordpiece", "lowercase": True,
                      "pad_token": "[PAD]", "pad_id": 0},
        "inputs": ["input_ids", "attention_mask", "token_type_ids"],
        "output": "logits",
        "exported_at": datetime.now().isoformat(),
        "val_acc": round(val_acc, 4),
        "eval_acc": round(eval_acc, 4),
        "onnx_parity": parity,
    }
    with open(OUTPUT_DIR / "intent_config.json", "w", encoding="utf-8") as f:
        json.dump(intent_config, f, ensure_ascii=False, indent=2)

    calibration_report = {
        "model": "IntentBertClassifier (hfl/rbt3)",
        "method": "Temperature Scaling (Guo et al. 2017)",
        "n_samples": len(val_samples),
        "temperature": round(temperature, 4),
        "final_nll": round(final_nll, 4),
        "before": {"accuracy": round(float(accs_before.mean()), 4),
                   "ece": ece_before["ece"], "mce": ece_before["mce"]},
        "after": {"accuracy": round(val_acc, 4),
                  "ece": ece_after["ece"], "mce": ece_after["mce"]},
        "ece_reduction": round(ece_before["ece"] - ece_after["ece"], 4),
        "reliability_before": ece_before,
        "reliability_after": ece_after,
        "timestamp": datetime.now().isoformat(),
    }
    with open(OUTPUT_DIR / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calibration_report, f, ensure_ascii=False, indent=2)

    train_report = {
        "model": "IntentBertClassifier (hfl/rbt3 ONNX)",
        "timestamp": datetime.now().isoformat(),
        "config": {"epochs": args.epochs, "batch_size": args.batch_size, "lr": args.lr,
                   "weight_decay": args.weight_decay, "llrd_decay": args.llrd_decay,
                   "patience": args.patience, "max_len": args.max_len, "seed": args.seed,
                   "device": args.device, "precision": args.precision,
                   "skipped_training": bool(args.skip_train)},
        "training": finetune_info,
        "calibration": {"temperature": round(temperature, 4),
                        "ece_before": ece_before["ece"], "ece_after": ece_after["ece"]},
        "results": {"val_acc": round(val_acc, 4), "eval_acc": round(eval_acc, 4),
                    "eval_total": len(eval_samples),
                    "per_class": {k: {"correct": v[0], "total": v[1]}
                                  for k, v in sorted(per_class.items())},
                    "errors": errors},
        "artifacts": {"model": str(out_final), "parity": parity},
    }
    with open(TRAIN_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(train_report, f, ensure_ascii=False, indent=2)

    # ── 摘要 ──
    print("\n" + "=" * 60)
    print("rbt3 意图模型管线完成")
    print("=" * 60)
    print(f"  best epoch        : {finetune_info.get('best_epoch', 'N/A')}")
    print(f"  val_acc           : {val_acc:.4f}")
    print(f"  eval_acc (84句)   : {int(round(eval_acc * len(eval_samples)))}/{len(eval_samples)}"
          f" = {eval_acc:.4f}")
    print(f"  temperature       : {temperature:.4f}")
    print(f"  ECE               : {ece_before['ece']} → {ece_after['ece']}")
    print(f"  ONNX parity       : argmax {parity['argmax_agreement']}, "
          f"maxdiff {parity['max_prob_diff']}")
    print(f"  产物              : {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
