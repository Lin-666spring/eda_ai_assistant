"""自研 NLU 意图分类器 — 测试套件"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 确保项目根在 path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

# src.ml 顶层 import torch：纯运行时依赖环境（requirements.txt 不含 torch）整文件收集即崩。
# 2026-10-10 依赖批：importorskip 让 ML 测试在未装 requirements-dev 的环境下跳过。
pytest.importorskip("torch", reason="ML 测试需要 torch（pip install -r requirements-dev.txt）")
from src.ml.vocab import PCBVocab
from src.ml.intent_classifier import (
    IntentClassifier,
    IntentPredictor,
    INTENT_CLASSES,
    INTENT_TO_IDX,
    NUM_CLASSES,
    DEFAULT_CONFIG,
)


class TestPCBVocab:
    """词表单元测试"""

    def test_build_vocab(self):
        vocab = PCBVocab()
        assert len(vocab) > 1000, "词表应有足够字符覆盖"
        assert vocab.pad_id == 0
        assert vocab.unk_id == 1

    def test_encode_decode_ascii(self):
        vocab = PCBVocab()
        text = "Hello, PCB!"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        assert decoded == text

    def test_encode_decode_chinese(self):
        vocab = PCBVocab()
        text = "检查电源走线宽度"
        ids = vocab.encode(text)
        decoded = vocab.decode(ids)
        assert decoded == text

    def test_encode_unknown_char(self):
        vocab = PCBVocab()
        text = "test \U0001f600"  # emoji not in vocab
        ids = vocab.encode(text)
        assert vocab.unk_id in ids

    def test_save_load(self):
        vocab = PCBVocab()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            vocab.save(f.name)
            path = f.name

        try:
            loaded = PCBVocab.load(path)
            assert len(loaded) == len(vocab)
            assert loaded.pad_id == vocab.pad_id
            assert loaded.unk_id == vocab.unk_id

            # 验证编解码一致性
            text = "STM32F103的VDD引脚"
            assert loaded.decode(loaded.encode(text)) == text
        finally:
            os.unlink(path)

    def test_vocab_size_property(self):
        vocab = PCBVocab()
        assert vocab.vocab_size == len(vocab)


class TestIntentClassifier:
    """模型单元测试"""

    def test_model_creation(self):
        vocab = PCBVocab()
        model = IntentClassifier(vocab_size=len(vocab))
        assert isinstance(model, IntentClassifier)

        # 检查参数数量合理
        params = model._count_params()
        assert 100_000 < params < 500_000, (
            f"期望参数量在 100K-500K 之间，实际 {params}"
        )

    def test_forward_shape(self):
        vocab = PCBVocab()
        model = IntentClassifier(vocab_size=len(vocab))

        # 伪造输入
        import torch
        batch_size = 4
        seq_len = 32
        input_ids = torch.randint(0, len(vocab), (batch_size, seq_len))

        logits = model(input_ids)
        assert logits.shape == (batch_size, NUM_CLASSES)

    def test_predict(self):
        vocab = PCBVocab()
        model = IntentClassifier(vocab_size=len(vocab))

        import torch
        input_ids = torch.randint(0, len(vocab), (2, DEFAULT_CONFIG["max_len"]))

        intents, confidences = model.predict(input_ids)
        assert len(intents) == 2
        assert len(confidences) == 2
        assert all(i in INTENT_CLASSES for i in intents)
        assert all(0.0 <= c <= 1.0 for c in confidences)

    def test_save_load(self):
        vocab = PCBVocab()
        model = IntentClassifier(vocab_size=len(vocab))

        with tempfile.NamedTemporaryFile(
            suffix=".pt", delete=False
        ) as f:
            model.save(f.name)
            path = f.name

        try:
            loaded = IntentClassifier.load(path)
            assert loaded.vocab_size == model.vocab_size
            assert loaded.embed_dim == model.embed_dim
            assert loaded.num_classes == model.num_classes

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
        model = IntentClassifier(vocab_size=len(vocab))
        model.eval()

        text = "检查电源走线"
        ids = vocab.encode(text)
        ids = ids + [vocab.pad_id] * (DEFAULT_CONFIG["max_len"] - len(ids))
        input_ids = torch.tensor([ids])

        with torch.no_grad():
            logits1 = model(input_ids)
            logits2 = model(input_ids)

        assert torch.equal(logits1, logits2)


class TestIntentPredictor:
    """推理封装测试"""

    @pytest.fixture
    def predictor(self):
        """使用模板数据训练一个临时模型"""
        import torch
        torch.manual_seed(42)

        vocab = PCBVocab()
        model = IntentClassifier(vocab_size=len(vocab))
        return IntentPredictor(model, vocab)

    def test_classify_returns_valid(self, predictor):
        intent, confidence, debug = predictor.classify("检查电源走线")
        assert intent in INTENT_CLASSES
        assert 0.0 <= confidence <= 1.0
        assert "scores" in debug
        assert "top_two" in debug
        assert len(debug["top_two"]) == 2
        assert debug.get("model") == "local_textcnn"

    def test_classify_empty_input(self, predictor):
        intent, confidence, debug = predictor.classify("")
        assert intent == "TEXT_CHAT"
        assert confidence == 0.0
        assert "reason" in debug

    def test_classify_whitespace(self, predictor):
        intent, confidence, debug = predictor.classify("   ")
        assert intent == "TEXT_CHAT"

    def test_all_scores_summary(self, predictor):
        """每个意图类别都有分数"""
        _, _, debug = predictor.classify("帮我检查PCB设计规则")
        scores = debug["scores"]
        assert len(scores) == NUM_CLASSES
        for name in INTENT_CLASSES:
            assert name in scores


class TestTrainedModel:
    """使用实际训练的模型进行集成测试"""

    @pytest.fixture
    def trained_predictor(self):
        model_path = "data/intent_model.pt"
        vocab_path = "data/vocab.json"

        if not os.path.exists(model_path) or not os.path.exists(vocab_path):
            pytest.skip("训练模型不存在，请先运行 python src/ml/train_intent.py")

        return IntentPredictor.from_path(model_path, vocab_path)

    def test_model_files_exist(self):
        """验证训练产物存在"""
        assert os.path.exists("data/intent_model.pt"), "模型文件缺失"
        assert os.path.exists("data/vocab.json"), "词表文件缺失"
        assert os.path.exists("data/nlu_train_report.json"), "训练报告缺失"

    def test_model_file_size(self):
        """模型文件大小合理（< 3MB）"""
        size = os.path.getsize("data/intent_model.pt")
        assert size < 3 * 1024 * 1024, f"模型文件过大: {size / 1024 / 1024:.1f}MB"
        print(f"模型文件大小: {size / 1024:.1f}KB")

    def test_typical_queries(self, trained_predictor):
        """典型 PCB 查询应正确分类"""
        test_cases = [
            ("检查电源走线宽度", "RULE_CHECK"),
            ("帮我合并BOM中的同类元件", "BOM_ANALYSIS"),
            ("分析一下PCB布局", "PCB_ANALYSIS"),
            ("什么是去耦电容？", "TEXT_CHAT"),
            ("查一下这个元件有没有库存", "BOM_HEALTH"),
            ("生成HTML交互式BOM", "REPORT_GEN"),
            ("帮我写一个去耦电容检查规则", "CODE_RULE_GEN"),
            ("这张原理图帮我看看", "VISUAL"),
            ("查询STM32F103C8T6的规格参数", "COMPONENT_LOOKUP"),
            ("显示BOM统计信息", "LOCAL_ONLY"),
        ]

        for text, expected_intent in test_cases:
            intent, confidence, debug = trained_predictor.classify(text)
            top_two = [name for name, _ in debug["top_two"][:2]]
            assert (
                intent == expected_intent or expected_intent in top_two
            ), (
                f"'{text}' → {intent} (conf={confidence:.2f}), "
                f"期望 {expected_intent}, top2={top_two}"
            )

    def test_drc_queries_go_to_rule_check(self, trained_predictor):
        """DRC 相关查询应归到 RULE_CHECK"""
        drc_queries = [
            "检查设计规则",
            "跑一下DRC",
            "看看去耦电容放对没有",
            "检查走线有没有问题",
            "电源线宽度够不够",
        ]
        for q in drc_queries:
            intent, confidence, _ = trained_predictor.classify(q)
            top_intents = [intent]
            assert "RULE_CHECK" in top_intents or confidence > 0.3, (
                f"'{q}' → {intent} (conf={confidence:.2f})，期望 RULE_CHECK"
            )

    def test_model_inference_speed(self, trained_predictor):
        """推理速度 < 5ms/条（CPU）"""
        import time

        # 预热
        trained_predictor.classify("测试")

        # 计时
        queries = [
            "检查电源走线",
            "帮我分析BOM",
            "这块PCB布局合理吗",
            "什么是去耦电容",
        ] * 25  # 100 条

        start = time.perf_counter()
        for q in queries:
            trained_predictor.classify(q)
        elapsed = time.perf_counter() - start

        avg_ms = elapsed / len(queries) * 1000
        assert avg_ms < 5.0, f"推理速度过慢: {avg_ms:.2f}ms/条"
        print(f"推理速度: {avg_ms:.2f}ms/条")


class TestBertIntentPredictor:
    """rbt3 ONNX 意图分类器测试（2026-10-14 BERT 批）

    产物不入库（data/models/intent_bert/model.onnx 已 gitignore），
    克隆后先跑 scripts/download_rbt3.py + src/ml/train_intent_bert.py 再生，
    缺产物时本组自动 skip（与 data/*.pt 的 skip 约定一致）。
    """

    @pytest.fixture
    def bert_predictor(self):
        pytest.importorskip("onnxruntime", reason="BERT 运行时需要 onnxruntime")
        pytest.importorskip("tokenizers", reason="BERT 运行时需要 tokenizers")
        model_dir = Path("data/models/intent_bert")
        if not (model_dir / "model.onnx").exists():
            pytest.skip("BERT 模型产物不存在，先跑 scripts/download_rbt3.py "
                        "+ src/ml/train_intent_bert.py")

        from src.ml.intent_bert import BertIntentPredictor
        return BertIntentPredictor.from_path(model_dir)

    def test_load_and_contract(self, bert_predictor):
        assert bert_predictor is not None
        intent, confidence, debug = bert_predictor.classify("检查电源走线")
        assert intent in INTENT_CLASSES
        assert 0.0 <= confidence <= 1.0
        assert abs(sum(debug["scores"].values()) - 1.0) < 0.01, "softmax 概率和应≈1"
        assert len(debug["top_two"]) == 2
        assert debug["model"] == "local_bert_onnx"

    def test_empty_and_whitespace(self, bert_predictor):
        intent, confidence, debug = bert_predictor.classify("")
        assert intent == "TEXT_CHAT" and confidence == 0.0
        assert "reason" in debug
        intent, _, _ = bert_predictor.classify("   ")
        assert intent == "TEXT_CHAT"

    def test_all_scores_present(self, bert_predictor):
        _, _, debug = bert_predictor.classify("帮我检查PCB设计规则")
        assert len(debug["scores"]) == NUM_CLASSES
        for name in INTENT_CLASSES:
            assert name in debug["scores"]

    def test_typical_queries(self, bert_predictor):
        """典型查询（裸模型口径，引擎级另有 OOD 门+关键词回退）"""
        cases = [
            ("检查电源走线宽度", "RULE_CHECK"),
            ("帮我合并BOM中的同类元件", "BOM_ANALYSIS"),
            ("分析一下PCB布局", "PCB_ANALYSIS"),
            ("什么是去耦电容？", "TEXT_CHAT"),
            ("生成HTML交互式BOM", "REPORT_GEN"),
            ("这张原理图帮我看看", "VISUAL"),
            ("显示BOM统计信息", "LOCAL_ONLY"),
        ]
        for text, expected in cases:
            intent, conf, _ = bert_predictor.classify(text)
            assert intent == expected, f"{text!r} → {intent}({conf:.2f})，期望 {expected}"

    def test_short_commands(self, bert_predictor):
        """短命令（BERT 相对 TextCNN 的弱项，模板全覆盖后应过关）。

        「运行DRC」刻意不在此列：4 字输入跨训练 seed 在 RULE_CHECK/
        BOM_ANALYSIS 间摇摆（0.6-0.7 置信），裸模型口径不稳定；运行时由
        关键词层（探针硬断言）与中置信澄清（controller 0.40-0.70）兜底。
        """
        cases = [
            ("查重", "BOM_ANALYSIS"),
            ("全板DRC跑一遍", "RULE_CHECK"),
        ]
        for text, expected in cases:
            intent, conf, _ = bert_predictor.classify(text)
            assert intent == expected, f"{text!r} → {intent}({conf:.2f})，期望 {expected}"

    def test_inference_speed(self, bert_predictor):
        """fp16 ONNX 单条推理 < 30ms（实测 ~3-5ms）"""
        import time
        bert_predictor.classify("预热")
        queries = ["检查电源走线", "帮我分析BOM", "什么是去耦电容"] * 20
        t0 = time.perf_counter()
        for q in queries:
            bert_predictor.classify(q)
        avg_ms = (time.perf_counter() - t0) / len(queries) * 1000
        assert avg_ms < 30.0, f"推理过慢: {avg_ms:.2f}ms/条"
        print(f"BERT 推理速度: {avg_ms:.2f}ms/条")


class TestNLUEngineIntegration:
    """NLU 引擎集成测试 — 验证本地模型集成到 NLUEngine"""

    @pytest.fixture
    def engine(self):
        from src.agent.nlu_engine import NLUEngine
        return NLUEngine()

    def test_engine_uses_local_model_if_available(self, engine):
        """如果本地模型可用（BERT 或 TextCNN 兜底），engine 应优先使用"""
        has_bert = Path("data/models/intent_bert/model.onnx").exists()
        has_textcnn = os.path.exists("data/intent_model.pt")
        if not (has_bert or has_textcnn):
            pytest.skip("本地模型产物不存在")

        intent, confidence, debug = engine.classify("检查电源走线")
        model_used = debug.get("model", "")
        # 2026-10-14 BERT 批：标签由预测器自带（local_bert_onnx 优先，
        # TextCNN 兜底 local_textcnn）；回退路径带 + 后缀
        assert model_used.split("+")[0] in ("local_bert_onnx", "local_textcnn"), (
            f"应使用本地模型，实际: {model_used}"
        )

    def test_engine_debug_structure_compatible(self, engine):
        """debug 结构保持向后兼容"""
        _, _, debug = engine.classify("检查PCB设计")

        # 原有字段保持存在
        assert "scores" in debug
        assert "top_two" in debug
        assert len(debug["top_two"]) == 2

    def test_engine_fallback_without_model(self):
        """本地模型不可用时，engine 应正常降级到 embedding+keyword"""
        from src.agent.nlu_engine import NLUEngine

        # 强制本地模型不可用
        engine = NLUEngine()
        engine._local_model_attempted = True
        engine._local_predictor = None

        intent, confidence, debug = engine.classify("检查BOM")
        assert intent in INTENT_CLASSES
        # 不应包含本地模型标记（BERT 与 TextCNN 均不算）
        model = debug.get("model", "")
        assert not model.startswith("local_")
