"""AnthropicClient 单元测试"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.agent.anthropic_client import AnthropicClient


class TestAnthropicClient:
    def test_init(self):
        c = AnthropicClient(api_key="sk-ant-test")
        assert c.api_key == "sk-ant-test"
        assert c.model == "claude-opus-4-8"
        assert c.base_url.endswith("/messages")

    def test_custom_model(self):
        c = AnthropicClient(api_key="k", model="claude-sonnet-4-6")
        assert c.model == "claude-sonnet-4-6"

    def test_headers(self):
        c = AnthropicClient(api_key="sk-ant-xxx")
        h = c._headers()
        assert h["x-api-key"] == "sk-ant-xxx"
        assert h["anthropic-version"] == "2023-06-01"
        assert h["content-type"] == "application/json"

    def test_build_messages_no_history(self):
        c = AnthropicClient(api_key="k")
        msgs = c._build_messages("hello")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"

    def test_build_messages_with_history(self):
        c = AnthropicClient(api_key="k")
        c._record_turn("q1", "a1")
        msgs = c._build_messages("q2", use_history=True)
        assert len(msgs) == 3  # user/assistant + new user
        assert msgs[0]["role"] == "user" and msgs[0]["content"] == "q1"
        assert msgs[1]["role"] == "assistant" and msgs[1]["content"] == "a1"
        assert msgs[2]["role"] == "user" and msgs[2]["content"] == "q2"

    def test_clear_history(self):
        c = AnthropicClient(api_key="k")
        c._record_turn("q", "a")
        assert len(c._history) == 2
        c.clear_history()
        assert len(c._history) == 0

    def test_convert_functions_to_tools(self):
        c = AnthropicClient(api_key="k")
        tools = c._convert_functions_to_tools([
            {"function": {"name": "test", "description": "d", "parameters": {"type": "object", "properties": {}}}}
        ])
        assert len(tools) == 1
        assert tools[0]["name"] == "test"
        assert tools[0]["description"] == "d"
        assert "input_schema" in tools[0]

    def test_extract_text(self):
        c = AnthropicClient(api_key="k")
        resp = {"content": [{"type": "text", "text": "hello"}, {"type": "text", "text": "world"}]}
        assert c._extract_text(resp) == "hello\nworld"

    def test_extract_text_empty(self):
        c = AnthropicClient(api_key="k")
        assert c._extract_text({"content": []}) == ""

    def test_chat_raises_without_network(self):
        """验证无网络时 chat 正确抛出异常"""
        c = AnthropicClient(api_key="invalid-key")
        with pytest.raises(Exception):
            c.chat("test")

    def test_record_turn_trims_history(self):
        c = AnthropicClient(api_key="k")
        for i in range(25):
            c._record_turn(f"q{i}", f"a{i}")
        assert len(c._history) <= 40  # 20 turns * 2

    def test_provider_label(self):
        c = AnthropicClient(api_key="k", provider="claude")
        assert c.provider_label == "claude"


class TestDesignTemplates:
    def test_engine_loads(self):
        from src.agent.design_templates import DesignTemplateEngine, DESIGN_TEMPLATES
        engine = DesignTemplateEngine()
        assert len(engine.templates) >= 12

    def test_match_stm32(self):
        from src.agent.design_templates import DesignTemplateEngine
        from src.bom.parser import BOMItem
        engine = DesignTemplateEngine()
        items = [
            BOMItem(reference="U1", value="", package="LQFP-48",
                    part_number="STM32F103C8T6", description="MCU", quantity=1),
            BOMItem(reference="C1,C2", value="100nF", package="0603",
                    part_number="C1588", description="贴片电容", quantity=2),
        ]
        matches = engine.match(items)
        assert len(matches) >= 1
        assert matches[0].template_name == "STM32 最小系统"
        assert matches[0].confidence > 0

    def test_no_match(self):
        from src.agent.design_templates import DesignTemplateEngine
        from src.bom.parser import BOMItem
        engine = DesignTemplateEngine()
        items = [BOMItem(reference="X1", value="", package="DIP-8",
                         part_number="UNKNOWN-12345", description="未知元件", quantity=1)]
        matches = engine.match(items)
        assert len(matches) == 0

    def test_suggestions_report(self):
        from src.agent.design_templates import DesignTemplateEngine
        from src.bom.parser import BOMItem
        engine = DesignTemplateEngine()
        items = [
            BOMItem(reference="U1", value="", package="LQFP-64",
                    part_number="STM32F407VET6", description="MCU", quantity=1),
        ]
        report = engine.get_suggestions_report(items)
        assert "STM32" in report
        assert len(report) > 50
