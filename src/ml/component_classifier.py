"""自研轻量 BOM 元件类型分类器 — 字符级 TextCNN

架构：
  输入字段拼接 → 字符 Embedding → 多尺度 Conv1D → GlobalMaxPool → FC → 12类输出

与 IntentClassifier 同架构，参数更大（~600K vs ~244K），分类更细（12类 vs 10类）。

使用方式:
    vocab = PCBVocab.load("data/vocab.json")
    model = ComponentClassifier(vocab_size=len(vocab))
    predictor = ComponentPredictor(model, vocab)

    comp_type, confidence, debug = predictor.classify(item)
    # → ("ic_mcu", 0.93, {"scores": {...}})
"""

import logging
import os
from typing import Optional, Union

import torch
import torch.nn as nn
import torch.nn.functional as F

from .vocab import PCBVocab, DEFAULT_VOCAB_SIZE

logger = logging.getLogger(__name__)

# ── 12 个元件细分类别 ──
COMPONENT_CLASSES = [
    "ic_mcu",        # 单片机/处理器/FPGA/CPLD/DSP
    "ic_power",      # 电源管理IC (LDO/DC-DC/稳压/电荷泵)
    "ic_analog",     # 模拟/接口IC (运放/比较器/ADC/DAC/USB芯片/电平转换)
    "ic_other",      # 其他IC (驱动/传感器/存储/RTC/逻辑门)
    "cap_mlcc",      # 陶瓷电容 (MLCC)
    "cap_elec",      # 电解/钽电容
    "resistor",      # 电阻 (贴片/排阻/功率/电位器)
    "inductor",      # 电感/磁珠/共模扼流圈
    "diode_led",     # 二极管/LED/TVS/稳压管
    "transistor",    # 三极管/MOSFET/IGBT/JFET
    "crystal",       # 晶振/振荡器/谐振器
    "connector",     # 连接器/开关/继电器/保险丝/测试点/跳线
]

COMPONENT_TO_IDX = {name: i for i, name in enumerate(COMPONENT_CLASSES)}
IDX_TO_COMPONENT = {i: name for i, name in enumerate(COMPONENT_CLASSES)}
NUM_COMPONENT_CLASSES = len(COMPONENT_CLASSES)

# 粗粒度映射：细类 → 原 4 类（向后兼容 checker.py 的 ic/cap/passive/other）
FINE_TO_COARSE = {
    "ic_mcu": "ic", "ic_power": "ic", "ic_analog": "ic", "ic_other": "ic",
    "cap_mlcc": "cap", "cap_elec": "cap",
    "resistor": "passive", "inductor": "passive",
    "diode_led": "passive", "transistor": "passive",
    "crystal": "other", "connector": "other",
}

# ── 模型超参数（比 IntentClassifier 高 ~2.5×）──
DEFAULT_COMPONENT_CONFIG = {
    "vocab_size": DEFAULT_VOCAB_SIZE,
    "embed_dim": 128,                   # ↑ 96 → 128
    "kernel_sizes": [2, 3, 4, 5, 6],    # ↑ 4 → 5 个尺度
    "num_filters": 128,                  # ↑ 64 → 128
    "dropout": 0.35,                     # ↑ 0.3 → 0.35（参数多需要更强正则化）
    "hidden_dim": 128,                   # ↑ 64 → 128
    "max_len": 128,
    "num_classes": NUM_COMPONENT_CLASSES,
}


class ComponentClassifier(nn.Module):
    """字符级 TextCNN 元件类型分类器

    使用方式:
        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))
        logits = model(input_ids)  # (batch, 12)
    """

    def __init__(self, vocab_size: int = DEFAULT_VOCAB_SIZE, **kwargs):
        super().__init__()

        cfg = {**DEFAULT_COMPONENT_CONFIG, "vocab_size": vocab_size, **kwargs}

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
            "ComponentClassifier: vocab=%d, embed=%d, kernels=%s, filters=%d/%d, params=%.1fK",
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
            logits: (batch, 12) float32 tensor
        """
        # Embedding → (batch, embed_dim, seq_len)
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
        """推理并返回元件类型和置信度（应用校准 temperature）

        Returns:
            types: 元件类型名列表
            confidences: softmax 置信度列表
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(input_ids) / self.temperature
            probs = F.softmax(logits, dim=1)
            best_idx = probs.argmax(dim=1)
            types = [IDX_TO_COMPONENT[i.item()] for i in best_idx]
            confidences = probs.max(dim=1).values.tolist()
        return types, confidences

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
        logger.info("Component model saved: %.1fK params → %s", self._count_params() / 1000, path)

    @classmethod
    def load(cls, path: str, device: str = "cpu") -> "ComponentClassifier":
        """加载模型权重（含校准 temperature）"""
        checkpoint = torch.load(path, map_location=device, weights_only=False)
        cfg = checkpoint.get("config", {})

        model = cls(**cfg)
        model.load_state_dict(checkpoint["state_dict"])
        model.temperature = checkpoint.get("temperature", 1.0)
        model.to(device)
        model.eval()

        logger.info(
            "Component model loaded: %.1fK params, T=%.3f ← %s",
            model._count_params() / 1000, model.temperature, path,
        )
        return model


class ComponentPredictor:
    """元件类型分类推理封装

    使用方式:
        vocab = PCBVocab.load("data/vocab.json")
        model = ComponentClassifier.load("data/component_model.pt")
        predictor = ComponentPredictor(model, vocab)

        comp_type, confidence, debug = predictor.classify(bom_item)
        # → ("ic_mcu", 0.93, {"scores": {...}, "coarse": "ic"})
    """

    def __init__(
        self,
        model: ComponentClassifier,
        vocab: PCBVocab,
        device: str = "cpu",
    ):
        self.model = model.to(device)
        self.vocab = vocab
        self.device = device
        self.max_len = model.max_len

        model.eval()
        logger.info("ComponentPredictor ready: device=%s, max_len=%d", device, self.max_len)

    def _build_input_text(self, item) -> str:
        """将 BOMItem 或 dict 拼接为分类输入文本

        格式: "ref:{prefix} pn:{part_number} pkg:{package} val:{value} desc:{description}"
        """
        if hasattr(item, "reference"):
            # BOMItem dataclass
            ref = item.reference
            ref_list = item.reference_list if hasattr(item, "reference_list") else [ref]
            prefix = "".join(ch for ch in (ref_list[0] if ref_list else ref) if ch.isalpha()).upper()
            pn = getattr(item, "part_number", "")
            pkg = getattr(item, "package", "")
            val = getattr(item, "value", "")
            desc = getattr(item, "description", "")
        elif isinstance(item, dict):
            ref = item.get("reference", "")
            prefix = "".join(ch for ch in ref.split(",")[0].strip() if ch.isalpha()).upper()
            pn = item.get("part_number", "")
            pkg = item.get("package", "")
            val = item.get("value", "")
            desc = item.get("description", "")
        else:
            return ""

        # 构建特征文本
        parts = []
        if prefix:
            parts.append(f"ref:{prefix}")
        if pn:
            parts.append(f"pn:{pn}")
        if pkg:
            parts.append(f"pkg:{pkg}")
        if val:
            parts.append(f"val:{val}")
        if desc:
            parts.append(f"desc:{desc}")
        return " ".join(parts)

    def classify(self, item) -> tuple[str, float, dict]:
        """分类 BOM 元件

        Args:
            item: BOMItem dataclass or dict with reference/part_number/package/value/description

        Returns:
            comp_type: str — 细粒度元件类型 (如 "ic_mcu", "cap_mlcc")
            confidence: float — 置信度 0.0-1.0
            debug: dict — {"scores": {type: prob, ...}, "coarse": "ic", "top_two": [...]}
        """
        text = self._build_input_text(item)

        if not text or not text.strip():
            return ("connector", 0.0, {
                "scores": {}, "top_two": [], "coarse": "other",
                "reason": "empty_input",
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
        for i, name in enumerate(COMPONENT_CLASSES):
            scores[name] = round(probs[i].item(), 4)

        # 排序
        sorted_items = sorted(scores.items(), key=lambda x: -x[1])
        best_name, confidence = sorted_items[0]
        top_two = sorted_items[:2]
        coarse = FINE_TO_COARSE.get(best_name, "other")

        debug = {
            "scores": scores,
            "top_two": [(name, score) for name, score in top_two],
            "coarse": coarse,
            "model": "local_component_textcnn",
        }

        return best_name, confidence, debug

    @staticmethod
    def from_path(
        model_path: str,
        vocab_path: str,
        device: str = "cpu",
    ) -> Optional["ComponentPredictor"]:
        """从文件路径加载预测器"""
        try:
            vocab = PCBVocab.load(vocab_path)
            model = ComponentClassifier.load(model_path, device=device)
            return ComponentPredictor(model, vocab, device=device)
        except FileNotFoundError as e:
            logger.warning("Component model file not found: %s", e)
            return None
        except Exception as e:
            logger.error("Failed to load ComponentPredictor: %s", e)
            return None
