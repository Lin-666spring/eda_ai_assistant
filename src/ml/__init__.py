"""src/ml — 自研轻量 ML 模型模块

当前包含：
- IntentClassifier: 字符级 TextCNN，NLU 意图分类 (10类, ~244K 参数)
- ComponentClassifier: 字符级 TextCNN，BOM 元件类型分类 (12类, ~600K 参数)
- ChangeRiskPredictor: 特征工程 + 逻辑回归，BOM 变更风险预测 (第三个模型)
- ViolationMining: FP-Growth + 关联规则，跨设计违规模式挖掘
- ConfidenceCalibration: Temperature Scaling，模型置信度校准
- PCBVocab: PCB 电子领域专用字符词表

设计原则：
- 纯 PyTorch + numpy，无额外重依赖
- CPU 推理优先，模型文件 < 3MB
- 独立于云端 API，可离线运行
- 三模型协同：意图理解 + 元件识别 + 变更风险预测
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
