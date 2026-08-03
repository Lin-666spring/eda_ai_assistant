"""
Pydantic request / response models for the REST API.

Every response follows the pattern  { ok: bool, ...data }
to match the existing main.py Eel endpoint convention exactly.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
#  Generic wrappers
# ═══════════════════════════════════════════════════════════════


class OkResponse(BaseModel):
    ok: bool = True


class DataResponse(BaseModel):
    ok: bool = True
    data: Any = None


class ErrorResponse(BaseModel):
    ok: bool = False
    msg: str = ""


# ═══════════════════════════════════════════════════════════════
#  File import
# ═══════════════════════════════════════════════════════════════


class FileImportRequest(BaseModel):
    filename: str
    content_base64: str  # base64-encoded file bytes


class BOMImportResponse(BaseModel):
    ok: bool = True
    count: int = 0
    msg: str = ""
    items: list[dict[str, Any]] = []


class PCBImportResponse(BaseModel):
    ok: bool = True
    count: int = 0
    msg: str = ""
    pcb: Optional[dict[str, Any]] = None


class PositionImportResponse(BaseModel):
    ok: bool = True
    count: int = 0
    msg: str = ""


# ═══════════════════════════════════════════════════════════════
#  BOM import from LCEDA (direct, no file export)
# ═══════════════════════════════════════════════════════════════


class LCEDAComponentItem(BaseModel):
    reference: str = ""
    value: str = ""
    package: str = ""
    part_number: str = ""
    description: str = ""
    quantity: int = 1
    manufacturer: str = ""


class BOMFromLCEDARequest(BaseModel):
    components: list[LCEDAComponentItem] = []


# ═══════════════════════════════════════════════════════════════
#  Report responses (most BOM / rule / review operations)
# ═══════════════════════════════════════════════════════════════


class ReportResponse(BaseModel):
    ok: bool = True
    report: str = ""


class ReportWithPathResponse(BaseModel):
    ok: bool = True
    report: str = ""
    path: str = ""


class ReviewResponse(BaseModel):
    ok: bool = True
    report: str = ""  # JSON string from multi-agent review


# ═══════════════════════════════════════════════════════════════
#  Chat / AI
# ═══════════════════════════════════════════════════════════════


class ChatRequest(BaseModel):
    text: str


class ImageRequest(BaseModel):
    text: str = ""
    image_base64: str


class ChatResponse(BaseModel):
    ok: bool = True
    result: str = ""


class AssistantRequest(BaseModel):
    assistant_id: str


# ═══════════════════════════════════════════════════════════════
#  LLM configuration
# ═══════════════════════════════════════════════════════════════


class LLMConfigRequest(BaseModel):
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class LLMConfigResponse(BaseModel):
    ok: bool = True
    provider: str = ""
    model: str = ""
    is_configured: bool = False
    provider_label: str = ""


class LLMTestRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str = ""
    model: str = ""


class LLMTestResponse(BaseModel):
    ok: bool = True
    latency: float = 0.0
    model_used: str = ""
    error: str = ""


# ═══════════════════════════════════════════════════════════════
#  Settings
# ═══════════════════════════════════════════════════════════════


class SettingsRequest(BaseModel):
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.7
    theme: str = "dark"
    accent: str = "#4A90D9"
    font_size: int = 14
    data_dir: str = ""


# ═══════════════════════════════════════════════════════════════
#  Status
# ═══════════════════════════════════════════════════════════════


class StatusResponse(BaseModel):
    ok: bool = True
    has_bom: bool = False
    has_pcb: bool = False
    pcb_info: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    status: str = "ok"


class SummaryResponse(BaseModel):
    ok: bool = True
    summary: dict[str, Any] = {}


class VerifySuggestionRequest(BaseModel):
    suggestion: str = ""


class KnowledgeQueryRequest(BaseModel):
    query: str = ""
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeQueryResponse(BaseModel):
    ok: bool = True
    result: str = ""
    sources: list[dict[str, Any]] = []
