"""LLM 客户端单元测试"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from src.agent.llm_client import (
    ChatRequest,
    StreamToken,
    LLMClient,
    resolve_provider,
    _extract_reply_text,
    _parse_tool_call_from_response,
    _parse_stream_line,
)


# ——— resolve_provider ———

class TestResolveProvider:
    def test_deepseek_preset(self):
        url, model = resolve_provider("deepseek")
        assert "deepseek.com" in url
        assert "deepseek" in model.lower()

    def test_openai_preset(self):
        url, model = resolve_provider("openai")
        assert "openai.com" in url
        assert "gpt" in model.lower()

    def test_qwen_preset(self):
        url, model = resolve_provider("qwen")
        assert "aliyuncs.com" in url

    def test_manual_override(self):
        url, model = resolve_provider(provider="openai", base_url="https://custom.com/v1", model="custom-model")
        assert url == "https://custom.com/v1"
        assert model == "custom-model"

    def test_unknown_provider_falls_back_to_default(self):
        url, model = resolve_provider("nonexistent")
        assert "deepseek.com" in url

    def test_case_insensitive(self):
        url1, model1 = resolve_provider("DEEPSEEK")
        url2, model2 = resolve_provider("DeepSeek")
        assert url1 == url2
        assert model1 == model2

    def test_default_when_none(self):
        url, model = resolve_provider(None)
        assert "deepseek.com" in url


# ——— ChatRequest.build_payload ———

class TestChatRequestBuildPayload:
    def test_basic_payload(self):
        req = ChatRequest(messages=[{"role": "user", "content": "hello"}])
        payload = req.build_payload("test-model")
        assert payload["model"] == "test-model"
        assert payload["messages"] == [{"role": "user", "content": "hello"}]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 4096
        assert payload["stream"] is False

    def test_stream_payload(self):
        req = ChatRequest(messages=[], stream=True)
        payload = req.build_payload("m")
        assert payload["stream"] is True

    def test_extra_fields(self):
        req = ChatRequest(messages=[])
        payload = req.build_payload("m", tools=[{"type": "function", "function": {}}], tool_choice="auto")
        assert "tools" in payload
        assert payload["tool_choice"] == "auto"


# ——— _extract_reply_text ———

class TestExtractReplyText:
    def test_normal_response(self):
        resp = {"choices": [{"message": {"content": "你好"}}]}
        assert _extract_reply_text(resp) == "你好"

    def test_empty_content(self):
        resp = {"choices": [{"message": {"content": ""}}]}
        assert _extract_reply_text(resp) == ""


# ——— _parse_tool_call_from_response ———

class TestParseToolCall:
    def test_with_tool_call(self):
        resp = {
            "choices": [{"message": {"tool_calls": [
                {"function": {"name": "merge_bom", "arguments": '{"keyword": "test"}'}}
            ]}}]
        }
        result = _parse_tool_call_from_response(resp)
        assert result["name"] == "merge_bom"
        assert result["arguments"] == {"keyword": "test"}

    def test_no_tool_calls(self):
        resp = {"choices": [{"message": {}}]}
        result = _parse_tool_call_from_response(resp)
        assert result == {"name": "", "arguments": {}}


# ——— _parse_stream_line ———

class TestParseStreamLine:
    def test_content_line(self):
        token = _parse_stream_line('data: {"choices":[{"delta":{"content":"你好"}}]}')
        assert token.content == "你好"
        assert not token.is_done

    def test_done_signal(self):
        token = _parse_stream_line("data: [DONE]")
        assert token.is_done
        assert token.content == ""

    def test_empty_line(self):
        token = _parse_stream_line("")
        assert token.content == ""
        assert not token.is_done

    def test_non_data_line(self):
        token = _parse_stream_line(": ping")
        assert token.content == ""
        assert not token.is_done

    def test_malformed_json(self):
        token = _parse_stream_line("data: {broken")
        assert token.content == ""
        assert not token.is_done


# ——— LLMClient ———

@pytest.fixture
def client():
    """共享 LLMClient fixture"""
    return LLMClient(api_key="sk-test-key")


class TestLLMClient:

    def test_provider_label(self, client):
        assert isinstance(client.provider_label, str)
        assert len(client.provider_label) > 0

    def test_headers_contain_auth(self, client):
        headers = client._build_headers()
        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["Content-Type"] == "application/json"

    def test_prepare_request_no_history(self, client):
        req = client._prepare_request("你好", system_prompt="你是一个助手")
        assert len(req.messages) == 2
        assert req.messages[0]["role"] == "system"
        assert req.messages[0]["content"] == "你是一个助手"
        assert req.messages[1]["role"] == "user"
        assert req.messages[1]["content"] == "你好"

    def test_prepare_request_stream(self, client):
        req = client._prepare_request("hi", stream=True)
        assert req.stream is True

    def test_prepare_request_no_system_prompt(self, client):
        req = client._prepare_request("hi")
        assert len(req.messages) == 1
        assert req.messages[0]["role"] == "user"

    def test_record_and_get_history(self, client):
        assert client.get_history() == []
        client._record_turn("user msg", "assistant reply")
        history = client.get_history()
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "user msg"}
        assert history[1] == {"role": "assistant", "content": "assistant reply"}

    def test_clear_history(self, client):
        client._record_turn("q", "a")
        client.clear_history()
        assert client.get_history() == []

    def test_prepare_request_with_history(self, client):
        client._record_turn("q1", "a1")
        client._record_turn("q2", "a2")
        req = client._prepare_request("q3", use_history=True)
        assert len(req.messages) == 5  # q1,a1,q2,a2 + q3
        assert req.messages[0]["role"] == "user"
        assert req.messages[0]["content"] == "q1"

    def test_model_defaults(self, client):
        assert client.model is not None
        assert client.base_url is not None


# ——— Multimodal ———


class TestMultimodalRequest:
    """多模态请求结构测试"""

    def test_prepare_multimodal_content_array(self, client):
        req = client._prepare_multimodal_request(
            "分析这张PCB", "fakebase64data", system_prompt="你是一个视觉专家",
        )
        # 验证消息结构
        assert len(req.messages) == 2  # system + user
        assert req.messages[0]["role"] == "system"
        assert req.messages[0]["content"] == "你是一个视觉专家"

        user_msg = req.messages[1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)  # content array
        assert len(user_msg["content"]) == 2  # text + image

        # 第一部分：文本
        assert user_msg["content"][0]["type"] == "text"
        assert user_msg["content"][0]["text"] == "分析这张PCB"

        # 第二部分：图片
        assert user_msg["content"][1]["type"] == "image_url"
        assert "url" in user_msg["content"][1]["image_url"]

    def test_image_b64_prefixed_with_data_uri(self, client):
        """纯 base64 应自动补 data: 前缀"""
        req = client._prepare_multimodal_request("test", "plainbase64string")
        # 无 system prompt → 只有 1 条消息
        user_msg = req.messages[0]
        assert user_msg["role"] == "user"
        url = user_msg["content"][1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")

    def test_image_data_uri_unchanged(self, client):
        """已含 data: 前缀的不重复添加"""
        data_uri = "data:image/jpeg;base64,/9j/4AAQ"
        req = client._prepare_multimodal_request("test", data_uri)
        user_msg = req.messages[0]
        url = user_msg["content"][1]["image_url"]["url"]
        assert url == data_uri

    def test_manual_model_and_url(self):
        c = LLMClient(api_key="sk-xxx", base_url="https://my.api/v1", model="my-model")
        assert c.base_url == "https://my.api/v1"
        assert c.model == "my-model"
