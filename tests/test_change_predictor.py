"""BOM 变更风险预测器测试 — 第三个 ML 模型"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.change_predictor import (
    ChangeRiskPredictor,
    ChangeFeatureExtractor,
    ChangeFeatures,
    train_change_predictor,
    prepare_training_data,
    NUM_FEATURES,
)


class TestValueParsing:
    """参数值解析"""

    def test_parse_resistor(self):
        e = ChangeFeatureExtractor()
        assert e._parse_ratio("10k") == 10_000
        assert e._parse_ratio("4.7K") == 4_700
        assert e._parse_ratio("1M") == 1_000_000
        assert e._parse_ratio("10Ω") == 10.0
        assert e._parse_ratio("10R") == 10.0

    def test_parse_capacitor(self):
        e = ChangeFeatureExtractor()
        assert e._parse_ratio("100nF") == pytest.approx(100e-9)
        assert e._parse_ratio("1uF") == pytest.approx(1e-6)
        assert e._parse_ratio("0.1UF") == pytest.approx(0.1e-6)
        assert e._parse_ratio("10μF") == pytest.approx(10e-6)
        assert e._parse_ratio("22pF") == pytest.approx(22e-12)

    def test_parse_frequency(self):
        e = ChangeFeatureExtractor()
        assert e._parse_ratio("8MHz") == pytest.approx(8e6)
        assert e._parse_ratio("16MHz") == pytest.approx(16e6)
        assert e._parse_ratio("32.768kHz") == pytest.approx(32768.0)

    def test_parse_invalid(self):
        e = ChangeFeatureExtractor()
        assert e._parse_ratio("") is None
        assert e._parse_ratio(None) is None
        assert e._parse_ratio("abc") is None


class TestFeatureExtraction:
    """特征提取"""

    def test_feature_dimension(self):
        """特征维度 = 12 type + 9 others = 21"""
        assert NUM_FEATURES == 21

    def test_resistor_type(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "R1", "field": "value",
                       "old_value": "10k", "new_value": "11k"})
        # R → resistor 是第 6 类 (index 6)
        assert f.type_features[6] == 1.0
        assert f.type_base_risk == 0.2
        assert f.field_value == 1.0

    def test_capacitor_type(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "C1", "field": "value",
                       "old_value": "100nF", "new_value": "1uF"})
        # C → cap_mlcc 是第 4 类 (index 4)
        assert f.type_features[4] == 1.0
        assert f.type_base_risk == 0.45

    def test_value_large_change_detected(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "C1", "field": "value",
                       "old_value": "100nF", "new_value": "1uF"})
        assert f.value_large_change == 1.0
        assert f.value_log_ratio > 0.1

    def test_value_small_change(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "R1", "field": "value",
                       "old_value": "10k", "new_value": "10.5k"})
        assert f.value_large_change == 0.0
        assert abs(f.value_log_ratio) < 0.05

    def test_package_change(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "U2", "field": "package",
                       "old_value": "SOT-223", "new_value": "SOT-89"})
        assert f.field_package == 1.0

    def test_existing_violations(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "X1", "field": "value",
                       "old_value": "8MHz", "new_value": "16MHz"},
                      existing_violations=[{"rule": "a"}, {"rule": "b"}])
        assert f.has_existing_violation == 1.0
        assert f.existing_violation_count == 0.4  # 2/5

    def test_baseline_score_norm(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "R1", "field": "value",
                       "old_value": "10k", "new_value": "11k"},
                      baseline_score=80.0)
        assert f.baseline_score_norm == 0.8


class TestRiskPrediction:
    """风险预测排序"""

    def test_crystal_riskier_than_resistor(self):
        """晶振改频风险 > 电阻微调风险"""
        r_crystal, _ = ChangeRiskPredictor.heuristic_predict(
            {"reference": "X1", "field": "value",
             "old_value": "8MHz", "new_value": "16MHz"},
            existing_violations=[1],
        )
        r_resistor, _ = ChangeRiskPredictor.heuristic_predict(
            {"reference": "R1", "field": "value",
             "old_value": "10k", "new_value": "10.5k"},
        )
        assert r_crystal > r_resistor

    def test_large_change_riskier(self):
        """10 倍值变更风险 > 微调"""
        r_large, _ = ChangeRiskPredictor.heuristic_predict(
            {"reference": "C1", "field": "value",
             "old_value": "100nF", "new_value": "1uF"},
        )
        r_small, _ = ChangeRiskPredictor.heuristic_predict(
            {"reference": "C1", "field": "value",
             "old_value": "100nF", "new_value": "110nF"},
        )
        assert r_large > r_small

    def test_risk_range(self):
        """风险概率在 [0, 1]"""
        risk, _ = ChangeRiskPredictor.heuristic_predict(
            {"reference": "U1", "field": "package",
             "old_value": "LQFP-48", "new_value": "QFN-48"},
        )
        assert 0.0 <= risk <= 1.0

    def test_debug_structure(self):
        """debug 结构完整"""
        _, d = ChangeRiskPredictor.heuristic_predict(
            {"reference": "X1", "field": "value",
             "old_value": "8MHz", "new_value": "16MHz"},
            existing_violations=[1],
        )
        assert "probability" in d
        assert "top_risks" in d
        assert "factors" in d
        assert "type" in d
        assert d["model"] == "change_risk_logistic"

    def test_top_risk_attribution(self):
        """已有违规应出现在 top risk"""
        _, d = ChangeRiskPredictor.heuristic_predict(
            {"reference": "X1", "field": "value",
             "old_value": "8MHz", "new_value": "16MHz"},
            existing_violations=[1, 2],
        )
        factor_names = [f["factor"] for f in d["top_risks"]]
        assert any("违规" in name for name in factor_names)


class TestTraining:
    """训练流程"""

    def test_prepare_training_data(self):
        """从实验 JSON 提取训练数据"""
        if not os.path.exists("experiment_results/run_2026-08-03_235428/results.json"):
            pytest.skip("实验数据不存在")
        samples, labels = prepare_training_data()
        assert len(samples) > 0
        assert len(labels) == len(samples)
        assert all(l in (0.0, 1.0) for l in labels)

    def test_training_runs(self):
        """训练流程可运行"""
        if not os.path.exists("experiment_results/run_2026-08-03_235428/results.json"):
            pytest.skip("实验数据不存在")
        report = train_change_predictor(
            report_output="data/test_change_risk_report.json"
        )
        assert report["n_samples"] > 0
        assert report["n_features"] == NUM_FEATURES
        assert "accuracy" in report

    def test_model_saved(self):
        """模型文件已保存"""
        if not os.path.exists("data/change_risk_model.json"):
            pytest.skip("模型不存在")
        with open("data/change_risk_model.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "weights" in data
        assert data["num_features"] == NUM_FEATURES

    def test_load_saved_model(self):
        """加载已保存模型并预测"""
        if not os.path.exists("data/change_risk_model.json"):
            pytest.skip("模型不存在")
        predictor = ChangeRiskPredictor.from_file("data/change_risk_model.json")
        risk, _ = predictor.predict(
            {"reference": "C1", "field": "value",
             "old_value": "100nF", "new_value": "1uF"}
        )
        assert 0.0 <= risk <= 1.0


class TestVectorConsistency:
    """特征向量一致性"""

    def test_vector_length(self):
        e = ChangeFeatureExtractor()
        f = e.extract({"reference": "R1", "field": "value",
                       "old_value": "10k", "new_value": "11k"})
        assert len(f.to_vector()) == NUM_FEATURES

    def test_vector_deterministic(self):
        e = ChangeFeatureExtractor()
        change = {"reference": "C1", "field": "value",
                  "old_value": "100nF", "new_value": "1uF"}
        v1 = e.extract(change).to_vector()
        v2 = e.extract(change).to_vector()
        assert np.array_equal(v1, v2)
