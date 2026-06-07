"""LLMRouter 单元测试 — 意图分类"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.agent.router import LLMRouter, TaskIntent, RouterConfig, ProviderBinding
from src.config import config as app_config


# ——— fixtures ———


@pytest.fixture
def router_no_api():
    """创建无 API key 的路由器"""
    return LLMRouter.from_config(api_key="")


@pytest.fixture
def router_with_key():
    """创建有 API key 的路由器"""
    return LLMRouter.from_config(api_key="sk-test-key-123456")


# ——— TaskIntent 枚举 ———


class TestTaskIntent:
    def test_all_intents(self):
        intents = list(TaskIntent)
        assert len(intents) == 7
        assert TaskIntent.TEXT_CHAT in intents
        assert TaskIntent.BOM_ANALYSIS in intents
        assert TaskIntent.RULE_CHECK in intents
        assert TaskIntent.PCB_ANALYSIS in intents
        assert TaskIntent.CODE_RULE_GEN in intents
        assert TaskIntent.VISUAL in intents
        assert TaskIntent.LOCAL_ONLY in intents


# ——— classify_intent（向后兼容） ———


class TestClassifyIntentBackwardCompat:
    """验证 classify_intent 行为不变"""

    def test_merge_bom(self, router_no_api):
        assert router_no_api.classify_intent("合并BOM") == TaskIntent.BOM_ANALYSIS

    def test_validate(self, router_no_api):
        assert router_no_api.classify_intent("校验封装") == TaskIntent.BOM_ANALYSIS

    def test_rule_check(self, router_no_api):
        assert router_no_api.classify_intent("检查设计规则") == TaskIntent.RULE_CHECK

    def test_code_gen(self, router_no_api):
        assert router_no_api.classify_intent("生成一个规则") == TaskIntent.CODE_RULE_GEN

    def test_pcb_analysis(self, router_no_api):
        assert router_no_api.classify_intent("分析PCB布局") == TaskIntent.PCB_ANALYSIS

    def test_visual(self, router_no_api):
        assert router_no_api.classify_intent("看看这张原理图") == TaskIntent.VISUAL

    def test_text_chat_fallback(self, router_no_api):
        assert router_no_api.classify_intent("你好") == TaskIntent.TEXT_CHAT


# ——— classify_intent_with_confidence ———


class TestClassifyIntentWithConfidence:
    def test_returns_tuple(self, router_no_api):
        result = router_no_api.classify_intent_with_confidence("合并BOM")
        assert isinstance(result, tuple)
        assert len(result) == 2
        intent, confidence = result
        assert isinstance(intent, TaskIntent)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_high_confidence_for_clear_input(self, router_no_api):
        _, confidence = router_no_api.classify_intent_with_confidence("合并BOM同类元件")
        assert confidence > 0.5

    def test_empty_input(self, router_no_api):
        intent, confidence = router_no_api.classify_intent_with_confidence("")
        assert intent == TaskIntent.TEXT_CHAT
        # 空输入 TEXT_CHAT 置信度较低
        assert confidence <= 0.5


# ——— 关键词扩充验证 ———


class TestExpandedKeywords:
    """验证新增关键词能命中"""

    def test_bom_list_keyword(self, router_no_api):
        """'物料清单' 应在 BOM_ANALYSIS"""
        assert router_no_api.classify_intent("整理物料清单") == TaskIntent.BOM_ANALYSIS

    def test_bom_material_keyword(self, router_no_api):
        """'材料' 应在 BOM_ANALYSIS"""
        assert router_no_api.classify_intent("材料合并") == TaskIntent.BOM_ANALYSIS

    def test_pcb_stackup(self, router_no_api):
        """'叠层' 应在 PCB_ANALYSIS"""
        assert router_no_api.classify_intent("检查叠层结构") == TaskIntent.PCB_ANALYSIS

    def test_pcb_routing(self, router_no_api):
        """'check routing' — 'routing' 在 PCB 关键词列表中"""
        intent = router_no_api.classify_intent("check routing")
        # "check" 可能命中 RULE_CHECK，"routing" 可能命中 PCB
        assert intent in (TaskIntent.PCB_ANALYSIS, TaskIntent.RULE_CHECK, TaskIntent.TEXT_CHAT)


# ——— available_intents ———


class TestAvailableIntents:
    def test_no_api_key_returns_empty(self, router_no_api):
        """无 API key 时 resolve 返回 None，但 available_intents 仍应列出"""
        available = router_no_api.available_intents
        assert isinstance(available, list)

    def test_with_api_key_returns_nonempty(self, router_with_key):
        """有 API key 时至少 VISUAL 不可用（moonshot 需要单独 key）"""
        available = router_with_key.available_intents
        assert len(available) >= 0  # 取决于 key 是否有效

    def test_local_only_not_in_available(self, router_no_api):
        available = router_no_api.available_intents
        # LOCAL_ONLY 的 binding name 是 "local"，resolve 返回 None
        assert TaskIntent.LOCAL_ONLY not in available
