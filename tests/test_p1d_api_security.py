"""P1-18 回归（验收 2026-10-24）：REST API 反 CSRF / CORS 收敛 / TrustedHost。

修复前三个洞：
- CORS 白名单含 "null"：任意本地 file:// 页面可跨站读响应；
- /clear-all-data 等破坏性端点无鉴权：一个跨站 <form> POST 就能静默清空
  用户全部数据（含已存 API Key）—— CORS 拦「读响应」但拦不住「发请求」；
- 无 TrustedHostMiddleware：Host 头不设防。

负样本断言方向：跨站形态（无自定义头 / 非 null 白名单外 Origin / 陌生 Host）
必须被拒，且破坏性动作不得执行。
"""

import pytest
from fastapi.testclient import TestClient

from src.api.server import app

# 与 test_api_server.py 同口径：TrustedHost 只认回环，Host 必须落 127.0.0.1
client = TestClient(app, base_url="http://127.0.0.1:8710")

# P1-18 约定：破坏性端点必须携带的反 CSRF 头（前端/插件补头以此为准）
AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}

# 受保护端点清单（与 endpoints.py 的 Depends(require_ajax_header) 一一对应）
PROTECTED_ENDPOINTS = [
    ("post", "/api/v1/clear-all-data"),
    ("post", "/api/v1/settings"),
    ("post", "/api/v1/llm/config"),
    ("delete", "/api/v1/persist/assistant/test-instance"),
    ("delete", "/api/v1/persist/conversation/test-conv"),
]


class TestAjaxHeaderRequired:
    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_destructive_endpoint_without_header_is_403(self, method, path, monkeypatch):
        """无反 CSRF 头 → 403，且 clear_local_data 绝不能被执行。"""
        calls = []

        def _must_not_run(*a, **k):
            calls.append(1)
            raise AssertionError("破坏性动作在未携带反 CSRF 头时被执行")

        monkeypatch.setattr("src.config.clear_local_data", _must_not_run)
        if method == "post":
            resp = client.post(path, json={})
        else:
            resp = client.delete(path)
        assert resp.status_code == 403, resp.text
        assert calls == []

    def test_clear_all_data_with_header_succeeds(self, monkeypatch):
        """合法调用方（同源前端/插件）显式带头 → 正常放行。"""
        monkeypatch.setattr("src.config.clear_local_data", lambda: None)
        monkeypatch.setattr("src.api.server.reset_controller", lambda: None)
        resp = client.post("/api/v1/clear-all-data", headers=AJAX_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_settings_post_with_header_passes(self):
        resp = client.post("/api/v1/settings", headers=AJAX_HEADERS, json={
            "provider": "deepseek", "api_key": "", "base_url": "",
            "model": "", "temperature": 0.7, "theme": "light",
            "accent": "#5b8def", "font_size": 13, "data_dir": "",
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_get_endpoints_stay_open_without_header(self):
        """只读端点不受反 CSRF 头影响（插件 /health 探活路径）。"""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200


class TestCorsWhitelist:
    def test_null_origin_no_longer_allowed(self):
        """P1-18 核心：file:// 沙盒页（Origin: null）的预检必须拿不到放行头。"""
        resp = client.options("/api/v1/clear-all-data", headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.headers.get("access-control-allow-origin") is None

    def test_unknown_web_origin_not_allowed(self):
        resp = client.options("/api/v1/clear-all-data", headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.headers.get("access-control-allow-origin") is None

    def test_whitelisted_origin_preflight_allows_ajax_header(self):
        """白名单来源的合法调用方预检 X-Requested-With 必须放行。"""
        resp = client.options("/api/v1/clear-all-data", headers={
            "Origin": "http://127.0.0.1:8710",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-requested-with",
        })
        assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:8710"
        assert "x-requested-with" in resp.headers.get(
            "access-control-allow-headers", "").lower()


class TestTrustedHost:
    def test_loopback_host_allowed(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_foreign_host_rejected(self):
        """DNS rebinding / 陌生 Host 扫描 → 400。"""
        stranger = TestClient(app, base_url="http://evil.example")
        resp = stranger.get("/api/v1/health")
        assert resp.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
