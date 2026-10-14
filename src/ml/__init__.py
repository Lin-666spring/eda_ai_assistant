"""src/ml — 自研轻量 ML 模型模块

当前包含：
- BertIntentPredictor: rbt3 ONNX (fp16)，NLU 意图分类运行时 (10类, ~38M 底座)
  （训练/导出管线 train_intent_bert.py；运行时仅依赖 onnxruntime+tokenizers）
- IntentClassifier: 字符级 TextCNN，意图分类兜底 (10类, ~244K 参数)
- ComponentClassifier: 字符级 TextCNN，BOM 元件类型分类 (12类, ~600K 参数)
- ChangeRiskPredictor: 特征工程 + 逻辑回归，BOM 变更风险预测 (第三个模型)
- ViolationMining: FP-Growth + 关联规则，跨设计违规模式挖掘
- ConfidenceCalibration: Temperature Scaling，模型置信度校准
- PCBVocab: PCB 电子领域专用字符词表

设计原则：
- CPU 推理优先；意图模型 ONNX 随 exe 分发（2026-10-14 BERT 批）
- torch/transformers 仅训练侧（requirements-dev.txt），不进运行时
- 独立于云端 API，可离线运行
"""

from .intent_classifier import IntentClassifier, IntentPredictor
from .component_classifier import (
    ComponentClassifier,
    ComponentPredictor,
    COMPONENT_CLASSES,
    COMPONENT_TO_IDX,
    IDX_TO_COMPONENT,
    NUM_COMPONENT_CLASSES,
    FINE_TO_COARSE,
)
from .change_predictor import (
    ChangeRiskPredictor,
    ChangeFeatureExtractor,
    ChangeFeatures,
    train_change_predictor,
    prepare_training_data,
)
from .vocab import PCBVocab

__all__ = [
    "IntentClassifier", "IntentPredictor",
    "ComponentClassifier", "ComponentPredictor",
    "COMPONENT_CLASSES", "COMPONENT_TO_IDX", "IDX_TO_COMPONENT",
    "NUM_COMPONENT_CLASSES", "FINE_TO_COARSE",
    "ChangeRiskPredictor", "ChangeFeatureExtractor", "ChangeFeatures",
    "train_change_predictor", "prepare_training_data",
    "PCBVocab",
]
