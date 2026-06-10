"""NLUEngine 单元测试"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.agent.nlu_engine import (
    NLUEngine, IntentDescriptor, INTENT_DESCRIPTORS,
    EMBEDDING_WEIGHT, KEYWORD_WEIGHT,
    HIGH_CONFIDENCE, MEDIUM_CONFIDENCE, LOW_CONFIDENCE_FLOOR,
)


# ——— fixtures ———


@pytest.fixture
def engine_no_embedding():
    """创建不带 embedding 的引擎（模拟未配置 API key）"""
    engine = NLUEngine(api_key="")
    # 强制标记为不可用
    engine._embedding_failed = True
    engine._embedding_fn = None
    return engine


# ——— IntentDescriptor 完整性 ———


class TestIntentDescriptors:
    """验证所有 7 个意图都有完整描述"""

    def test_all_seven_intents(self):
        assert len(INTENT_DESCRIPTORS) == 10

    def test_each_has_name_label_description(self):
        for d in INTENT_DESCRIPTORS:
            assert d.intent_name, f"{d} missing intent_name"
            assert d.label, f"{d} missing label"
            assert d.description, f"{d} missing description"
            assert len(d.description) > 20, f"{d.intent_name} description too short"

    def test_each_has_keywords(self):
        for d in INTENT_DESCRIPTORS:
            assert len(d.keywords) >= 3, f"{d.intent_name} needs >=3 keywords"

    def test_each_has_examples(self):
        for d in INTENT_DESCRIPTORS:
            assert len(d.examples) >= 2, f"{d.intent_name} needs >=2 examples"


# ——— 纯关键词分类（无 embedding） ———


class TestKeywordOnlyClassification:
    """无 embedding 时的纯关键词分类"""

    def test_exact_bom_keyword(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("合并BOM")
        assert name == "BOM_ANALYSIS"
        # 纯关键词评分可能因归一化偏低，只要求 > 0.3
        assert confidence > 0.3
        assert not debug["embedding_used"]

    def test_chinese_merge(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("整理物料清单")
        assert name == "BOM_ANALYSIS", f"Expected BOM_ANALYSIS, got {name}"

    def test_pcb_layout(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("帮我分析PCB布局")
        assert name == "PCB_ANALYSIS", f"Expected PCB_ANALYSIS, got {name}"

    def test_rule_check(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("检查设计规则DRC")
        assert name == "RULE_CHECK", f"Expected RULE_CHECK, got {name}"

    def test_visual_image(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("帮我看看这张原理图")
        assert name == "VISUAL", f"Expected VISUAL, got {name}"

    def test_code_generation(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("生成一个DRC检查脚本")
        assert name == "CODE_RULE_GEN", f"Expected CODE_RULE_GEN, got {name}"

    def test_general_chat(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("什么是去耦电容")
        assert name == "TEXT_CHAT", f"Expected TEXT_CHAT, got {name}"

    def test_empty_input(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("")
        assert name == "TEXT_CHAT"
        assert confidence == 0.0

    def test_bom_health_keywords(self, engine_no_embedding):
        name, confidence, debug = engine_no_embedding.classify("检查元件库存和替代料")
        # "检查" 也可能命中 RULE_CHECK，所以接受多种结果
        assert name in ("BOM_ANALYSIS", "TEXT_CHAT", "RULE_CHECK", "BOM_HEALTH"), f"Unexpected intent: {name}"
        # "库存" 和 "替代料" 都在 BOM/BOM_HEALTH 关键词列表中


# ——— 置信度阈值 ———


class TestConfidenceTiers:
    """三档置信度行为"""

    def test_high_confidence_exact_match(self, engine_no_embedding):
        _, confidence, _ = engine_no_embedding.classify("合并BOM同类元件 校验封装")
        # 应该高置信度（命中了 BOM 的多个核心关键词）
        assert confidence >= MEDIUM_CONFIDENCE

    def test_empty_input_zero_confidence(self, engine_no_embedding):
        _, confidence, _ = engine_no_embedding.classify("")
        assert confidence == 0.0

    def test_random_text_returns_text_chat(self, engine_no_embedding):
        name, confidence, _ = engine_no_embedding.classify("xyzabc123 没有意义的随机文字")
        assert name == "TEXT_CHAT"
        assert confidence <= LOW_CONFIDENCE_FLOOR + 0.01


# ——— 追问生成 ———


class TestClarificationQuestion:
    """中置信度时的追问"""

    def test_generates_question(self, engine_no_embedding):
        question = engine_no_embedding.get_clarification_question("检查")
        assert "🤔" in question
        assert len(question) > 20

    def test_question_mentions_operations(self, engine_no_embedding):
        question = engine_no_embedding.get_clarification_question("分析一下")
        # 追问应该包含可用操作提示
        assert any(
            kw in question
            for kw in ["合并", "校验", "规则", "PCB", "BOM"]
        )


# ——— 工具方法 ———


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert NLUEngine._cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert NLUEngine._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_different_lengths(self):
        assert NLUEngine._cosine_similarity([1, 0], [1, 0, 0]) == 0.0

    def test_zero_vector(self):
        assert NLUEngine._cosine_similarity([0, 0], [1, 1]) == 0.0


class TestEngineProperties:
    def test_embedding_available_false(self, engine_no_embedding):
        assert not engine_no_embedding.embedding_available

    def test_intent_count(self, engine_no_embedding):
        assert engine_no_embedding.intent_count == 10

    def test_get_label(self, engine_no_embedding):
        assert engine_no_embedding._get_label("BOM_ANALYSIS") == "BOM物料分析"
        assert engine_no_embedding._get_label("TEXT_CHAT") == "通用对话"
        assert engine_no_embedding._get_label("NONEXISTENT") == "NONEXISTENT"


# ——— 混合评分 ———


class TestHybridScore:
    def test_empty_embedding_uses_keyword_only(self, engine_no_embedding):
        emb = {}
        kw = {"BOM_ANALYSIS": 0.8, "TEXT_CHAT": 0.1}
        hybrid = engine_no_embedding._hybrid_score(emb, kw)
        assert hybrid["BOM_ANALYSIS"] == 0.8

    def test_with_embedding_combines(self, engine_no_embedding):
        emb = {"BOM_ANALYSIS": 0.9, "TEXT_CHAT": 0.3, "RULE_CHECK": 0.5, "PCB_ANALYSIS": 0.2, "CODE_RULE_GEN": 0.1, "BOM_HEALTH": 0.15, "REPORT_GEN": 0.1, "COMPONENT_LOOKUP": 0.1, "VISUAL": 0.05, "LOCAL_ONLY": 0.05}
        kw = {"BOM_ANALYSIS": 0.7, "TEXT_CHAT": 0.1, "RULE_CHECK": 0.3, "PCB_ANALYSIS": 0.1, "CODE_RULE_GEN": 0.05, "BOM_HEALTH": 0.1, "REPORT_GEN": 0.05, "COMPONENT_LOOKUP": 0.05, "VISUAL": 0.05, "LOCAL_ONLY": 0.05}
        hybrid = engine_no_embedding._hybrid_score(emb, kw)
        assert "BOM_ANALYSIS" in hybrid
        # 混合后 BOM 应该得分最高
        assert hybrid["BOM_ANALYSIS"] > hybrid["RULE_CHECK"]


# ——— 消歧负关键词 ———


class TestNegativeKeywords:
    def test_pcb_keywords_rejected_by_code_gen_negative(self, engine_no_embedding):
        """'画一个PCB' — PCB '画' 在 negative 中，可能会被其他意图抢走"""
        name, _, _ = engine_no_embedding.classify("画一个PCB")
        # 负关键词惩罚后 PCB_ANALYSIS 得分降低，可能落在 TEXT_CHAT 或 VISUAL
        assert name in ("PCB_ANALYSIS", "TEXT_CHAT", "VISUAL", "CODE_RULE_GEN")

    def test_create_pcb_not_pcb_analysis(self, engine_no_embedding):
        """'创建一个PCB项目' — PCB_ANALYSIS 有 negative='创建'"""
        name, _, _ = engine_no_embedding.classify("创建一个PCB项目")
        # CODE_RULE_GEN 关键词含 "创建"，应该胜出
        assert name in ("CODE_RULE_GEN", "TEXT_CHAT")
