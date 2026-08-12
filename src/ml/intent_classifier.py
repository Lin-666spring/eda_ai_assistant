"""自研轻量 NLU 意图分类器 — 字符级 TextCNN

架构：
  输入文本 → 字符 Embedding → 多尺度 Conv1D → GlobalMaxPool → FC → 10类输出

特点：
  - 纯字符级，无需分词，中文英文混合自然处理
  - 参数量 ~600K，模型文件 < 3MB
  - CPU 推理 < 1ms/条
  - 可独立于云端 API 离线运行

参考：
  - Kim, Y. (2014) "Convolutional Neural Networks for Sentence Classification"
  - Zhang & LeCun (2015) "Character-level Convolutional Networks for Text Classification"
"""

import logging
import os
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .vocab import PCBVocab, DEFAULT_VOCAB_SIZE

logger = logging.getLogger(__name__)

# ── 10 个意图类（与 src/agent/router.py TaskIntent 对齐）──
INTENT_CLASSES = [
    "TEXT_CHAT",
    "BOM_ANALYSIS",
    "BOM_HEALTH",
    "RULE_CHECK",
    "PCB_ANALYSIS",
    "CODE_RULE_GEN",
    "REPORT_GEN",
    "COMPONENT_LOOKUP",
    "VISUAL",
    "LOCAL_ONLY",
]

INTENT_TO_IDX = {name: i for i, name in enumerate(INTENT_CLASSES)}
IDX_TO_INTENT = {i: name for i, name in enumerate(INTENT_CLASSES)}
NUM_CLASSES = len(INTENT_CLASSES)

# ── 模型超参数 ──
DEFAULT_CONFIG = {
    "vocab_size": DEFAULT_VOCAB_SIZE,  # ~5000+ chars
    "embed_dim": 96,                   # 字符嵌入维度
    "kernel_sizes": [2, 3, 4, 5],      # 多尺度卷积核
    "num_filters": 64,                  # 每个尺度的滤波器数
    "dropout": 0.3,                     # Dropout 概率
    "hidden_dim": 64,                   # FC 隐层维度
    "max_len": 128,                     # 最大输入长度
    "num_classes": NUM_CLASSES,
}


class IntentClassifier(nn.Module):
    """字符级 TextCNN 意图分类器

    使用方式:
        vocab = PCBVocab()
        model = IntentClassifier(vocab_size=len(vocab))
        logits = model(input_ids)  # (batch, num_classes)
    """

    def __init__(self, vocab_size: int = DEFAULT_VOCAB_SIZE, **kwargs):
        super().__init__()

        cfg = {**DEFAULT_CONFIG, "vocab_size": vocab_size, **kwargs}

        self.vocab_size = cfg["vocab_size"]
        self.embed_dim = cfg["embed_dim"]
        self.kernel_sizes = cfg["kernel_sizes"]
        self.num_filters = cfg["num_filters"]
        self.dropout_rate = cfg["dropout"]
        self.hidden_dim = cfg["hidden_dim"]
        self.max_len = cfg["max_len"]
        self.num_classes = cfg["num_classes"]
        self.temperature = cfg.get("temperature", 1.0)

        # 字符嵌入层
        self.embedding = nn.Embedding(
            self.vocab_size, self.embed_dim, padding_idx=0
        )

        # 多尺度卷积
        self.convs = nn.ModuleList([
            nn.Conv1d(
                in_channels=self.embed_dim,
                out_channels=self.num_filters,
                kernel_size=k,
                padding="same",
            )
            for k in self.kernel_sizes
        ])

        # 分类头
        total_filters = self.num_filters * len(self.kernel_sizes)
        self.dropout = nn.Dropout(self.dropout_rate)
        self.fc1 = nn.Linear(total_filters, self.hidden_dim)
        self.fc2 = nn.Linear(self.hidden_dim, self.num_classes)

        # 初始化
        self._init_weights()

        logger.info(
            "IntentClassifier: vocab=%d, embed=%d, kernels=%s, filters=%d/%d, params=%.1fK",
            self.vocab_size, self.embed_dim, self.kernel_sizes,
            self.num_filters, total_filters, self._count_params() / 1000,
        )

    def _init_weights(self):
        """Xavier 初始化"""
        nn.init.xavier_uniform_(self.embedding.weight)
        for conv in self.convs:
            nn.init.xavier_uniform_(conv.weight)
            if conv.bias is not None:
                nn.init.zeros_(conv.bias)
        nn.init.xavier_uniform_(self.fc1.weight)
        nn.init.zeros_(self.fc1.bias)
        nn.init.xavier_uniform_(self.fc2.weight)
        nn.init.zeros_(self.fc2.bias)

    def _count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        """前向传播

        Args:
            input_ids: (batch, seq_len) int64 tensor

        Returns:
            logits: (batch, num_classes) float32 tensor
        """
        # Embedding + 调整维度给 Conv1d
        # (batch, seq_len, embed_dim) → (batch, embed_dim, seq_len)
        x = self.embedding(input_ids).transpose(1, 2)

        # 多尺度卷积 + GlobalMaxPool
        conv_outputs = []
        for conv in self.convs:
            y = conv(x)                     # (batch, filters, seq_len)
            y = F.relu(y)
            y = F.max_pool1d(y, y.size(2))  # (batch, filters, 1)
            conv_outputs.append(y.squeeze(2))

        # 拼接所有尺度特征
        x = torch.cat(conv_outputs, dim=1)  # (batch, total_filters)

        # 分类头
        x = self.dropout(x)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)                     # (batch, num_classes)

        return x

    def predict(self, input_ids: torch.Tensor) -> tuple[list[str], list[float]]:
        """推理并返回意图名和置信度（应用校准 temperature）

        Returns:
            intents: 意图名列表
            confidences: softmax 置信度列表
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(input_ids) / self.temperature
            probs = F.softmax(logits, dim=1)
            best_idx = probs.argmax(dim=1)
            intents = [IDX_TO_INTENT[i.item()] for i in best_idx]
            confidences = probs.max(dim=1).values.tolist()
        return intents, confidences

    def save(self, path: str) -> None:
        """保存模型权重（含校准 temperature）"""
        torch.save(
            {
                "state_dict": self.state_dict(),
                "config": {
                    "vocab_size": self.vocab_size,
                    "embed_dim": self.embed_dim,
                    "kernel_sizes": self.kernel_sizes,
                    "num_filters": self.num_filters,
                    "dropout": self.dropout_rate,
                    "hidden_dim": self.hidden_dim,
                    "max_len": self.max_len,
                    "num_classes": self.num_classes,
                },
                "temperature": self.temperature,
            },
            path,
        )
        logger.info("Model saved: %.1fK params → %s", self._count_params() / 1000, path)

    @classmethod
    def load(cls, path: str, device: str = "cpu") -> "IntentClassifier":
        """加载模型权重（含校准 temperature）"""
        checkpoint = torch.load(path, map_location=device, weights_only=False)
        cfg = checkpoint.get("config", {})

        model = cls(**cfg)
        model.load_state_dict(checkpoint["state_dict"])
        model.temperature = checkpoint.get("temperature", 1.0)
        model.to(device)
        model.eval()

        logger.info(
            "Model loaded: %.1fK params, T=%.3f ← %s",
            model._count_params() / 1000, model.temperature, path,
        )
        return model


class IntentPredictor:
    """意图分类推理封装

    使用方式:
        vocab = PCBVocab.load("data/vocab.json")
        model = IntentClassifier.load("data/intent_model.pt")
        predictor = IntentPredictor(model, vocab)

        intent, confidence, debug = predictor.classify("检查电源走线")
        # → ("RULE_CHECK", 0.89, {"scores": {...}})
    """

    def __init__(
        self,
        model: IntentClassifier,
        vocab: PCBVocab,
        device: str = "cpu",
    ):
        self.model = model.to(device)
        self.vocab = vocab
        self.device = device
        self.max_len = model.max_len

        model.eval()
        logger.info("IntentPredictor ready: device=%s, max_len=%d", device, self.max_len)

    def classify(self, text: str) -> tuple[str, float, dict]:
        """分类用户输入

        Args:
            text: 用户输入文本

        Returns:
            intent_name: str — 意图名 (如 "RULE_CHECK")
            confidence: float — 置信度 0.0-1.0
            debug: dict — {"scores": {name: prob, ...}, "top_two": [...]}
        """
        if not text or not text.strip():
            return ("TEXT_CHAT", 0.0, {
                "scores": {}, "top_two": [], "reason": "empty_input",
            })

        # Tokenize
        ids = self.vocab.encode(text)

        # Truncate or pad
        if len(ids) > self.max_len:
            ids = ids[:self.max_len]
        else:
            ids = ids + [self.vocab.pad_id] * (self.max_len - len(ids))

        input_ids = torch.tensor([ids], dtype=torch.long, device=self.device)

        # 推理（应用校准 temperature）
        with torch.no_grad():
            logits = self.model(input_ids) / self.model.temperature
            probs = F.softmax(logits, dim=1).squeeze(0)

        # 构建 scores
        scores = {}
        for i, name in enumerate(INTENT_CLASSES):
            scores[name] = round(probs[i].item(), 4)

        # 排序
        sorted_items = sorted(scores.items(), key=lambda x: -x[1])
        best_name, confidence = sorted_items[0]
        top_two = sorted_items[:2]

        debug = {
            "scores": scores,
            "top_two": [(name, score) for name, score in top_two],
            "model": "local_textcnn",
        }

        return best_name, confidence, debug

    @staticmethod
    def from_path(
        model_path: str,
        vocab_path: str,
        device: str = "cpu",
    ) -> Optional["IntentPredictor"]:
        """从文件路径加载预测器"""
        try:
            vocab = PCBVocab.load(vocab_path)
            model = IntentClassifier.load(model_path, device=device)
            return IntentPredictor(model, vocab, device=device)
        except FileNotFoundError as e:
            logger.warning("Model file not found: %s", e)
            return None
        except Exception as e:
            logger.error("Failed to load IntentPredictor: %s", e)
            return None
