"""自研 BOM 元件类型分类器 — 测试套件"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 确保项目根在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.vocab import PCBVocab
from src.ml.component_classifier import (
    ComponentClassifier,
    ComponentPredictor,
    COMPONENT_CLASSES,
    COMPONENT_TO_IDX,
    IDX_TO_COMPONENT,
    NUM_COMPONENT_CLASSES,
    FINE_TO_COARSE,
    DEFAULT_COMPONENT_CONFIG,
)


class TestComponentClasses:
    """类别定义测试"""

    def test_num_classes(self):
        assert NUM_COMPONENT_CLASSES == 12

    def test_all_have_coarse_mapping(self):
        for cls in COMPONENT_CLASSES:
            assert cls in FINE_TO_COARSE, f"{cls} 缺少粗类映射"
            assert FINE_TO_COARSE[cls] in ("ic", "cap", "passive", "other")

    def test_ic_types_map_to_ic(self):
        for ic_type in ("ic_mcu", "ic_power", "ic_analog", "ic_other"):
            assert FINE_TO_COARSE[ic_type] == "ic"

    def test_cap_types_map_to_cap(self):
        for cap_type in ("cap_mlcc", "cap_elec"):
            assert FINE_TO_COARSE[cap_type] == "cap"

    def test_passive_types_map_to_passive(self):
        for passive_type in ("resistor", "inductor", "diode_led", "transistor"):
            assert FINE_TO_COARSE[passive_type] == "passive"

    def test_other_types_map_to_other(self):
        for other_type in ("crystal", "connector"):
            assert FINE_TO_COARSE[other_type] == "other"

    def test_bidirectional_mapping(self):
        """COMPONENT_TO_IDX ↔ IDX_TO_COMPONENT 一致"""
        for name in COMPONENT_CLASSES:
            assert IDX_TO_COMPONENT[COMPONENT_TO_IDX[name]] == name


class TestComponentClassifier:
    """模型单元测试"""

    def test_model_creation(self):
        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))
        assert isinstance(model, ComponentClassifier)

        # 检查参数数量合理
        params = model._count_params()
        assert 400_000 < params < 800_000, (
            f"期望参数量在 400K-800K 之间，实际 {params}"
        )

    def test_forward_shape(self):
        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))

        import torch
        batch_size = 8
        seq_len = 64
        input_ids = torch.randint(0, len(vocab), (batch_size, seq_len))

        logits = model(input_ids)
        assert logits.shape == (batch_size, NUM_COMPONENT_CLASSES)

    def test_predict(self):
        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))

        import torch
        input_ids = torch.randint(0, len(vocab), (3, DEFAULT_COMPONENT_CONFIG["max_len"]))

        types, confidences = model.predict(input_ids)
        assert len(types) == 3
        assert len(confidences) == 3
        assert all(t in COMPONENT_CLASSES for t in types)
        assert all(0.0 <= c <= 1.0 for c in confidences)

    def test_save_load(self):
        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))

        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            model.save(f.name)
            path = f.name

        try:
            loaded = ComponentClassifier.load(path)
            assert loaded.vocab_size == model.vocab_size
            assert loaded.embed_dim == model.embed_dim
            assert loaded.num_classes == model.num_classes
            assert loaded.num_filters == model.num_filters
            assert loaded.kernel_sizes == model.kernel_sizes

            # 验证权重一致
            import torch
            for p1, p2 in zip(model.parameters(), loaded.parameters()):
                assert torch.equal(p1, p2)
        finally:
            os.unlink(path)

    def test_deterministic_inference(self):
        """相同输入应产生相同输出"""
        import torch
        torch.manual_seed(42)

        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))
        model.eval()

        text = "ref:U pn:STM32F103C8T6 pkg:LQFP-48 desc:ARM Cortex-M3 微控制器"
        ids = vocab.encode(text)
        ids = ids + [vocab.pad_id] * (DEFAULT_COMPONENT_CONFIG["max_len"] - len(ids))
        input_ids = torch.tensor([ids])

        with torch.no_grad():
            logits1 = model(input_ids)
            logits2 = model(input_ids)

        assert torch.equal(logits1, logits2)

    def test_config_override(self):
        """自定义配置应生效"""
        model = ComponentClassifier(
            vocab_size=2000, embed_dim=64, kernel_sizes=[2, 3, 4],
            num_filters=32, hidden_dim=32,
        )
        assert model.embed_dim == 64
        assert model.kernel_sizes == [2, 3, 4]
        assert model.num_filters == 32
        assert model.hidden_dim == 32


class TestComponentPredictor:
    """推理封装测试"""

    @pytest.fixture
    def predictor(self):
        import torch
        torch.manual_seed(42)

        vocab = PCBVocab()
        model = ComponentClassifier(vocab_size=len(vocab))
        return ComponentPredictor(model, vocab)

    def test_classify_bom_item(self, predictor):
        """分类 BOMItem 对象"""
        from src.bom.parser import BOMItem

        item = BOMItem(
            reference="U1",
            value="",
            package="LQFP-48",
            part_number="STM32F103C8T6",
            description="ARM Cortex-M3 MCU",
        )

        comp_type, confidence, debug = predictor.classify(item)
        assert comp_type in COMPONENT_CLASSES
        assert 0.0 <= confidence <= 1.0
        assert "scores" in debug
        assert "coarse" in debug
        assert "top_two" in debug
        assert len(debug["top_two"]) == 2
        assert debug.get("model") == "local_component_textcnn"

    def test_classify_dict(self, predictor):
        """分类字典（无 BOMItem）"""
        item = {
            "reference": "C1",
            "part_number": "CL10B104KB8NNNC",
            "package": "0603",
            "value": "100nF",
            "description": "贴片电容 100nF 50V X7R",
        }

        comp_type, confidence, debug = predictor.classify(item)
        assert comp_type in COMPONENT_CLASSES
        assert confidence > 0.0

    def test_classify_empty_input(self, predictor):
        comp_type, confidence, debug = predictor.classify({})
        assert comp_type == "connector"  # 默认兜底
        assert confidence == 0.0
        assert "reason" in debug

    def test_coarse_mapping_in_debug(self, predictor):
        """debug 中的 coarse 字段正确"""
        item = {
            "reference": "C5",
            "part_number": "",
            "package": "0805",
            "value": "10μF",
            "description": "贴片电容",
        }
        _, _, debug = predictor.classify(item)
        assert "coarse" in debug
        assert debug["coarse"] in ("ic", "cap", "passive", "other")

    def test_all_scores_summary(self, predictor):
        """每个类别都有分数"""
        item = {
            "reference": "U1",
            "part_number": "STM32F103",
            "package": "LQFP-48",
            "description": "MCU",
        }
        _, _, debug = predictor.classify(item)
        scores = debug["scores"]
        assert len(scores) == NUM_COMPONENT_CLASSES
        for name in COMPONENT_CLASSES:
            assert name in scores

    def test_build_input_text_format(self, predictor):
        """输入文本格式正确"""
        item = {
            "reference": "R3,R4",
            "part_number": "RC0603FR-0710KL",
            "package": "0603",
            "value": "10kΩ",
            "description": "贴片电阻",
        }
        text = predictor._build_input_text(item)
        assert "ref:R" in text
        assert "pn:RC0603FR-0710KL" in text
        assert "pkg:0603" in text
        assert "val:10kΩ" in text
        assert "desc:贴片电阻" in text


class TestTrainedModel:
    """使用实际训练的模型进行集成测试"""

    @pytest.fixture
    def trained_predictor(self):
        model_path = "data/component_model.pt"
        vocab_path = "data/vocab.json"

        if not os.path.exists(model_path) or not os.path.exists(vocab_path):
            pytest.skip("训练模型不存在，请先运行 python src/ml/train_component.py")

        return ComponentPredictor.from_path(model_path, vocab_path)

    def test_model_files_exist(self):
        """验证训练产物存在"""
        assert os.path.exists("data/component_model.pt"), "元件分类模型文件缺失"
        assert os.path.exists("data/vocab.json"), "词表文件缺失"
        assert os.path.exists("data/component_train_report.json"), "训练报告缺失"

    def test_model_file_size(self):
        """模型文件大小合理（< 5MB）"""
        size = os.path.getsize("data/component_model.pt")
        assert size < 5 * 1024 * 1024, f"模型文件过大: {size / 1024 / 1024:.1f}MB"
        print(f"元件模型文件大小: {size / 1024:.1f}KB")

    def test_sample_bom_items(self, trained_predictor):
        """真实 BOM CSV 中所有元件应正确分类（粗类）"""
        from src.bom.parser import BOMParser

        items = BOMParser().parse("tests/sample_bom.csv")

        expected_coarse = {
            # R1-R6: resistors → passive
            "R1": "passive", "R2": "passive", "R3": "passive",
            "R4": "passive", "R5": "passive", "R6": "passive",
            # C1-C7: capacitors → cap
            "C1": "cap", "C2": "cap", "C3": "cap",
            "C4": "cap", "C5": "cap", "C6": "cap", "C7": "cap",
            # ICs → ic
            "U1": "ic", "U2": "ic", "U3": "ic", "U4": "ic",
            # LEDs → passive
            "D1": "passive", "D2": "passive",
            # Inductor → passive
            "L1": "passive",
            # Crystal → other
            "X1": "other",
            # Connectors → other
            "J1": "other", "J2": "other",
        }

        for item in items:
            comp_type, confidence, debug = trained_predictor.classify(item)
            coarse = debug.get("coarse", "?")
            expected = expected_coarse.get(item.reference, "?")

            assert coarse == expected, (
                f"{item.reference}: ML 粗类={coarse}，期望={expected} "
                f"(细类={comp_type}, conf={confidence:.2f})"
            )

    def test_ic_subclassification(self, trained_predictor):
        """IC 应被细分为 mcu/power/analog/other"""
        test_ics = [
            ({"reference": "U1", "part_number": "STM32F103C8T6",
              "package": "LQFP-48", "description": "ARM Cortex-M3"}, "ic_mcu"),
            ({"reference": "U2", "part_number": "AMS1117-3.3",
              "package": "SOT-223", "description": "线性稳压器 3.3V 1A"}, "ic_power"),
            ({"reference": "U3", "part_number": "LM358",
              "package": "SOP-8", "description": "双运算放大器"}, "ic_analog"),
        ]

        for item, expected_fine in test_ics:
            fine_type, confidence, _debug = trained_predictor.classify(item)
            top_two = [name for name, _ in _debug["top_two"]]
            assert fine_type == expected_fine or expected_fine in top_two[:2], (
                f"{item['part_number']}: 细类={fine_type} (conf={confidence:.2f}), "
                f"期望={expected_fine}, top2={top_two}"
            )

    def test_capacitor_subclassification(self, trained_predictor):
        """电容应被细分为 mlcc/elec"""
        mlcc = {"reference": "C1", "part_number": "", "package": "0603",
                "value": "100nF", "description": "贴片电容 X7R"}
        fine, _, _ = trained_predictor.classify(mlcc)
        assert fine == "cap_mlcc", f"MLCC 误判为 {fine}"

        elec = {"reference": "C10", "part_number": "EEEFK1V101P", "package": "SMD-Φ8",
                "value": "100μF", "description": "铝电解电容 35V"}
        fine2, _, debug2 = trained_predictor.classify(elec)
        top_two2 = [n for n, _ in debug2["top_two"]]
        assert fine2 == "cap_elec" or "cap_elec" in top_two2[:2], (
            f"电解电容 细类={fine2}, top2={top_two2}"
        )

    def test_model_inference_speed(self, trained_predictor):
        """推理速度 < 5ms/条（CPU）"""
        import time

        test_item = {
            "reference": "U1",
            "part_number": "STM32F103C8T6",
            "package": "LQFP-48",
            "description": "ARM Cortex-M3 微控制器",
        }

        # 预热
        trained_predictor.classify(test_item)

        # 计时
        queries = [test_item] * 100

        start = time.perf_counter()
        for q in queries:
            trained_predictor.classify(q)
        elapsed = time.perf_counter() - start

        avg_ms = elapsed / len(queries) * 1000
        assert avg_ms < 5.0, f"推理速度过慢: {avg_ms:.2f}ms/条"
        print(f"推理速度: {avg_ms:.2f}ms/条")


class TestCheckerIntegration:
    """checker.py 集成测试 — 验证 _classify_component 使用 ML 模型"""

    def test_classify_component_uses_ml(self):
        """验证 _classify_component 优先使用 ML 模型"""
        from src.rules.checker import _classify_component, _init_component_model

        if not os.path.exists("data/component_model.pt"):
            pytest.skip("训练模型不存在")

        _init_component_model()

        from src.bom.parser import BOMParser
        items = BOMParser().parse("tests/sample_bom.csv")

        for item in items:
            coarse = _classify_component(item)
            assert coarse in ("ic", "cap", "passive", "other"), (
                f"{item.reference}: 无效粗类 '{coarse}'"
            )

    def test_classify_component_backward_compat(self):
        """粗类分类结果应与原规则一致（至少不会更差）"""
        from src.rules.checker import _classify_component, _init_component_model

        if not os.path.exists("data/component_model.pt"):
            pytest.skip("训练模型不存在")

        _init_component_model()

        from src.bom.parser import BOMParser
        items = BOMParser().parse("tests/sample_bom.csv")

        # 每个元件的粗类应合理
        for item in items:
            coarse = _classify_component(item)
            ref = item.reference
            prefix = "".join(ch for ch in ref if ch.isalpha()).upper()

            # 基本合理性检查：R 开头不应该是 cap/ic
            if prefix == "R":
                assert coarse != "cap", f"{ref}: 电阻不可能分到 cap"
                assert coarse != "ic", f"{ref}: 电阻不可能分到 ic"
            # C 开头应该是 cap
            if prefix == "C":
                assert coarse == "cap", f"{ref}: 电容前缀必须是 cap，实际 {coarse}"
            # U 开头应该是 ic
            if prefix == "U":
                assert coarse == "ic", f"{ref}: IC 前缀必须是 ic，实际 {coarse}"

    def test_rule_fallback_without_model(self):
        """模型文件缺失时，_classify_component 应回退规则"""
        from src.rules import checker as checker_module

        # 强制模型不可用
        old_predictor = checker_module._component_predictor
        old_attempted = checker_module._component_model_attempted
        old_path = checker_module._COMPONENT_MODEL_PATH

        try:
            checker_module._component_predictor = None
            checker_module._component_model_attempted = True  # 标记为已尝试，避免重新加载
            checker_module._COMPONENT_MODEL_PATH = "nonexistent/model.pt"

            from src.bom.parser import BOMItem
            item = BOMItem(
                reference="C1", value="100nF", package="0603",
                part_number="C1588", description="贴片电容",
            )
            coarse = checker_module._classify_component(item)
            # 规则应正确返回 cap（C 前缀）
            assert coarse == "cap", f"规则回退失败: {coarse}"

        finally:
            checker_module._component_predictor = old_predictor
            checker_module._component_model_attempted = old_attempted
            checker_module._COMPONENT_MODEL_PATH = old_path

    def test_fine_classify_with_model(self):
        """_classify_component_fine 返回细粒度分类"""
        from src.rules.checker import _classify_component_fine, _init_component_model

        if not os.path.exists("data/component_model.pt"):
            pytest.skip("训练模型不存在")

        _init_component_model()

        from src.bom.parser import BOMItem
        item = BOMItem(
            reference="U1", value="", package="LQFP-48",
            part_number="STM32F103C8T6", description="ARM MCU",
        )
        fine_type, confidence = _classify_component_fine(item)
        assert fine_type in COMPONENT_CLASSES, f"无效细类: {fine_type}"
        assert 0.0 <= confidence <= 1.0
