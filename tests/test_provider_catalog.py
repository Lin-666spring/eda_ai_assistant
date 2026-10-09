# -*- coding: utf-8 -*-
"""厂商 / 模型目录 — 预设完整性、协议适配、实时拉取、前端不漂移。

背景（2026-09-10 核对）：
  * 前端 app.js 手写了一份 10 家厂商 + 模型清单的副本，已积了一堆不存在的
    型号（`deepseek-v4.5-flash` 从未存在、`deepseek-v4-flash` 官方已退役、
    `gpt-5.5`/`claude-opus-4-8` 均已被换代）；
  * `test_llm_connection()` 用第三方 `openai` SDK 建客户端，而 openai **不在
    requirements.txt 里**；且 Claude 的 base_url 是原生 Messages API，套给
    OpenAI SDK 必然 404。

现在：厂商表 → src/constants.py（SSOT）；实时列表 → GET /models；
前端只消费 get_providers()。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agent import model_catalog  # noqa: E402
from src.agent.llm_client import (  # noqa: E402
    _looks_like_unsupported_param,
    _strip_sampling_params,
)
from src.constants import (  # noqa: E402
    DEFAULT_PROVIDER,
    LLM_PROVIDER_PRESETS,
    ProviderPreset,
    get_provider_preset,
)

# P1-6 阶段C 后 app.js 拆为 web/js/*.js 多模块；断言改对模块拼接源做
# （各模块按序拼接 ≡ 原 app.js）。
def _frontend_js() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((ROOT / "web" / "js").glob("*.js"))
        if p.name != "marked.min.js"
    )


# ══════════════════════════════════════════════════════
#  1. 预设完整性
# ══════════════════════════════════════════════════════


class TestPresetIntegrity:
    def test_default_provider_exists(self):
        assert DEFAULT_PROVIDER in LLM_PROVIDER_PRESETS

    def test_keys_match_preset_names(self):
        for key, preset in LLM_PROVIDER_PRESETS.items():
            assert key == preset.name, f"{key} != {preset.name}"

    def test_all_have_https_base_url(self):
        for key, p in LLM_PROVIDER_PRESETS.items():
            assert p.base_url.startswith("https://"), key

    def test_default_model_is_in_models(self):
        """default_model 必须在兜底清单里，否则下拉框选不中默认值。"""
        for key, p in LLM_PROVIDER_PRESETS.items():
            if p.models:
                assert p.default_model in p.models, \
                    f"{key}: default_model {p.default_model} 不在 models {p.models}"

    def test_models_are_unique_and_nonempty(self):
        for key, p in LLM_PROVIDER_PRESETS.items():
            assert len(set(p.models)) == len(p.models), f"{key} 有重复型号"
            assert all(m.strip() for m in p.models), key

    def test_protocol_values(self):
        for key, p in LLM_PROVIDER_PRESETS.items():
            assert p.protocol in ("openai", "anthropic"), key

    def test_only_claude_uses_native_anthropic_protocol(self):
        native = {k for k, p in LLM_PROVIDER_PRESETS.items() if p.protocol == "anthropic"}
        assert native == {"claude"}

    def test_anthropic_preset_points_at_messages(self):
        assert LLM_PROVIDER_PRESETS["claude"].base_url.endswith("/messages")

    def test_icon_and_key_url_present(self):
        for key, p in LLM_PROVIDER_PRESETS.items():
            assert p.icon and len(p.icon) <= 3, key
            assert p.key_url.startswith("https://"), f"{key} 缺少申请 Key 的地址"

    def test_no_known_retired_models_offered(self):
        """已经确认退役/从未存在的型号不能出现在兜底清单里。"""
        deepseek_models = set(LLM_PROVIDER_PRESETS["deepseek"].models)
        assert "deepseek-v4.5-flash" not in deepseek_models   # 从未存在过
        assert "deepseek-v4-flash" not in deepseek_models     # 官方已退役
        assert LLM_PROVIDER_PRESETS["deepseek"].default_model == "deepseek-flash"


class TestGetProviderPreset:
    def test_lookup_is_case_insensitive(self):
        assert get_provider_preset("GLM") is LLM_PROVIDER_PRESETS["glm"]

    @pytest.mark.parametrize("bad", [None, "", "not-a-provider"])
    def test_unknown_falls_back_to_default(self, bad):
        assert get_provider_preset(bad) is LLM_PROVIDER_PRESETS[DEFAULT_PROVIDER]


# ══════════════════════════════════════════════════════
#  2. 端点推导 & 响应解析
# ══════════════════════════════════════════════════════


class TestModelsEndpoint:
    def test_openai_style_appends_models(self):
        url = model_catalog.models_endpoint(LLM_PROVIDER_PRESETS["glm"])
        assert url == "https://open.bigmodel.cn/api/paas/v4/models"

    def test_anthropic_strips_messages(self):
        url = model_catalog.models_endpoint(LLM_PROVIDER_PRESETS["claude"])
        assert url == "https://api.anthropic.com/v1/models"

    def test_base_url_override_wins(self):
        url = model_catalog.models_endpoint(
            LLM_PROVIDER_PRESETS["claude"], "https://proxy.local/v1/messages")
        assert url == "https://proxy.local/v1/models"

    def test_no_double_slash(self):
        url = model_catalog.models_endpoint(LLM_PROVIDER_PRESETS["glm"],
                                            "https://x.local/v4/")
        assert url == "https://x.local/v4/models"


class TestExtractIds:
    def test_openai_shape(self):
        payload = {"data": [{"id": "a"}, {"id": "b"}]}
        assert model_catalog._extract_ids(payload) == ["a", "b"]

    def test_name_shape(self):
        assert model_catalog._extract_ids({"models": [{"name": "x"}]}) == ["x"]

    def test_plain_string_list(self):
        assert model_catalog._extract_ids({"data": ["m1", "m2"]}) == ["m1", "m2"]

    def test_dedupes_preserving_order(self):
        payload = {"data": [{"id": "a"}, {"id": "b"}, {"id": "a"}]}
        assert model_catalog._extract_ids(payload) == ["a", "b"]

    @pytest.mark.parametrize("payload", [None, [], {}, {"data": None}, {"data": 5}])
    def test_garbage_returns_empty(self, payload):
        assert model_catalog._extract_ids(payload) == []


class TestChatModelFilter:
    @pytest.mark.parametrize("mid", [
        "text-embedding-3-large", "bge-m3", "whisper-1", "dall-e-3",
        "gpt-4o-audio-preview", "gemini-3.1-flash-tts-preview",
    ])
    def test_non_chat_filtered(self, mid):
        assert not model_catalog._is_chat_model(mid)

    @pytest.mark.parametrize("mid", [
        "deepseek-flash", "glm-5.3", "claude-opus-5", "gpt-5.6-sol",
        "gemini-3.8-flash", "kimi-k3",
    ])
    def test_chat_models_kept(self, mid):
        assert model_catalog._is_chat_model(mid)


# ══════════════════════════════════════════════════════
#  3. 实时拉取（mock HTTP）
# ══════════════════════════════════════════════════════


class _FakeResponse:
    def __init__(self, payload=None, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            err = requests.HTTPError(f"{self.status_code} error")
            err.response = self
            raise err

    def json(self):
        return self._payload


class _Recorder:
    """记录 requests.get 的调用参数，并按需返回预设响应。"""

    def __init__(self, monkeypatch, response=None, exc=None):
        self.calls = []
        self.response = response
        self.exc = exc
        monkeypatch.setattr(model_catalog.requests, "get", self)

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        if self.exc:
            raise self.exc
        return self.response


class TestListModels:
    def test_openai_style_success(self, monkeypatch):
        rec = _Recorder(monkeypatch, _FakeResponse(
            {"data": [{"id": "glm-5.3"}, {"id": "glm-5.2"}, {"id": "glm-5.1"}]}))
        res = model_catalog.list_models("glm", "sk-test")
        assert res["ok"] is True
        assert res["models"][0] == "glm-5.3"          # 默认型号排最前
        assert set(res["models"]) == {"glm-5.3", "glm-5.2", "glm-5.1"}
        url, kw = rec.calls[0]
        assert url.endswith("/models")
        assert kw["headers"]["Authorization"] == "Bearer sk-test"

    def test_anthropic_uses_x_api_key_header(self, monkeypatch):
        rec = _Recorder(monkeypatch, _FakeResponse(
            {"data": [{"id": "claude-opus-5"}, {"id": "claude-sonnet-5"}]}))
        res = model_catalog.list_models("claude", "sk-ant")
        assert res["ok"] is True
        url, kw = rec.calls[0]
        assert url == "https://api.anthropic.com/v1/models"
        assert kw["headers"]["x-api-key"] == "sk-ant"
        assert kw["headers"]["anthropic-version"] == model_catalog.ANTHROPIC_VERSION
        assert "Authorization" not in kw["headers"]

    def test_default_model_is_hoisted(self, monkeypatch):
        _Recorder(monkeypatch, _FakeResponse(
            {"data": [{"id": "other"}, {"id": "glm-5.3"}]}))
        res = model_catalog.list_models("glm", "k")
        assert res["models"][0] == "glm-5.3"

    def test_non_chat_models_filtered_out(self, monkeypatch):
        _Recorder(monkeypatch, _FakeResponse({"data": [
            {"id": "glm-5.3"}, {"id": "text-embedding-3-large"}, {"id": "bge-m3"}]}))
        res = model_catalog.list_models("glm", "k")
        assert res["models"] == ["glm-5.3"]

    def test_missing_key_is_rejected_locally(self, monkeypatch):
        rec = _Recorder(monkeypatch, _FakeResponse({"data": []}))
        res = model_catalog.list_models("glm", "")
        assert res["ok"] is False and "API Key" in res["error"]
        assert rec.calls == []          # 不该发请求

    def test_401_gives_actionable_message(self, monkeypatch):
        _Recorder(monkeypatch, _FakeResponse({}, status=401))
        res = model_catalog.list_models("glm", "bad")
        assert res["ok"] is False
        assert "401" in res["error"] and "重新生成" in res["error"]

    def test_404_suggests_manual_entry(self, monkeypatch):
        _Recorder(monkeypatch, _FakeResponse({}, status=404))
        res = model_catalog.list_models("doubao", "k")
        assert res["ok"] is False and "手动填写" in res["error"]

    def test_network_error_is_graceful(self, monkeypatch):
        import requests
        _Recorder(monkeypatch, exc=requests.ConnectionError("boom"))
        res = model_catalog.list_models("glm", "k")
        assert res["ok"] is False and "无法连接" in res["error"]

    def test_empty_list_is_reported(self, monkeypatch):
        _Recorder(monkeypatch, _FakeResponse({"data": []}))
        res = model_catalog.list_models("glm", "k")
        assert res["ok"] is False and "空" in res["error"]

    def test_invalid_json_is_graceful(self, monkeypatch):
        class _Bad(_FakeResponse):
            def json(self):
                raise ValueError("not json")
        _Recorder(monkeypatch, _Bad(status=200))
        res = model_catalog.list_models("glm", "k")
        assert res["ok"] is False and "JSON" in res["error"]


class TestFallbackModels:
    def test_default_model_is_first(self):
        assert model_catalog.fallback_models("glm")[0] == "glm-5.3"

    def test_unknown_provider_falls_back_to_default(self):
        assert model_catalog.fallback_models("nope") == \
            model_catalog.fallback_models(DEFAULT_PROVIDER)

    def test_every_provider_has_fallback(self):
        for key in LLM_PROVIDER_PRESETS:
            models = model_catalog.fallback_models(key)
            assert models, key
            assert LLM_PROVIDER_PRESETS[key].default_model in models, key

    def test_inserts_default_when_preset_omits_it(self):
        """预设只写了 default_model、没写 models 时也要能选出默认值。"""
        bare = ProviderPreset("bare", "https://x/v1", "only-model", "d")
        assert bare.default_model not in bare.models
        LLM_PROVIDER_PRESETS["bare"] = bare
        try:
            assert model_catalog.fallback_models("bare") == ["only-model"]
        finally:
            del LLM_PROVIDER_PRESETS["bare"]


# ══════════════════════════════════════════════════════
#  4. 采样参数兼容（新推理模型移除了 temperature）
# ══════════════════════════════════════════════════════


class TestSamplingParamTolerance:
    @pytest.mark.parametrize("msg", [
        "Unsupported parameter: 'temperature' is not supported with this model.",
        "unknown parameter: top_p",
        "Invalid request: temperature has been removed",
    ])
    def test_detects_unsupported_sampling(self, msg):
        assert _looks_like_unsupported_param(msg)

    @pytest.mark.parametrize("msg", [
        "Incorrect API key provided",
        "Rate limit reached",
        "",
        "model not found",
    ])
    def test_ignores_unrelated_errors(self, msg):
        assert not _looks_like_unsupported_param(msg)

    def test_strip_removes_only_sampling(self):
        payload = {"model": "m", "temperature": 0.7, "top_p": 1, "messages": [],
                   "max_tokens": 10}
        stripped = _strip_sampling_params(payload)
        assert "temperature" not in stripped and "top_p" not in stripped
        assert stripped["model"] == "m" and stripped["max_tokens"] == 10


class TestSamplingRetryEndToEnd:
    """gpt-6-astra 这类模型会因 temperature 直接 400 —— 客户端应自动降级重试。"""

    def _patch(self, monkeypatch, fail_first_with: str):
        import requests
        import src.agent.llm_client as lc

        seen: list[dict] = []

        class _Err(_FakeResponse):
            def raise_for_status(self):
                err = requests.HTTPError("400 Client Error")
                err.response = self
                raise err

        def fake_post(url, headers=None, json=None, timeout=None, stream=False):
            seen.append(dict(json or {}))
            if len(seen) == 1:
                return _Err({"error": {"message": fail_first_with}},
                            status=400, text=fail_first_with)
            return _FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        monkeypatch.setattr(lc.requests, "post", fake_post)
        return lc, seen

    def test_retries_without_sampling_params(self, monkeypatch):
        lc, seen = self._patch(
            monkeypatch,
            "Unsupported parameter: 'temperature' is not supported with this model.")
        client = lc.LLMClient("sk-test", provider="openai", model="gpt-6-astra")
        assert client.chat("hi") == "ok"
        assert len(seen) == 2, "应当自动重试一次"
        assert "temperature" in seen[0]
        assert "temperature" not in seen[1], "重试请求必须去掉 temperature"
        assert seen[1]["model"] == "gpt-6-astra"
        assert seen[1]["messages"], "重试不能丢掉对话内容"

    def test_unrelated_400_is_not_retried(self, monkeypatch):
        import pytest as _pytest
        lc, seen = self._patch(monkeypatch, "Incorrect API key provided")
        client = lc.LLMClient("bad", provider="openai", model="gpt-5.6-sol")
        with _pytest.raises(Exception):
            client.chat("hi")
        assert len(seen) == 1, "无关的 400 不该重试"


# ══════════════════════════════════════════════════════
#  5. Eel 端点（含 test_llm_connection 的协议适配）
# ══════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def main_mod():
    import main
    return main


class TestGetProvidersEndpoint:
    def test_shape(self, main_mod):
        resp = main_mod.get_providers()
        assert resp["ok"] is True
        assert resp["count"] == len(LLM_PROVIDER_PRESETS)
        assert resp["default_provider"] == DEFAULT_PROVIDER
        keys = {p["key"] for p in resp["providers"]}
        assert keys == set(LLM_PROVIDER_PRESETS)

    def test_each_entry_is_complete(self, main_mod):
        for p in main_mod.get_providers()["providers"]:
            assert p["base_url"] and p["default_model"]
            assert p["models"] and p["default_model"] in p["models"]
            assert p["protocol"] in ("openai", "anthropic")
            assert p["icon"] and p["key_url"]

    def test_models_start_as_fallback(self, main_mod):
        for p in main_mod.get_providers()["providers"]:
            assert p["models_source"] == "fallback"


class TestTestConnectionProtocolAdaptation:
    """锁住 2026-09 修的两个坑：不依赖第三方 openai SDK；Claude 走原生协议。"""

    def _capture(self, monkeypatch):
        calls = []

        def fake_post(url, headers=None, json=None, timeout=None, stream=False):
            calls.append({"url": url, "headers": headers or {}, "json": json or {}})
            if "anthropic" in url:
                return _FakeResponse({"content": [{"type": "text", "text": "Hi"}]})
            return _FakeResponse({"choices": [{"message": {"content": "Hi"}}]})

        import src.agent.llm_client as lc
        import src.agent.anthropic_client as ac
        monkeypatch.setattr(lc.requests, "post", fake_post)
        monkeypatch.setattr(ac.requests, "post", fake_post)
        return calls

    def test_claude_hits_native_messages_endpoint(self, main_mod, monkeypatch):
        calls = self._capture(monkeypatch)
        resp = main_mod.test_llm_connection("claude", "sk-ant", "", "")
        assert resp["ok"] is True, resp
        assert resp["protocol"] == "anthropic"
        url = calls[0]["url"]
        assert url == "https://api.anthropic.com/v1/messages"
        # 绝不能再拼成 /messages/chat/completions（修复前的 404）
        assert "/messages/chat/completions" not in url
        assert calls[0]["headers"].get("x-api-key") == "sk-ant"

    def test_openai_compatible_hits_chat_completions(self, main_mod, monkeypatch):
        calls = self._capture(monkeypatch)
        resp = main_mod.test_llm_connection("glm", "sk-test", "", "")
        assert resp["ok"] is True, resp
        assert resp["protocol"] == "openai"
        assert calls[0]["url"] == "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        assert calls[0]["headers"]["Authorization"] == "Bearer sk-test"

    def test_missing_key_rejected_without_request(self, main_mod, monkeypatch):
        calls = self._capture(monkeypatch)
        resp = main_mod.test_llm_connection("glm", "", "", "")
        assert resp["ok"] is False and "API Key" in resp["error"]
        assert calls == []

    def test_does_not_import_third_party_openai_sdk(self):
        """`openai` 不在 requirements.txt 里，main.py 不能再依赖它。

        只检查真实的 import 语句，忽略注释/文档字符串里的举例
        （历史上曾因注释中出现该字符串而误报）。
        """
        import ast

        src = (ROOT / "main.py").read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert "openai" not in imported, "main.py 不应依赖 openai，实际 imports=" + str(sorted(imported))


class TestFetchProviderModelsEndpoint:
    def test_uses_saved_key_when_blank(self, main_mod, monkeypatch):
        seen = {}

        def fake_list(provider, api_key, base_url="", timeout=15):
            seen["provider"] = provider
            seen["api_key"] = api_key
            return {"ok": True, "provider": provider, "models": ["m"], "count": 1}

        monkeypatch.setattr("src.agent.model_catalog.list_models", fake_list)
        resp = main_mod.fetch_provider_models("glm", "", "")
        assert resp["ok"] is True and resp["models_source"] == "live"
        assert seen["provider"] == "glm"

    def test_error_passthrough(self, main_mod, monkeypatch):
        monkeypatch.setattr("src.agent.model_catalog.list_models",
                            lambda *a, **k: {"ok": False, "error": "boom", "models": []})
        resp = main_mod.fetch_provider_models("glm", "k", "")
        assert resp["ok"] is False and resp["error"] == "boom"
        assert "models_source" not in resp


# ══════════════════════════════════════════════════════
#  6. 前端不再自带一份厂商表
# ══════════════════════════════════════════════════════


class TestFrontendProviderSource:
    @pytest.fixture(scope="class")
    def app_js(self) -> str:
        return _frontend_js()

    def test_providers_start_empty_and_load_from_backend(self, app_js):
        assert re.search(r"var PROVIDERS = \{\};", app_js), \
            "PROVIDERS 应该从空对象开始，由 get_providers() 填充"
        assert "eel.get_providers()" in app_js

    def test_no_hardcoded_retired_model_ids(self, app_js):
        for stale in ("deepseek-v4.5-flash", "gpt-5.5", "claude-opus-4-8'",
                      "qwen3.6-plus", "gemini-3.1-flash-lite"):
            assert stale not in app_js, f"app.js 里还留着过时型号 {stale}"

    def test_endpoints_are_wired(self, app_js):
        assert "fetch_provider_models" in app_js
        assert "fetchModelsForProvider" in app_js
