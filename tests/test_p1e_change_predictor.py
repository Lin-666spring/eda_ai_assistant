"""P1-25 回归（2026-10-24）：变更风险预测器的诚实评估与训练/推理特征一致。

验收报告缺陷：
- 训练后 accuracy 在训练集上计算并汇报（73 条全部参与拟合，无 holdout），
  指标口径不可辨、必然虚高；
- 训练从不传 existing_violations，特征末两维（has_existing_violation /
  existing_violation_count）恒 0，学出权重 ≈0 —— 推理时传入的违规邻近度
  信号被静默丢弃（训练/推理特征不一致）。

修法：训练数据从实验 JSON 的 drc_results.violations_by_component 补出
每条变更目标位号的基线违规（变更前算得，无标签泄漏）；评估改固定确定性
leave-one-out CV 并与训练集拟合度分开汇报；模型用全量样本重训落盘。
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# src.ml 顶层 import torch：纯运行时依赖环境整文件收集即崩（同 test_change_predictor）。
pytest.importorskip("torch", reason="ML 测试需要 torch（pip install -r requirements-dev.txt）")

from src.ml.change_predictor import (
    NUM_FEATURES,
    ChangeFeatureExtractor,
    _feature_names,
    _loocv_accuracy,
    prepare_training_data,
    train_change_predictor,
)

RESULTS_JSON = "experiment_results/run_2026-08-03_235428/results.json"


def _real_data_available() -> bool:
    return Path(RESULTS_JSON).exists()


def _feature_matrix(samples: list[dict]) -> np.ndarray:
    extractor = ChangeFeatureExtractor()
    return np.array([
        extractor.extract(
            s["change"],
            baseline_score=s["baseline_score"],
            existing_violations=s.get("existing_violations"),
        ).to_vector()
        for s in samples
    ])


@pytest.mark.skipif(not _real_data_available(), reason="实验数据不存在")
class TestFeatureConstructionFix:
    """训练/推理特征一致性 —— 末两维不再恒 0"""

    def test_samples_carry_existing_violations(self):
        samples, _ = prepare_training_data(RESULTS_JSON)
        assert samples, "训练样本为空"
        # 26/73 条变更的目标位号在基线 DRC 中已有违规 —— 必须进入样本
        n_with = sum(1 for s in samples if s.get("existing_violations"))
        assert n_with > 0, "训练样本未携带基线违规（末两维将恒 0，特征 bug 回潮）"

    def test_last_two_dims_not_all_zero(self):
        samples, _ = prepare_training_data(RESULTS_JSON)
        X = _feature_matrix(samples)
        # 末两维 = has_existing_violation / existing_violation_count
        assert X[:, -2].std() > 0, "has_existing_violation 在训练集恒定（特征构造 bug）"
        assert X[:, -1].std() > 0, "existing_violation_count 在训练集恒定（特征构造 bug）"

    def test_existing_violations_derived_from_baseline_drc(self):
        # 基线违规必须真的来自变更前 DRC（violations_by_component），而不是
        # 标签导出（那会是标签泄漏）。prepare_training_data 与本处按同一顺序
        # 展平 verify_results，逐条全量核对（73/73）。
        with open(RESULTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        vbc = {
            d["design"]: d.get("violations_by_component") or {}
            for d in data["drc_results"] if d.get("design")
        }
        samples, _ = prepare_training_data(RESULTS_JSON)
        flat = [
            (v, c)
            for v in data["verify_results"]
            for c in (v.get("applied_changes") or [])
        ]
        assert len(flat) == len(samples), "样本与源数据展平顺序不一致"
        for (v, c), s in zip(flat, samples):
            assert s["change"] == c
            expect = list((vbc.get(v.get("design", ""), {}) or {}).get(c.get("reference", "")) or [])
            assert s["existing_violations"] == expect


@pytest.mark.skipif(not _real_data_available(), reason="实验数据不存在")
class TestHonestEvaluation:
    """评估口径：LOOCV 样本外指标与训练集拟合度分离汇报"""

    def test_report_protocol_and_fields(self, tmp_path):
        model_out = tmp_path / "model.json"
        report_out = tmp_path / "report.json"
        report = train_change_predictor(
            results_path=RESULTS_JSON,
            model_output=str(model_out),
            report_output=str(report_out),
        )
        assert report["eval_protocol"] == "leave_one_out_cv"
        # 对外 accuracy 必须是 LOOCV 样本外值，训练集拟合值另列
        assert report["accuracy"] == report["accuracy_loocv"]
        assert "accuracy_train_fit" in report
        assert report["n_features"] == NUM_FEATURES
        assert model_out.exists() and report_out.exists()

    def test_trained_weights_inform_violation_proximity_dims(self, tmp_path):
        """修过的特征必须有非零权重（此前恒 0 → 权重 ≈0，推理信号被丢弃）"""
        report = train_change_predictor(
            results_path=RESULTS_JSON,
            model_output=str(tmp_path / "model.json"),
            report_output=str(tmp_path / "report.json"),
        )
        names = report["feature_names"]
        w = report["weights"]
        assert len(w) == NUM_FEATURES
        i_flag = names.index("has_existing_violation")
        i_cnt = names.index("existing_violation_count")
        # 数据中 26/73 样本该维度非零且与标签正相关 → 学到的权重应为正
        assert w[i_flag] > 0, f"has_existing_violation 权重仍为 0: {w[i_flag]}"
        assert w[i_cnt] > 0, f"existing_violation_count 权重仍为 0: {w[i_cnt]}"

    def test_loocv_deterministic_and_in_range(self, tmp_path):
        """LOOCV 是固定确定性口径：同一数据重跑结果恒定，且在 [0,1]"""
        samples, labels = prepare_training_data(RESULTS_JSON)
        X = _feature_matrix(samples)
        y = np.array(labels)
        a1 = _loocv_accuracy(X, y)
        a2 = _loocv_accuracy(X, y)
        assert 0.0 <= a1 <= 1.0
        assert a1 == a2, "LOOCV 结果不可复现（评估口径引入了随机性）"
