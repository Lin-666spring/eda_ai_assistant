"""NLU 意图分类器训练脚本

使用方式:
    # 先生成数据
    python src/ml/generate_nlu_data.py --count 60

    # 训练
    python src/ml/train_intent.py

    # 指定参数
    python src/ml/train_intent.py --epochs 30 --batch-size 32 --lr 0.001

输出:
    data/intent_model.pt     — 模型权重
    data/vocab.json          — 词表
    data/nlu_train_report.json — 训练报告
"""

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# 确保 src 在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ml.vocab import PCBVocab
from src.ml.intent_classifier import (
    IntentClassifier,
    INTENT_CLASSES,
    INTENT_TO_IDX,
    NUM_CLASSES,
    DEFAULT_CONFIG,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Dataset ──

class NLUDataset(Dataset):
    """NLU 意图分类 Dataset"""

    def __init__(self, samples: list[dict], vocab: PCBVocab, max_len: int = 128):
        self.samples = samples
        self.vocab = vocab
        self.max_len = max_len

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        ids = self.vocab.encode(sample["text"])

        # Pad / truncate
        if len(ids) > self.max_len:
            ids = ids[:self.max_len]
        else:
            ids = ids + [self.vocab.pad_id] * (self.max_len - len(ids))

        label = INTENT_TO_IDX.get(sample["intent"], 0)

        return {
            "input_ids": torch.tensor(ids, dtype=torch.long),
            "label": torch.tensor(label, dtype=torch.long),
        }


# ── 训练 ──

def train(
    train_path: str = "data/nlu_train_train.json",
    val_path: str = "data/nlu_train_val.json",
    model_output: str = "data/intent_model.pt",
    vocab_output: str = "data/vocab.json",
    report_output: str = "data/nlu_train_report.json",
    epochs: int = 25,
    batch_size: int = 32,
    lr: float = 0.001,
    weight_decay: float = 1e-4,
    device: str = "cpu",
    seed: int = 42,
) -> dict:
    """训练入口"""

    # 设置随机种子
    random.seed(seed)
    torch.manual_seed(seed)

    logger.info("=" * 60)
    logger.info("NLU Intent Classifier — 训练")
    logger.info("=" * 60)

    # 加载数据
    logger.info("加载数据: %s", train_path)
    with open(train_path, "r", encoding="utf-8") as f:
        train_samples = json.load(f)
    logger.info("加载数据: %s", val_path)
    with open(val_path, "r", encoding="utf-8") as f:
        val_samples = json.load(f)

    logger.info("训练集: %d 条, 验证集: %d 条", len(train_samples), len(val_samples))

    # 统计类别分布
    from collections import Counter
    train_dist = Counter(s["intent"] for s in train_samples)
    logger.info("训练集类别分布: %s", dict(train_dist))

    # 构建词表
    logger.info("构建词表...")
    vocab = PCBVocab()
    logger.info("词表大小: %d", len(vocab))

    # 保存词表
    vocab.save(vocab_output)

    # 创建 Dataset / DataLoader
    max_len = DEFAULT_CONFIG["max_len"]
    train_dataset = NLUDataset(train_samples, vocab, max_len)
    val_dataset = NLUDataset(val_samples, vocab, max_len)

    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        drop_last=False,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        drop_last=False,
    )

    # 创建模型
    model = IntentClassifier(vocab_size=len(vocab))
    model.to(device)
    logger.info("模型参数: %.1fK", model._count_params() / 1000)

    # 损失函数 & 优化器
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        model.parameters(), lr=lr, weight_decay=weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=epochs, eta_min=lr * 0.01,
    )

    # 训练循环
    best_val_acc = 0.0
    best_epoch = 0
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for epoch in range(1, epochs + 1):
        # ── 训练 ──
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            labels = batch["label"].to(device)

            optimizer.zero_grad()
            logits = model(input_ids)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * input_ids.size(0)

        train_loss /= len(train_dataset)
        scheduler.step()

        # ── 验证 ──
        model.eval()
        val_loss = 0.0
        correct = 0
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                labels = batch["label"].to(device)

                logits = model(input_ids)
                loss = criterion(logits, labels)
                val_loss += loss.item() * input_ids.size(0)

                preds = logits.argmax(dim=1)
                correct += (preds == labels).sum().item()

        val_loss /= len(val_dataset)
        val_acc = correct / len(val_dataset)

        history["train_loss"].append(round(train_loss, 4))
        history["val_loss"].append(round(val_loss, 4))
        history["val_acc"].append(round(val_acc, 4))

        # 标记最佳
        marker = ""
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            marker = " *"

        logger.info(
            "Epoch %3d/%d | train_loss=%.4f | val_loss=%.4f | val_acc=%.2f%%%s",
            epoch, epochs, train_loss, val_loss, val_acc * 100, marker,
        )

    # ── 保存模型 ──
    model.save(model_output)
    logger.info("最佳模型: epoch=%d, val_acc=%.2f%%", best_epoch, best_val_acc * 100)

    # ── 按类别评估 ──
    model.eval()
    class_correct = {name: 0 for name in INTENT_CLASSES}
    class_total = {name: 0 for name in INTENT_CLASSES}

    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch["input_ids"].to(device)
            labels = batch["label"].to(device)
            logits = model(input_ids)
            preds = logits.argmax(dim=1)

            for pred, label in zip(preds, labels):
                class_name = INTENT_CLASSES[label.item()]
                class_total[class_name] += 1
                if pred == label:
                    class_correct[class_name] += 1

    per_class = {}
    logger.info("按类别准确率:")
    for name in INTENT_CLASSES:
        total = class_total[name]
        correct = class_correct[name]
        acc = correct / total if total > 0 else 0.0
        per_class[name] = {"total": total, "correct": correct, "accuracy": round(acc, 4)}
        logger.info("  %-20s  %2d/%2d  %.1f%%", name, correct, total, acc * 100)

    # ── 报告 ──
    report = {
        "model": "IntentClassifier (TextCNN)",
        "timestamp": datetime.now().isoformat(),
        "config": DEFAULT_CONFIG.copy(),
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": lr,
            "weight_decay": weight_decay,
            "train_samples": len(train_samples),
            "val_samples": len(val_samples),
            "best_epoch": best_epoch,
            "best_val_acc": round(best_val_acc, 4),
        },
        "results": {
            "train_loss_final": history["train_loss"][-1],
            "val_loss_final": history["val_loss"][-1],
            "val_acc_final": history["val_acc"][-1],
            "per_class": per_class,
        },
        "history": history,
    }

    with open(report_output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("报告已保存: %s", report_output)
    logger.info("训练完成!")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="训练 NLU 意图分类器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--train-data", default="data/nlu_train_train.json",
                        help="训练数据路径")
    parser.add_argument("--val-data", default="data/nlu_train_val.json",
                        help="验证数据路径")
    parser.add_argument("--model-output", default="data/intent_model.pt",
                        help="模型输出路径")
    parser.add_argument("--vocab-output", default="data/vocab.json",
                        help="词表输出路径")
    parser.add_argument("--report-output", default="data/nlu_train_report.json",
                        help="训练报告路径")
    parser.add_argument("--epochs", type=int, default=25,
                        help="训练轮数 (default: 25)")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="批次大小 (default: 32)")
    parser.add_argument("--lr", type=float, default=0.001,
                        help="学习率 (default: 0.001)")
    parser.add_argument("--weight-decay", type=float, default=1e-4,
                        help="权重衰减 (default: 1e-4)")
    parser.add_argument("--device", default="cpu",
                        help="训练设备 (default: cpu)")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子 (default: 42)")

    args = parser.parse_args()

    # 确保 data 目录存在
    Path("data").mkdir(parents=True, exist_ok=True)

    train(
        train_path=args.train_data,
        val_path=args.val_data,
        model_output=args.model_output,
        vocab_output=args.vocab_output,
        report_output=args.report_output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        device=args.device,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
