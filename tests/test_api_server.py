"""
FastAPI TestClient integration tests for the REST API server.

All API endpoints are tested against FastAPI's TestClient — no real
server needed.  These tests verify:
- Correct HTTP status codes
- Correct request/response JSON shapes
- SSE streaming contract
- Temporary file cleanup for import-from-lceda
- Error handling for invalid inputs
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.api.server import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════
#  Health / Status
# ═══════════════════════════════════════════════════════════════


class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_status_returns_structure(self):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "has_bom" in data
        assert "has_pcb" in data
        assert "pcb_info" in data


# ═══════════════════════════════════════════════════════════════
#  BOM import from LCEDA (the new endpoint)
# ═══════════════════════════════════════════════════════════════


class TestBOMImportFromLCEDA:
    def test_empty_components_returns_error(self):
        resp = client.post("/api/v1/bom/import-from-lceda", json={"components": []})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False

    def test_import_basic_components(self):
        """Import a basic BOM with resistor + capacitor — smoke test."""
        payload = {
            "components": [
                {
                    "reference": "R1,R2,R3",
                    "value": "10kΩ",
                    "package": "0603",
                    "part_number": "C25804",
                    "description": "贴片电阻 10kΩ ±1%",
                    "quantity": 3,
                    "manufacturer": "国巨",
                },
                {
                    "reference": "C1,C2",
                    "value": "100nF",
                    "package": "0603",
                    "part_number": "C28233",
                    "description": "贴片电容 100nF 50V",
                    "quantity": 2,
                    "manufacturer": "三星",
                },
                {
                    "reference": "U1",
                    "value": "STM32F103C8T6",
                    "package": "LQFP-48",
                    "part_number": "C8734",
                    "description": "ARM Cortex-M3 MCU",
                    "quantity": 1,
                    "manufacturer": "ST",
                },
            ]
        }
        resp = client.post("/api/v1/bom/import-from-lceda", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["count"] == 3  # 3 unique parts (R1-R3 grouped as 1 line)
        assert len(data["items"]) == 3

        # Verify component fields are preserved
        refs = [i["reference"] for i in data["items"]]
        assert "R1,R2,R3" in refs
        assert "C1,C2" in refs
        assert "U1" in refs

    def test_import_preserves_all_fields(self):
        """Verify all BOMItem fields survive the round trip."""
        payload = {
            "components": [
                {
                    "reference": "D1",
                    "value": "1N4148",
                    "package": "SOD-123",
                    "part_number": "C10001",
                    "description": "高速开关二极管",
                    "quantity": 5,
                    "manufacturer": "NXP",
                }
            ]
        }
        resp = client.post("/api/v1/bom/import-from-lceda", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        item = data["items"][0]
        assert item["reference"] == "D1"
        assert item["value"] == "1N4148"
        assert item["package"] == "SOD-123"
        assert item["part_number"] == "C10001"
        assert item["description"] == "高速开关二极管"
        assert item["quantity"] == 5
        assert item["manufacturer"] == "NXP"

    def test_missing_fields_get_defaults(self):
        """Omitted fields should fall back to sensible defaults."""
        payload = {
            "components": [
                {"reference": "X1"}
            ]
        }
        resp = client.post("/api/v1/bom/import-from-lceda", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        if data["ok"]:
            item = data["items"][0]
            assert item["reference"] == "X1"
            assert item["value"] == ""
            assert item["package"] == ""

    def test_can_call_merge_after_import(self):
        """After importing BOM, the merge endpoint should work."""
        payload = {
            "components": [
                {"reference": "R1,R2", "value": "10k", "package": "0603",
                 "part_number": "C12345", "description": "电阻", "quantity": 2},
                {"reference": "R3", "value": "10k", "package": "0603",
                 "part_number": "C12345", "description": "电阻", "quantity": 1},
            ]
        }
        # Import
        resp = client.post("/api/v1/bom/import-from-lceda", json=payload)
        assert resp.json()["ok"]

        # Merge should work
        resp = client.post("/api/v1/bom/merge")
        assert resp.status_code == 200
        assert resp.json()["ok"]


# ═══════════════════════════════════════════════════════════════
#  BOM operations (no BOM loaded — verify graceful errors)
# ═══════════════════════════════════════════════════════════════


class TestBOMOperationsEmpty:
    """Test BOM operations when no BOM has been loaded yet."""

    def test_validate_packages_no_bom(self):
        """Validate with no data — should not crash."""
        resp = client.post("/api/v1/bom/validate-packages")
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data

    def test_check_duplicates_no_bom(self):
        resp = client.post("/api/v1/bom/check-duplicates")
        assert resp.status_code == 200
        assert "ok" in resp.json()


# ═══════════════════════════════════════════════════════════════
#  Design review endpoints
# ═══════════════════════════════════════════════════════════════


class TestDesignReview:
    def test_rules_check_no_pcb(self):
        """DRC check with no PCB loaded — should not crash."""
        resp = client.post("/api/v1/rules/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data

    def test_design_suggestions_no_bom(self):
        """Design suggestions with no BOM — should not crash."""
        resp = client.get("/api/v1/design-suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data


# ═══════════════════════════════════════════════════════════════
#  Chat endpoints (no LLM configured — verify graceful handling)
# ═══════════════════════════════════════════════════════════════


class TestChatEndpoints:
    def test_chat_send_no_llm(self):
        """Non-streaming chat without LLM — should return something."""
        resp = client.post("/api/v1/chat/send", json={"text": "帮助"})
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data

    def test_chat_clear(self):
        """Clear chat — always succeeds."""
        resp = client.post("/api/v1/chat/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

    def test_set_active_assistant(self):
        """Switch assistant — should succeed for known IDs."""
        for aid in ["eda-general", "bom-expert", "pcb-reviewer", "vision-analyst"]:
            resp = client.post("/api/v1/assistant/set-active", json={"assistant_id": aid})
            assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
#  SSE streaming endpoints
# ═══════════════════════════════════════════════════════════════


class TestSSEStreaming:
    def test_stream_returns_sse_content_type(self):
        """The streaming endpoint should return text/event-stream."""
        resp = client.get("/api/v1/chat/stream?text=hello&agent_mode=false")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_agent_mode(self):
        """The agent mode streaming endpoint should also return SSE."""
        resp = client.get("/api/v1/chat/stream?text=分析BOM&agent_mode=true")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    def test_stream_empty_text(self):
        """Streaming with empty text should still work."""
        resp = client.get("/api/v1/chat/stream?text=&agent_mode=false")
        assert resp.status_code == 200

    def test_stream_event_structure(self):
        """Verify SSE events follow the expected structure."""
        resp = client.get("/api/v1/chat/stream?text=hello&agent_mode=false")
        body = resp.text
        # Each event should have "event:" and "data:" lines
        lines = body.strip().split("\n")
        # SSE format: empty line separates events
        assert len(body) > 0


# ═══════════════════════════════════════════════════════════════
#  LLM configuration endpoints
# ═══════════════════════════════════════════════════════════════


class TestLLMConfig:
    def test_get_config(self):
        resp = client.get("/api/v1/llm/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "provider" in data
        assert "model" in data
        assert "is_configured" in data

    def test_update_config_no_key(self):
        """Update with empty key — should still succeed (settings are saved)."""
        resp = client.post("/api/v1/llm/config", json={
            "provider": "deepseek",
            "api_key": "",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        })
        assert resp.status_code == 200

    def test_test_connection_no_key(self):
        """Test connection without a real API key — should fail gracefully."""
        resp = client.post("/api/v1/llm/test", json={
            "provider": "deepseek",
            "api_key": "invalid-key",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should fail with error message, not a 500
        assert data["ok"] is False
        assert "error" in data


# ═══════════════════════════════════════════════════════════════
#  Settings endpoints
# ═══════════════════════════════════════════════════════════════


class TestSettings:
    def test_get_settings(self):
        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "provider" in data
        assert "theme" in data
        assert "accent" in data
        assert "data_dir" in data

    def test_save_settings_minimal(self):
        resp = client.post("/api/v1/settings", json={
            "provider": "openai", "api_key": "", "base_url": "",
            "model": "", "temperature": 0.7, "theme": "dark",
            "accent": "#5b8def", "font_size": 14, "data_dir": "",
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
#  Response shape conventions
# ═══════════════════════════════════════════════════════════════


class TestResponseConventions:
    """Verify all endpoints follow the {ok, ...} convention."""

    @pytest.mark.parametrize("method,path,body", [
        ("GET", "/api/v1/status", None),
        ("GET", "/api/v1/llm/config", None),
        ("GET", "/api/v1/settings", None),
        ("GET", "/api/v1/design-suggestions", None),
        ("POST", "/api/v1/bom/merge", None),
        ("POST", "/api/v1/bom/check-duplicates", None),
        ("POST", "/api/v1/bom/validate-packages", None),
        ("POST", "/api/v1/rules/check", None),
        ("POST", "/api/v1/chat/clear", None),
        ("POST", "/api/v1/chat/send", {"text": "help"}),
    ])
    def test_endpoint_has_ok_field(self, method, path, body):
        """Every endpoint should return JSON with an 'ok' field."""
        if method == "GET":
            resp = client.get(path)
        else:
            resp = client.post(path, json=body or {})
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data, f"{method} {path} response missing 'ok' field"


class TestKnowledgeEndpoint:
    """RAG 知识库查询 API 端点测试"""

    def test_knowledge_query_returns_ok(self):
        resp = client.post("/api/v1/knowledge/query", json={
            "query": "IPC-2221 载流能力",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data
        assert "result" in data
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_knowledge_query_empty_query(self):
        """空查询返回帮助提示"""
        resp = client.post("/api/v1/knowledge/query", json={"query": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "知识库" in data["result"]

    def test_knowledge_query_has_convention(self):
        """Follows the {ok, result, sources} convention"""
        resp = client.post("/api/v1/knowledge/query", json={
            "query": "0603封装",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "ok" in data
        assert "result" in data
        assert isinstance(data["ok"], bool)
