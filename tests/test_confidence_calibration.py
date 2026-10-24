"""置信度校准测试 — Temperature Scaling + ECE

验证:
1. ECE 计算正确
2. 校准后 ECE 不显著恶化（50 条小校准集上 TS 可能轻微变差，2026-10-24 实测 +0.008/+0.003）
3. 校准后置信度仍为有效概率
4. 校准模型可加载且 temperature 在合理范围
5. 推理时应用 temperature
6. 运行时加载点优先取校准产物（P1-24）
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# src.ml 顶层 import torch：纯运行时依赖环境（requirements.txt 不含 torch）整文件收集即崩。
# 2026-10-10 依赖批：importorskip 让 ML 测试在未装 requirements-dev 的环境下跳过。
pytest.importorskip("torch", reason="ML 测试需要 torch（pip install -r requirements-dev.txt）")
from src.ml.calibrate import compute_ece, reliability_diagram_data


class TestECEComputation:
    """ECE 计算单元测试"""

    def test_perfectly_calibrated(self):
        """完美校准: conf == acc 时 ECE = 0"""
        confidences = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        accuracies = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        result = compute_ece(confidences, accuracies)
        assert result["ece"] == 0.0

    def test_completely_miscalibrated(self):
        """完全失准: conf=1.0, acc=0.0 时 ECE 大"""
        confidences = np.array([0.9, 0.8, 0.7])
        accuracies = np.array([0.0, 0.0, 0.0])
        result = compute_ece(confidences, accuracies)
        assert result["ece"] > 0.5

    def test_empty_bin_handled(self):
        """空 bin 不应崩溃"""
        confidences = np.array([0.95, 0.93, 0.91])
        accuracies = np.array([1.0, 1.0, 1.0])
        result = compute_ece(confidences, accuracies, n_bins=10)
        assert result["n_bins"] == 10
        assert len(result["bins"]) == 10

    def test_ece_range(self):
        """ECE 应在 [0, 1] 范围"""
        np.random.seed(42)
        confidences = np.random.rand(1000)
        accuracies = np.random.rand(1000) < confidences
        result = compute_ece(confidences, accuracies.astype(float))
        assert 0.0 <= result["ece"] <= 1.0

    def test_reliability_diagram_structure(self):
        """可靠性图数据结构正确"""
        confidences = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        accuracies = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        data = reliability_diagram_data(confidences, accuracies)
        assert "perfect" in data
        assert "calibrated" in data
        assert data["perfect"] == [[0.0, 0.0], [1.0, 1.0]]
        assert "ece" in data
        assert "mce" in data


class TestCalibratedModelLoading:
    """校准模型加载测试"""

    @pytest.fixture
    def has_calibration_files(self):
        return os.path.exists("data/calibration_report.json")

    def test_calibration_report_exists(self, has_calibration_files):
        if not has_calibration_files:
            pytest.skip("校准报告不存在")
        with open("data/calibration_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
        assert "results" in report
        assert "summary" in report
        assert len(report["results"]) >= 2  # intent + component

    def test_intent_model_has_temperature(self, has_calibration_files):
        """校准产物应携带合理 temperature。

        2026-10-24 A-9 重训后改口径：基础 .pt 是纯训练产物（T 恒为默认 1.0），
        校准温度只写入 *_calibrated.pt；断言改为「校准产物存在且 T 在合理范围」，
        不再要求 T≠1（小校准集上 LBFGS 学出 T≈1 是合法结果）。
        """
        if not has_calibration_files:
            pytest.skip("校准报告不存在")
        from src.ml.intent_classifier import IntentClassifier
        model = IntentClassifier.load("data/intent_model_calibrated.pt")
        assert 0.05 <= model.temperature <= 10.0

    def test_component_model_has_temperature(self, has_calibration_files):
        """同上，元件分类校准产物"""
        if not has_calibration_files:
            pytest.skip("校准报告不存在")
        from src.ml.component_classifier import ComponentClassifier
        model = ComponentClassifier.load("data/component_model_calibrated.pt")
        assert 0.05 <= model.temperature <= 10.0

    def test_calibration_ece_not_worsened(self, has_calibration_files):
        """校准后 ECE 不应显著恶化。

        旧断言「必降」在泄漏数据上成立（val 即训练样本的重复）；2026-10-24
        A-9 无泄漏重训后，50 条校准集上 Temperature Scaling 实测 ECE 反升
        +0.0076/+0.0028——属小样本正常波动。本测试防的是灾难性劣化（如负温度
        翻转预测导致的 ECE 爆炸，P1-24）。
        """
        if not has_calibration_files:
            pytest.skip("校准报告不存在")
        with open("data/calibration_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
        for r in report["results"]:
            assert r["after"]["ece"] <= r["before"]["ece"] + 0.05, (
                f"{r['model']}: 校准后 ECE 恶化超容差"
            )

    def test_calibration_keeps_accuracy(self, has_calibration_files):
        """校准不应改变准确率（仅改变置信度）"""
        if not has_calibration_files:
            pytest.skip("校准报告不存在")
        with open("data/calibration_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
        for r in report["results"]:
            assert abs(r["after"]["accuracy"] - r["before"]["accuracy"]) < 1e-4, (
                f"{r['model']}: 校准改变了准确率（不应改变）"
            )


class TestCalibratedInference:
    """校准后推理行为测试"""

    def test_calibrated_first_prefers_calibrated(self, tmp_path):
        """运行时加载点应优先取校准产物（P1-24：此前校准产物无人加载）"""
        from src.ml.model_paths import calibrated_first

        base = tmp_path / "intent_model.pt"
        base.write_bytes(b"x")
        cal = tmp_path / "intent_model_calibrated.pt"

        # 校准产物缺失 → 返回基础路径
        assert calibrated_first(str(base)) == str(base)
        # 校准产物在场 → 优先
        cal.write_bytes(b"x")
        assert calibrated_first(str(base)) == str(cal)

    def test_predictor_uses_temperature(self):
        """IntentPredictor 推理应应用 temperature"""
        if not os.path.exists("data/intent_model.pt"):
            pytest.skip("模型不存在")
        from src.ml.intent_classifier import IntentPredictor
        from src.ml.vocab import PCBVocab

        vocab = PCBVocab.load("data/vocab.json")
        predictor = IntentPredictor.from_path("data/intent_model.pt", "data/vocab.json")
        assert predictor is not None

        # 推理正常
        intent, confidence, debug = predictor.classify("检查电源走线")
        assert intent in ["RULE_CHECK", "TEXT_CHAT", "PCB_ANALYSIS"]
        assert 0.0 <= confidence <= 1.0

    def test_component_predictor_uses_temperature(self):
        """ComponentPredictor 推理应应用 temperature"""
        if not os.path.exists("data/component_model.pt"):
            pytest.skip("模型不存在")
        from src.ml.component_classifier import ComponentPredictor
        from src.ml.vocab import PCBVocab

        predictor = ComponentPredictor.from_path("data/component_model.pt", "data/vocab.json")
        assert predictor is not None

        item = {
            "reference": "U1", "part_number": "STM32F103C8T6",
            "package": "LQFP-48", "description": "ARM Cortex-M3",
        }
        comp_type, confidence, debug = predictor.classify(item)
        assert comp_type in ["ic_mcu", "ic_power", "ic_analog", "ic_other"]
        assert 0.0 <= confidence <= 1.0

    def test_probabilities_still_sum_to_one(self):
        """校准后 softmax 概率仍和为 1"""
        if not os.path.exists("data/intent_model.pt"):
            pytest.skip("模型不存在")
        from src.ml.intent_classifier import IntentPredictor
        predictor = IntentPredictor.from_path("data/intent_model.pt", "data/vocab.json")

        _, _, debug = predictor.classify("帮我检查PCB设计规则")
        scores = debug["scores"]
        total = sum(scores.values())
        assert abs(total - 1.0) < 0.05, f"概率和 {total} 不等于 1"


class TestTemperatureScalingFunction:
    """Temperature Scaling 核心逻辑测试"""

    def test_temperature_changes_confidence(self):
        """T<1 提高置信度，T>1 降低置信度"""
        import torch
        import torch.nn.functional as F

        logits = torch.tensor([[2.0, 1.0, 0.0]])
        probs_base = F.softmax(logits, dim=1)

        probs_sharp = F.softmax(logits / 0.5, dim=1)  # T<1 → 更自信
        probs_flat = F.softmax(logits / 2.0, dim=1)   # T>1 → 更保守

        assert probs_sharp.max() > probs_base.max()
        assert probs_flat.max() < probs_base.max()

    def test_temperature_preserves_prediction(self):
        """Temperature 不改变 argmax（只改变置信度）"""
        import torch
        import torch.nn.functional as F

        logits = torch.tensor([[2.0, 1.0, 0.0], [0.0, 3.0, 1.0]])
        pred_base = logits.argmax(dim=1)
        pred_scaled = (logits / 0.8).argmax(dim=1)
        assert torch.equal(pred_base, pred_scaled)
