"""模型置信度校准 — Temperature Scaling + ECE 评估

对 IntentClassifier 和 ComponentClassifier 做 Temperature Scaling，
让 softmax 输出的置信度等于实际正确概率。

方法参考:
  Guo et al. (2017) "On Calibration of Modern Neural Networks"
  Temperature Scaling: argmin_T NLL on validation set

使用方式:
    python src/ml/calibrate.py                           # 校准两个模型
    python src/ml/calibrate.py --model intent            # 仅校准意图模型
    python src/ml/calibrate.py --model component         # 仅校准元件模型
    python src/ml/calibrate.py --report-only             # 仅输出报告（不训练）

输出:
    data/intent_model_calibrated.pt   — 校准后的意图模型（含 temperature）
    data/component_model_calibrated.pt — 校准后的元件模型
    data/calibration_report.json      — 校准报告（含 ECE）
"""

import argparse
import json
import logging
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ml.vocab import PCBVocab
from src.ml.intent_classifier import (
    IntentClassifier, IntentPredictor,
    INTENT_CLASSES, NUM_CLASSES as INTENT_NUM,
    DEFAULT_CONFIG as INTENT_CONFIG,
)
from src.ml.component_classifier import (
    ComponentClassifier, ComponentPredictor,
    COMPONENT_CLASSES, NUM_COMPONENT_CLASSES,
    DEFAULT_COMPONENT_CONFIG,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── ECE 计算 ──

def compute_ece(confidences: np.ndarray, accuracies: np.ndarray, n_bins: int = 10) -> dict:
    """计算 Expected Calibration Error (ECE)

    ECE = Σ (|B_m| / n) * |acc(B_m) - conf(B_m)|

    Args:
        confidences: 每个预测的置信度 (n,)
        accuracies: 每个预测是否正确 (n,) 0/1
        n_bins: 分桶数

    Returns:
        {"ece": float, "mce": float, "bins": [{bin_start, bin_end, count, acc, conf, gap}], ...}
    """
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bin_results = []
    total = len(confidences)

    ece_sum = 0.0
    mce = 0.0

    for i in range(n_bins):
        mask = (confidences >= bins[i]) & (confidences < bins[i + 1])
        # 最后一个 bin 包含 1.0
        if i == n_bins - 1:
            mask = (confidences >= bins[i]) & (confidences <= bins[i + 1])

        count = mask.sum()
        if count == 0:
            bin_results.append({
                "bin_start": round(bins[i], 2),
                "bin_end": round(bins[i + 1], 2),
                "count": 0, "acc": None, "conf": None, "gap": None,
            })
            continue

        bin_acc = accuracies[mask].mean()
        bin_conf = confidences[mask].mean()
        gap = abs(bin_acc - bin_conf)

        ece_sum += (count / total) * gap
        mce = max(mce, gap)

        bin_results.append({
            "bin_start": round(bins[i], 2),
            "bin_end": round(bins[i + 1], 2),
            "count": int(count),
            "acc": round(float(bin_acc), 4),
            "conf": round(float(bin_conf), 4),
            "gap": round(float(gap), 4),
        })

    return {
        "ece": round(float(ece_sum), 4),
        "mce": round(float(mce), 4),
        "n_bins": n_bins,
        "n_samples": total,
        "bins": bin_results,
    }


def reliability_diagram_data(confidences: np.ndarray, accuracies: np.ndarray, n_bins: int = 10) -> dict:
    """生成可靠性图数据（JSON 友好格式）

    Returns:
        {"perfect": [[0,0],[1,1]], "calibrated": [[conf,acc],...], "ece": float}
    """
    result = compute_ece(confidences, accuracies, n_bins)
    points = []
    for b in result["bins"]:
        if b["conf"] is not None:
            points.append([b["conf"], b["acc"]])
    return {
        "perfect": [[0.0, 0.0], [1.0, 1.0]],
        "calibrated": points,
        "ece": result["ece"],
        "mce": result["mce"],
        "n_samples": result["n_samples"],
    }


# ── Temperature Scaling ──

class TemperatureScaledModel(torch.nn.Module):
    """在原始模型 logits 上除以 temperature 参数"""

    def __init__(self, base_model: torch.nn.Module, temperature: float = 1.0):
        super().__init__()
        self.base_model = base_model
        self.temperature = torch.nn.Parameter(torch.tensor(temperature))

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        logits = self.base_model(input_ids)
        return logits / self.temperature


def learn_temperature(
    model: torch.nn.Module,
    dataloader: DataLoader,
    device: str = "cpu",
    lr: float = 0.01,
    max_iter: int = 200,
) -> tuple[float, float]:
    """在验证集上学习最优温度参数

    优化目标: NLL loss on validation set

    Returns:
        (optimal_temperature, final_nll)
    """
    # Freeze base model
    for param in model.parameters():
        param.requires_grad = False

    # Wrap with temperature
    temperature_param = torch.nn.Parameter(torch.tensor(1.5))  # Start > 1 for safety
    optimizer = torch.optim.LBFGS([temperature_param], lr=lr, max_iter=max_iter)

    nll_criterion = torch.nn.CrossEntropyLoss()
    all_labels = []
    for batch in dataloader:
        all_labels.append(batch["label"])
    all_labels = torch.cat(all_labels).to(device)

    all_logits = []
    model.eval()
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            logits = model(input_ids)
            all_logits.append(logits)
    all_logits = torch.cat(all_logits).to(device)

    def closure():
        optimizer.zero_grad()
        scaled_logits = all_logits / temperature_param
        loss = nll_criterion(scaled_logits, all_labels)
        loss.backward()
        return loss

    optimizer.step(closure)

    optimal_t = temperature_param.item()
    final_nll = nll_criterion(all_logits / optimal_t, all_labels).item()

    logger.info("Optimal temperature: %.4f, NLL: %.4f", optimal_t, final_nll)
    return optimal_t, final_nll


# ── 模型评估 ──

def evaluate_model(
    model: torch.nn.Module,
    dataloader: DataLoader,
    temperature: float = 1.0,
    device: str = "cpu",
) -> tuple[np.ndarray, np.ndarray, float]:
    """评估模型并返回置信度、正确性、准确率

    Returns:
        (confidences, accuracies, overall_accuracy)
    """
    model.eval()
    all_confidences = []
    all_accuracies = []
    correct = 0
    total = 0

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            labels = batch["label"].to(device)
            logits = model(input_ids)
            probs = F.softmax(logits / temperature, dim=1)
            preds = probs.argmax(dim=1)
            confs = probs.max(dim=1).values

            all_confidences.append(confs.cpu().numpy())
            all_accuracies.append((preds == labels).cpu().numpy().astype(float))
            correct += (preds == labels).sum().item()
            total += len(labels)

    confidences = np.concatenate(all_confidences)
    accuracies = np.concatenate(all_accuracies)
    accuracy = correct / total if total > 0 else 0.0

    return confidences, accuracies, accuracy


# ── 主流程 ──

def calibrate_intent_model(
    val_path: str = "data/nlu_train_val.json",
    model_path: str = "data/intent_model.pt",
    vocab_path: str = "data/vocab.json",
    output_path: str = "data/intent_model_calibrated.pt",
    device: str = "cpu",
) -> dict:
    """校准意图分类模型"""
    logger.info("=" * 50)
    logger.info("Calibrating: IntentClassifier")
    logger.info("=" * 50)

    # 加载
    vocab = PCBVocab.load(vocab_path)
    with open(val_path, "r", encoding="utf-8") as f:
        val_samples = json.load(f)
    model = IntentClassifier.load(model_path, device=device)

    # 构建 DataLoader
    from src.ml.train_intent import NLUDataset
    dataset = NLUDataset(val_samples, vocab, INTENT_CONFIG["max_len"])
    loader = DataLoader(dataset, batch_size=32, shuffle=False)

    # 校准前评估
    logger.info("评估校准前...")
    confs_before, accs_before, acc = evaluate_model(model, loader, temperature=1.0, device=device)
    ece_before = compute_ece(confs_before, accs_before)
    logger.info("校准前: acc=%.4f, ECE=%.4f, MCE=%.4f", acc, ece_before["ece"], ece_before["mce"])

    # 学习温度
    logger.info("学习温度参数...")
    T, nll = learn_temperature(model, loader, device=device)

    # 校准后评估
    logger.info("评估校准后...")
    confs_after, accs_after, acc2 = evaluate_model(model, loader, temperature=T, device=device)
    ece_after = compute_ece(confs_after, accs_after)
    logger.info("校准后: acc=%.4f, ECE=%.4f, MCE=%.4f", acc2, ece_after["ece"], ece_after["mce"])

    # 保存校准后的模型（含 temperature）
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    checkpoint["temperature"] = T
    torch.save(checkpoint, output_path)
    logger.info("Calibrated model saved: %s (T=%.4f)", output_path, T)

    return {
        "model": "IntentClassifier",
        "n_samples": len(val_samples),
        "temperature": round(T, 4),
        "before": {
            "accuracy": round(acc, 4),
            "ece": ece_before["ece"],
            "mce": ece_before["mce"],
        },
        "after": {
            "accuracy": round(acc2, 4),
            "ece": ece_after["ece"],
            "mce": ece_after["mce"],
        },
        "ece_reduction": round(ece_before["ece"] - ece_after["ece"], 4),
        "reliability_before": reliability_diagram_data(confs_before, accs_before),
        "reliability_after": reliability_diagram_data(confs_after, accs_after),
    }


def calibrate_component_model(
    val_path: str = "data/component_train_val.json",
    model_path: str = "data/component_model.pt",
    vocab_path: str = "data/vocab.json",
    output_path: str = "data/component_model_calibrated.pt",
    device: str = "cpu",
) -> dict:
    """校准元件分类模型"""
    logger.info("=" * 50)
    logger.info("Calibrating: ComponentClassifier")
    logger.info("=" * 50)

    # 加载
    vocab = PCBVocab.load(vocab_path)
    with open(val_path, "r", encoding="utf-8") as f:
        val_samples = json.load(f)
    model = ComponentClassifier.load(model_path, device=device)

    # 构建 DataLoader
    from src.ml.train_component import ComponentDataset
    dataset = ComponentDataset(val_samples, vocab, DEFAULT_COMPONENT_CONFIG["max_len"])
    loader = DataLoader(dataset, batch_size=32, shuffle=False)

    # 校准前评估
    logger.info("评估校准前...")
    confs_before, accs_before, acc = evaluate_model(model, loader, temperature=1.0, device=device)
    ece_before = compute_ece(confs_before, accs_before)
    logger.info("校准前: acc=%.4f, ECE=%.4f, MCE=%.4f", acc, ece_before["ece"], ece_before["mce"])

    # 学习温度
    logger.info("学习温度参数...")
    T, nll = learn_temperature(model, loader, device=device)

    # 校准后评估
    logger.info("评估校准后...")
    confs_after, accs_after, acc2 = evaluate_model(model, loader, temperature=T, device=device)
    ece_after = compute_ece(confs_after, accs_after)
    logger.info("校准后: acc=%.4f, ECE=%.4f, MCE=%.4f", acc2, ece_after["ece"], ece_after["mce"])

    # 保存
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    checkpoint["temperature"] = T
    torch.save(checkpoint, output_path)
    logger.info("Calibrated model saved: %s (T=%.4f)", output_path, T)

    return {
        "model": "ComponentClassifier",
        "n_samples": len(val_samples),
        "temperature": round(T, 4),
        "before": {
            "accuracy": round(acc, 4),
            "ece": ece_before["ece"],
            "mce": ece_before["mce"],
        },
        "after": {
            "accuracy": round(acc2, 4),
            "ece": ece_after["ece"],
            "mce": ece_after["mce"],
        },
        "ece_reduction": round(ece_before["ece"] - ece_after["ece"], 4),
        "reliability_before": reliability_diagram_data(confs_before, accs_before),
        "reliability_after": reliability_diagram_data(confs_after, accs_after),
    }


def update_predictor_with_temperature(
    model_path: str,
    output_path: str,
    temperature: float,
) -> None:
    """更新模型文件中的 temperature 参数（用于 predictor 加载）"""
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    checkpoint["temperature"] = temperature
    torch.save(checkpoint, output_path)


def main():
    parser = argparse.ArgumentParser(description="模型置信度校准 (Temperature Scaling)")
    parser.add_argument("--model", choices=["intent", "component", "both"],
                        default="both", help="要校准的模型")
    parser.add_argument("--device", default="cpu", help="设备")
    parser.add_argument("--report-only", action="store_true",
                        help="仅输出报告，不重新学习温度")
    args = parser.parse_args()

    results = []
    timestamp = datetime.now().isoformat()

    if args.model in ("intent", "both"):
        if args.report_only:
            # 仅读已有校准结果
            logger.info("报告模式：跳过温度学习")
        result = calibrate_intent_model(device=args.device)
        results.append(result)

    if args.model in ("component", "both"):
        result = calibrate_component_model(device=args.device)
        results.append(result)

    # ── 生成综合报告 ──
    report = {
        "timestamp": timestamp,
        "method": "Temperature Scaling (Guo et al. 2017)",
        "results": results,
        "summary": {
            "total_models": len(results),
            "avg_ece_before": round(np.mean([r["before"]["ece"] for r in results]), 4),
            "avg_ece_after": round(np.mean([r["after"]["ece"] for r in results]), 4),
            "total_ece_reduction": round(sum(r["ece_reduction"] for r in results), 4),
        },
    }

    report_path = "data/calibration_report.json"
    Path("data").mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("校准报告: %s", report_path)

    # ── 打印摘要 ──
    print("\n" + "=" * 60)
    print("置信度校准报告")
    print("=" * 60)
    for r in results:
        print(f"\n{r['model']}:")
        print(f"  Temperature: T = {r['temperature']:.4f}")
        print(f"  校准前: acc={r['before']['accuracy']:.4f}, ECE={r['before']['ece']:.4f}")
        print(f"  校准后: acc={r['after']['accuracy']:.4f}, ECE={r['after']['ece']:.4f}")
        print(f"  ECE 降低: {r['ece_reduction']:.4f}")
    print(f"\n平均 ECE: {report['summary']['avg_ece_before']:.4f} → {report['summary']['avg_ece_after']:.4f}")


if __name__ == "__main__":
    main()
