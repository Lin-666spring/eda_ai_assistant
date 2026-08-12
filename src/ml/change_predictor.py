"""BOM 变更风险预测器 — 第三个自研模型

预测"拟议 BOM 变更是否可能引入新 DRC 违规"，在闭环验证中做预检。

架构：特征工程 + 逻辑回归（可解释，适合小样本）
  - 不从零学习表示，而是用领域知识提取特征
  - 特征 = 元件类型 + 变更类型 + 参数幅度 + 设计健康度 + 违规邻近度

数据来源：闭环验证历史（run_2026-08-03_235428，73 条变更记录）

输出：P(introduce_violation) ∈ [0, 1] + 风险因子归因

论文定位："Predictive Guard: ML-Based Pre-Flight Risk Assessment"
"""

import json
import logging
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ml.component_classifier import (
    ComponentClassifier, ComponentPredictor,
    COMPONENT_CLASSES, NUM_COMPONENT_CLASSES,
)
from src.ml.vocab import PCBVocab

logger = logging.getLogger(__name__)

# ═══ 风险权重（领域知识） ═══

# 各元件类型的变更风险基础权重（晶体/IC 改动风险高，电阻改动风险低）
_TYPE_BASE_RISK = {
    "ic_mcu": 0.55, "ic_power": 0.65, "ic_analog": 0.50, "ic_other": 0.45,
    "cap_mlcc": 0.45, "cap_elec": 0.50,
    "resistor": 0.20, "inductor": 0.55, "diode_led": 0.35,
    "transistor": 0.45, "crystal": 0.75, "connector": 0.30,
}

# 变更字段风险权重（改参数值最常引发降额违规）
_FIELD_RISK = {"value": 0.50, "package": 0.60, "reference": 0.30}

# 参数幅度变化阈值：超过此倍数认为高险
VALUE_CHANGE_RISK_FACTOR = 5.0

# 特征向量维度 = 12 (type one-hot) + 9 (field×3 + value×2 + type_risk + score + violations×2)
NUM_FEATURES = NUM_COMPONENT_CLASSES + 9


# ═══ 特征提取 ═══

@dataclass
class ChangeFeatures:
    """一条 BOM 变更的数值特征向量（用于风险预测）"""

    # 元件类型 one-hot (12 维)
    type_features: list[float] = field(default_factory=list)
    # 变更字段 (value/package/reference)
    field_value: float = 0.0
    field_package: float = 0.0
    field_reference: float = 0.0
    # 参数幅度变化风险
    value_log_ratio: float = 0.0
    value_large_change: float = 0.0
    # 元件基础风险
    type_base_risk: float = 0.3
    # 设计健康度
    baseline_score_norm: float = 0.0
    # 违规邻近度（该元件是否已有违规）
    has_existing_violation: float = 0.0
    existing_violation_count: float = 0.0

    def to_vector(self) -> np.ndarray:
        """拼接为特征向量"""
        vec = np.array(
            self.type_features
            + [
                self.field_value, self.field_package, self.field_reference,
                self.value_log_ratio, self.value_large_change,
                self.type_base_risk, self.baseline_score_norm,
                self.has_existing_violation, self.existing_violation_count,
            ],
            dtype=float,
        )
        return vec

    @property
    def num_features(self) -> int:
        return len(self.to_vector())


class ChangeFeatureExtractor:
    """从 BOM 变更提取可解释风险特征"""

    def __init__(
        self,
        component_predictor: Optional[ComponentPredictor] = None,
        vocab: Optional[PCBVocab] = None,
    ):
        self.component_predictor = component_predictor

    @classmethod
    def from_models(
        cls,
        model_path: str = "data/component_model.pt",
        vocab_path: str = "data/vocab.json",
    ) -> "ChangeFeatureExtractor":
        """从模型文件加载"""
        try:
            vocab = PCBVocab.load(vocab_path)
            model = ComponentClassifier.load(model_path)
            predictor = ComponentPredictor(model, vocab)
            return cls(component_predictor=predictor)
        except Exception as e:
            logger.warning("元件分类器加载失败，风险特征降级: %s", e)
            return cls(component_predictor=None)

    # 电阻/电容单位映射（长单位优先匹配）
    _VALUE_UNITS = [
        ("MΩ", 1e6), ("KΩ", 1e3), ("UF", 1e-6), ("μF", 1e-6), ("µF", 1e-6),
        ("NF", 1e-9), ("PF", 1e-12), ("MF", 1e-6),
        ("GHZ", 1e9), ("MHZ", 1e6), ("KHZ", 1e3), ("HZ", 1.0),
        ("K", 1e3), ("M", 1e6), ("R", 1.0), ("Ω", 1.0), ("欧", 1.0),
        ("欧姆", 1.0), ("OHM", 1.0), ("F", 1.0), ("U", 1e-6), ("µ", 1e-6),
        ("N", 1e-9), ("P", 1e-12), ("G", 1e9),
    ]

    @classmethod
    def _parse_ratio(cls, text: str) -> Optional[float]:
        """解析电阻/电容值字符串为浮点数（基本单位）

        支持: 10K, 4.7K, 100NF, 0.1UF, 1M, 10Ω, 10R, 100U, 8MHZ 等
        """
        if not text:
            return None
        text = text.strip().upper().replace(" ", "").replace("µ", "μ")
        # 匹配数字前缀（可能带小数点/负号）
        m = re.match(r"^([0-9.]+)\s*(.*)$", text)
        if not m:
            return None
        try:
            value = float(m.group(1))
        except ValueError:
            return None
        unit = m.group(2).strip()
        if not unit:
            return value
        # 长单位优先匹配
        for u, mult in cls._VALUE_UNITS:
            if unit.upper() == u.upper():
                return value * mult
        return value  # 未知单位：按原始数字

    def extract(
        self,
        change: dict,
        baseline_score: float = 0.0,
        existing_violations: Optional[list] = None,
        bom_items: Optional[list] = None,
    ) -> ChangeFeatures:
        """提取特征

        Args:
            change: {"reference": str, "field": str, "old_value": str,
                     "new_value": str, "action": str}
            baseline_score: 当前设计评分 0-100
            existing_violations: 当前涉及该元件的违规列表
            bom_items: 当前 BOM（用于元件类型识别）
        """
        feats = ChangeFeatures()

        ref = change.get("reference", "")
        field = change.get("field", "value")
        old_val = change.get("old_value", "")
        new_val = change.get("new_value", "")

        # ── 元件类型 one-hot + 基础风险 ──
        comp_type = self._classify_component(ref, bom_items)
        feats.type_features = [
            1.0 if ct == comp_type else 0.0 for ct in COMPONENT_CLASSES
        ]
        feats.type_base_risk = _TYPE_BASE_RISK.get(comp_type, 0.3)

        # ── 变更字段 ──
        feats.field_value = 1.0 if field == "value" else 0.0
        feats.field_package = 1.0 if field == "package" else 0.0
        feats.field_reference = 1.0 if field == "reference" else 0.0

        # ── 参数幅度变化 ──
        old_ratio = self._parse_ratio(old_val)
        new_ratio = self._parse_ratio(new_val)

        if old_ratio and new_ratio and old_ratio > 0:
            ratio = new_ratio / old_ratio
            feats.value_log_ratio = math.log(ratio) / 10.0  # 归一化到 [-1, 1] 附近
            feats.value_large_change = 1.0 if ratio >= VALUE_CHANGE_RISK_FACTOR else 0.0
        elif (old_val and not new_val) or (not old_val and new_val):
            # 新增/移除参数 → 中等风险
            feats.value_log_ratio = 0.5
            feats.value_large_change = 0.0
        else:
            feats.value_log_ratio = 0.0

        # ── 设计健康度 ──
        feats.baseline_score_norm = baseline_score / 100.0 if baseline_score else 0.0

        # ── 违规邻近度 ──
        if existing_violations:
            feats.has_existing_violation = 1.0
            feats.existing_violation_count = min(len(existing_violations), 5) / 5.0

        return feats

    def _classify_component(self, ref: str, bom_items: Optional[list]) -> str:
        """识别元件类型（优先 ML，降级规则）"""
        if self.component_predictor and bom_items:
            # 在 BOM 中找到对应元件
            for item in bom_items:
                ref_list = getattr(item, "reference_list", None) or []
                if ref in ref_list:
                    comp_type, _conf, _dbg = self.component_predictor.classify(item)
                    return comp_type
            # 找不到，用 reference 构造虚拟项
            item = {
                "reference": ref, "part_number": "",
                "package": "", "value": "", "description": "",
            }
            comp_type, _conf, _dbg = self.component_predictor.classify(item)
            return comp_type

        # 规则降级：按位号前缀
        prefix = "".join(ch for ch in ref if ch.isalpha()).upper()
        mapping = {
            "U": "ic_mcu", "IC": "ic_mcu", "LDO": "ic_power",
            "C": "cap_mlcc", "R": "resistor", "L": "inductor",
            "FB": "inductor", "D": "diode_led", "LED": "diode_led",
            "Q": "transistor", "X": "crystal", "Y": "crystal",
            "J": "connector", "CN": "connector", "SW": "connector",
        }
        return mapping.get(prefix, "connector")


# ═══ 风险预测模型 ═══

class ChangeRiskPredictor:
    """变更风险预测器

    使用方式:
        predictor = ChangeRiskPredictor.from_file("data/change_risk_model.json")
        risk, debug = predictor.predict(change, baseline_score, existing_violations)
        # → (0.72, {"factors": [...], "top_risks": [...]})
    """

    # 逻辑回归系数（可解释，从小样本学得）
    def __init__(self, weights: Optional[np.ndarray] = None, bias: float = 0.0):
        self.weights = weights
        self.bias = bias
        self.extractor = ChangeFeatureExtractor.from_models()

    def predict(
        self,
        change: dict,
        baseline_score: float = 0.0,
        existing_violations: Optional[list] = None,
        bom_items: Optional[list] = None,
    ) -> tuple[float, dict]:
        """预测风险概率

        Returns:
            (risk_score, debug)
        """
        feats = self.extractor.extract(
            change, baseline_score, existing_violations, bom_items
        )
        vec = feats.to_vector()

        if self.weights is None:
            # 未训练：使用特征加权启发式（可解释基线）
            raw = float(np.dot(vec, self._heuristic_weights()))
        else:
            raw = float(np.dot(vec, self.weights)) + self.bias

        prob = 1.0 / (1.0 + math.exp(-raw))

        # 风险因子归因
        factors = self._attribute_risk(feats)
        top_risks = sorted(factors.items(), key=lambda x: -x[1])[:3]

        debug = {
            "probability": round(prob, 4),
            "raw_score": round(raw, 4),
            "type": self._dominant_type(feats),
            "factors": factors,
            "top_risks": [{"factor": k, "score": round(v, 3)} for k, v in top_risks],
            "model": "change_risk_logistic",
        }

        return prob, debug

    def _heuristic_weights(self) -> np.ndarray:
        """启发式权重（无训练时的可解释基线）"""
        # 权重与特征顺序对齐: 12 type + 9 others
        w = np.zeros(NUM_FEATURES)
        # type one-hot (0-11) → 按类型风险
        for i, ct in enumerate(COMPONENT_CLASSES):
            w[i] = _TYPE_BASE_RISK.get(ct, 0.3) * 2.0
        # field
        w[12] = _FIELD_RISK["value"] * 2.0   # field_value
        w[13] = _FIELD_RISK["package"] * 2.0  # field_package
        w[14] = _FIELD_RISK["reference"] * 2.0  # field_reference
        # value_log_ratio
        w[15] = 1.0
        # value_large_change
        w[16] = 2.0
        # baseline_score_norm (低分高风险)
        w[17] = -2.0
        # has_existing_violation
        w[18] = 1.5
        # existing_violation_count
        w[19] = 1.5
        return w

    def _attribute_risk(self, feats: ChangeFeatures) -> dict:
        """归因各风险因子贡献"""
        contrib = {}
        if feats.type_base_risk > 0.5:
            contrib["元件类型高风险"] = feats.type_base_risk
        if feats.field_package:
            contrib["封装变更"] = _FIELD_RISK["package"]
        if feats.field_reference:
            contrib["位号变更"] = _FIELD_RISK["reference"]
        if feats.value_large_change:
            contrib["参数大幅变化"] = 2.0
        if feats.has_existing_violation:
            contrib["元件已有违规"] = 1.5
        return contrib

    def _dominant_type(self, feats: ChangeFeatures) -> str:
        for i, ct in enumerate(COMPONENT_CLASSES):
            if feats.type_features and feats.type_features[i] == 1.0:
                return ct
        return "unknown"

    # ── 兼容接口：直接预测函数 ──

    @staticmethod
    def heuristic_predict(
        change: dict,
        baseline_score: float = 0.0,
        existing_violations: Optional[list] = None,
    ) -> tuple[float, dict]:
        """静态启发式预测（无需加载模型文件）"""
        predictor = ChangeRiskPredictor()  # 未训练时自动用启发式权重
        return predictor.predict(
            change, baseline_score, existing_violations
        )

    # ── 持久化 ──

    def save(self, path: str) -> None:
        data = {
            "weights": self.weights.tolist() if self.weights is not None else None,
            "bias": self.bias,
            "num_features": NUM_FEATURES,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def from_file(cls, path: str) -> "ChangeRiskPredictor":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        weights = np.array(data["weights"]) if data.get("weights") else None
        return cls(weights=weights, bias=data.get("bias", 0.0))


# ═══ 训练 ═══

def prepare_training_data(
    results_path: str = "experiment_results/run_2026-08-03_235428/results.json",
) -> tuple[list[dict], list[float]]:
    """从实验 JSON 提取训练数据

    Returns:
        (samples, labels) — 每条样本对应一个变更，label=该建议是否引入新违规
    """
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    labels = []

    for v in data.get("verify_results", []):
        changes = v.get("applied_changes", [])
        if not changes:
            continue
        # 标签：该建议是否引入新违规
        label = 1.0 if v.get("new_violations_introduced", 0) > 0 else 0.0
        baseline_score = v.get("baseline_score", 0.0)

        for c in changes:
            samples.append({
                "change": c,
                "baseline_score": baseline_score,
                "label": label,
            })
            labels.append(label)

    logger.info("提取训练样本: %d 条变更, 危险比例: %.1f%%",
                len(samples), sum(labels) / len(labels) * 100 if labels else 0)
    return samples, labels


def train_change_predictor(
    results_path: str = "experiment_results/run_2026-08-03_235428/results.json",
    model_output: str = "data/change_risk_model.json",
    report_output: str = "data/change_risk_report.json",
) -> dict:
    """训练变更风险预测器（小样本逻辑回归）"""
    samples, labels = prepare_training_data(results_path)
    if len(samples) < 10:
        logger.warning("训练样本过少 (%d)，使用启发式基线", len(samples))

    extractor = ChangeFeatureExtractor.from_models()

    # 提取特征矩阵
    X = []
    y = np.array(labels)
    for s in samples:
        feats = extractor.extract(
            s["change"], baseline_score=s["baseline_score"]
        )
        X.append(feats.to_vector())
    X = np.array(X)

    n_features = X.shape[1]
    logger.info("特征维度: %d, 样本数: %d", n_features, len(X))

    # ── 训练逻辑回归（L2 正则，小样本防过拟合）──
    weights = np.zeros(n_features)
    bias = 0.0
    lr = 0.5
    l2_lambda = 1.0  # 强正则
    epochs = 200

    for _ in range(epochs):
        z = X @ weights + bias
        prob = 1.0 / (1.0 + np.exp(-z))
        # 梯度
        grad_w = X.T @ (prob - y) / len(X) + l2_lambda * weights
        grad_b = np.mean(prob - y)
        weights -= lr * grad_w
        bias -= lr * grad_b

    # ── 评估 ──
    pred = 1.0 / (1.0 + np.exp(-(X @ weights + bias)))
    pred_binary = (pred >= 0.5).astype(float)
    accuracy = np.mean(pred_binary == y)
    # 简单阈值评估
    positive = y.sum()
    negative = len(y) - positive
    logger.info("训练完成: acc=%.3f, 正样本=%d, 负样本=%d",
                accuracy, int(positive), int(negative))

    # ── 保存 ──
    predictor = ChangeRiskPredictor(weights=weights, bias=float(bias))
    predictor.save(model_output)

    report = {
        "model": "ChangeRiskPredictor (Logistic Regression)",
        "n_samples": len(samples),
        "n_features": n_features,
        "n_positive": int(positive),
        "n_negative": int(negative),
        "accuracy": round(float(accuracy), 4),
        "bias": float(bias),
        "weights": weights.tolist(),
        "feature_names": _feature_names(n_features),
    }
    with open(report_output, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("报告已保存: %s", report_output)

    return report


def _feature_names(n: int) -> list[str]:
    """特征名（调试用）"""
    names = list(COMPONENT_CLASSES) + [
        "field_value", "field_package", "field_reference",
        "value_log_ratio", "value_large_change",
        "type_base_risk", "baseline_score_norm",
        "has_existing_violation", "existing_violation_count",
    ]
    return names[:n]


# ═══ CLI ═══

def main():
    import argparse
    parser = argparse.ArgumentParser(description="训练 BOM 变更风险预测器")
    parser.add_argument("--results", type=str,
                        default="experiment_results/run_2026-08-03_235428/results.json",
                        help="实验 JSON 路径")
    parser.add_argument("--model-output", type=str,
                        default="data/change_risk_model.json")
    parser.add_argument("--report-output", type=str,
                        default="data/change_risk_report.json")
    parser.add_argument("--predict", type=str, default=None,
                        help="测试单条变更 JSON: '{\"reference\":\"C1\",\"field\":\"value\",...}'")
    args = parser.parse_args()

    if args.predict:
        change = json.loads(args.predict)
        predictor = ChangeRiskPredictor.from_file(args.model_output)
        risk, debug = predictor.predict(change, baseline_score=90.0)
        print(json.dumps({"risk": risk, **debug}, ensure_ascii=False, indent=2))
        return

    train_change_predictor(
        results_path=args.results,
        model_output=args.model_output,
        report_output=args.report_output,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    main()
