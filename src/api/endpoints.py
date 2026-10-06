"""
REST API endpoints — thin wrappers around AppController.

Every endpoint delegates to the same AppController methods that
main.py's @eel.expose functions use.  Zero business logic here.

Response convention:  { ok: bool, ...data }
"""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from src.api.models import (
    AssistantRequest,
    BOMFromLCEDARequest,
    BOMImportResponse,
    ChatRequest,
    ChatResponse,
    FileImportRequest,
    ImageRequest,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    LLMConfigRequest,
    LLMConfigResponse,
    VerifySuggestionRequest,
    LLMTestRequest,
    LLMTestResponse,
    OkResponse,
    PCBImportResponse,
    PositionImportResponse,
    ReportResponse,
    ReportWithPathResponse,
    ReviewResponse,
    SettingsRequest,
    StatusResponse,
    SummaryResponse,
    AssistantSaveRequest,
    ConversationSaveRequest,
    MessageSaveRequest,
    ActiveStateRequest,
    DemoLoadResponse,
    ChatStreamRequest,
)
from src.api.server import get_controller
from src.core.controller import AppController
from src.core.persistence import SessionStore
from src.bom.parser import BOMItem
from src.config import SETTINGS_DIR, load_settings, save_settings
from src.constants import get_provider_preset

logger = logging.getLogger(__name__)

router = APIRouter()

# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════


def _bom_item_to_dict(item: BOMItem) -> dict:
    return {
        "reference": item.reference,
        "value": item.value,
        "package": item.package,
        "part_number": item.part_number,
        "description": item.description,
        "quantity": item.quantity,
        "manufacturer": item.manufacturer,
    }


def _bom_items() -> list[dict]:
    ctrl = get_controller()
    return [_bom_item_to_dict(i) for i in ctrl.context.bom_items]


def _write_temp(name: str, b64: str) -> str:
    """Decode base64 content, write to temp dir, return file path."""
    content = base64.b64decode(b64)
    tmp = Path(tempfile.gettempdir()) / "eda_ai_assistant"
    tmp.mkdir(parents=True, exist_ok=True)
    file_path = tmp / name
    file_path.write_bytes(content)
    return str(file_path)


# ═══════════════════════════════════════════════════════════════
#  Health / Status
# ═══════════════════════════════════════════════════════════════


@router.get("/health")
def health_check():
    """Server discovery endpoint — pinged by the LCEDA plugin."""
    return {"status": "ok"}


@router.get("/status", response_model=StatusResponse)
def get_status():
    """Return whether BOM and PCB data are loaded."""
    ctrl = get_controller()
    pcb_info = None
    pcb = ctrl.context.pcb_data
    if pcb:
        pcb_info = {
            "format": pcb.format,
            "net_count": pcb.net_count,
            "trace_count": pcb.trace_count,
            "via_count": pcb.via_count,
            "layers": pcb.layers,
        }
    return StatusResponse(
        ok=True,
        has_bom=ctrl.context.has_data,
        has_pcb=pcb is not None,
        pcb_info=pcb_info,
    )


# ═══════════════════════════════════════════════════════════════
#  File import (base64-encoded)
# ═══════════════════════════════════════════════════════════════


@router.post("/bom/import", response_model=BOMImportResponse)
def import_bom(req: FileImportRequest):
    """Import BOM from a base64-encoded CSV/Excel file."""
    try:
        ctrl = get_controller()
        path = _write_temp(req.filename, req.content_base64)
        count, msg = ctrl.load_bom(path)
        return BOMImportResponse(ok=True, count=count, msg=msg, items=_bom_items())
    except Exception as e:
        return BOMImportResponse(ok=False, msg=str(e))


@router.post("/pos/import", response_model=PositionImportResponse)
def import_positions(req: FileImportRequest):
    """Import Pick & Place positions from a base64-encoded CSV file."""
    try:
        ctrl = get_controller()
        path = _write_temp(req.filename, req.content_base64)
        count, msg = ctrl.load_positions(path)
        return PositionImportResponse(ok=True, count=count, msg=msg)
    except Exception as e:
        return PositionImportResponse(ok=False, msg=str(e))


@router.post("/pcb/import", response_model=PCBImportResponse)
def import_pcb(req: FileImportRequest):
    """Import PCB layout from a base64-encoded JSON/.epro file."""
    try:
        ctrl = get_controller()
        path = _write_temp(req.filename, req.content_base64)
        count, msg = ctrl.load_pcb(path)
        pcb = ctrl.context.pcb_data
        info = None
        if pcb:
            info = {
                "format": pcb.format,
                "net_count": pcb.net_count,
                "trace_count": pcb.trace_count,
                "via_count": pcb.via_count,
                "layers": pcb.layers,
            }
        return PCBImportResponse(ok=True, count=count, msg=msg, pcb=info)
    except Exception as e:
        return PCBImportResponse(ok=False, msg=str(e))


# ═══════════════════════════════════════════════════════════════
#  BOM import from LCEDA (direct — no manual file export)
# ═══════════════════════════════════════════════════════════════


@router.post("/bom/import-from-lceda", response_model=BOMImportResponse)
def import_bom_from_lceda(req: BOMFromLCEDARequest):
    """Import BOM directly from LCEDA plugin — no file export needed.

    The plugin reads BOM data via SCH_ManufactureData.getBomFile(),
    converts to JSON, and sends it here.  We write a temp CSV and
    feed it through the standard load_bom() pipeline.
    """
    import csv

    ctrl = get_controller()
    if not req.components:
        return BOMImportResponse(ok=False, msg="No components provided")

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["位号", "参数", "封装", "型号", "描述", "数量", "制造商"])
            for c in req.components:
                writer.writerow([
                    c.reference,
                    c.value,
                    c.package,
                    c.part_number,
                    c.description,
                    c.quantity,
                    c.manufacturer,
                ])
            temp_path = f.name

        count, msg = ctrl.load_bom(temp_path)
        return BOMImportResponse(ok=True, count=count, msg=msg, items=_bom_items())
    except Exception as e:
        return BOMImportResponse(ok=False, msg=str(e))


# ═══════════════════════════════════════════════════════════════
#  BOM operations
# ═══════════════════════════════════════════════════════════════


@router.post("/bom/merge", response_model=ReportResponse)
def merge_bom():
    """Rule-based BOM merge."""
    ctrl = get_controller()
    try:
        report = ctrl.merge_bom()
        return ReportResponse(ok=True, report=report)
    except Exception as e:
        return ReportResponse(ok=False, report=str(e))


@router.post("/bom/ai-merge", response_model=ReportResponse)
def ai_merge_bom():
    """AI-assisted BOM merge."""
    ctrl = get_controller()
    try:
        report = ctrl.ai_merge_bom()
        return ReportResponse(ok=True, report=report)
    except Exception as e:
        return ReportResponse(ok=False, report=str(e))


@router.post("/bom/validate-packages", response_model=ReportResponse)
def validate_packages():
    """Validate package names against part numbers."""
    ctrl = get_controller()
    report = ctrl.validate_packages()
    return ReportResponse(ok=True, report=report)


@router.post("/bom/check-duplicates", response_model=ReportResponse)
def check_duplicates():
    """Detect duplicate reference designators."""
    ctrl = get_controller()
    report = ctrl.check_duplicates()
    return ReportResponse(ok=True, report=report)


@router.post("/bom/summary", response_model=SummaryResponse)
def bom_summary():
    """Get BOM component count and prefix distribution."""
    ctrl = get_controller()
    try:
        summary = ctrl.get_bom_summary()
        return SummaryResponse(ok=True, summary=summary)
    except Exception as e:
        return SummaryResponse(ok=False)


@router.post("/bom/export-csv", response_model=ReportResponse)
def export_bom_csv():
    """Export BOM as UTF-8-BOM CSV. Returns report + file path."""
    ctrl = get_controller()
    try:
        report = ctrl.export_bom_csv()
        return ReportResponse(ok=True, report=report)
    except Exception as e:
        return ReportResponse(ok=False, report=str(e))


@router.post("/bom/generate-html", response_model=ReportWithPathResponse)
def generate_html_bom():
    """Generate interactive HTML BOM."""
    ctrl = get_controller()
    try:
        report = ctrl.generate_html_bom()
        html_path = Path.cwd() / "output" / "ibom.html"
        path_str = str(html_path) if html_path.exists() else ""
        return ReportWithPathResponse(ok=True, report=report, path=path_str)
    except Exception as e:
        return ReportWithPathResponse(ok=False, report=str(e))


# ═══════════════════════════════════════════════════════════════
#  Design review
# ═══════════════════════════════════════════════════════════════


@router.post("/rules/check", response_model=ReportResponse)
def check_rules():
    """Run 69-rule DRC check."""
    ctrl = get_controller()
    report = ctrl.check_design_rules()
    return ReportResponse(ok=True, report=report)


@router.post("/health/check", response_model=ReportResponse)
def check_bom_health():
    """Check BOM health via LCSC API (stock, lifecycle, alternatives, cost)."""
    ctrl = get_controller()
    report = ctrl.check_bom_health()
    return ReportResponse(ok=True, report=report)


@router.get("/drc/heatmap")
def get_drc_heatmap(grid_size_mm: float = Query(default=5.0)):
    """Generate heatmap data: DRC violations mapped to component positions.

    Returns [[x_bin, y_bin, count], ...] for ECharts heatmap rendering, plus
    ``source`` (``pcb`` / ``positions``) and ``reason`` when nothing can be drawn.
    Empty list if no positions are loaded or no violation maps to a component.
    """
    return get_controller().get_drc_heatmap(grid_size_mm)


@router.post("/verify/suggestion")
def verify_suggestion(body: VerifySuggestionRequest):
    """Closed-loop verification — validate LLM design suggestion against rules engine.

    Request body: { "suggestion": "..." }
    Returns: VerificationReport JSON with rounds, issues, and final status.
    """
    import json
    ctrl = get_controller()
    result = ctrl.verify_suggestion(body.suggestion)
    return json.loads(result)


@router.post("/health/electrical")
def run_electrical_health():
    """Electrical health check using real circuit calculations.

    Covers: impedance, PDN, decoupling, current capacity, thermal, crosstalk.
    No LLM dependency — pure engineering math based on IPC standards.
    """
    import json
    ctrl = get_controller()
    result = ctrl.run_electrical_health_check()
    return json.loads(result)


@router.post("/review/multi-agent", response_model=ReviewResponse)
def review_design_multi_agent():
    """Run 5-agent collaborative review (power, signal, thermal, EMC, DFM).
    Returns raw JSON with radar chart data and agent reports.
    """
    ctrl = get_controller()
    try:
        report = ctrl.review_design_multi_agent()
        return ReviewResponse(ok=True, report=report)
    except Exception as e:
        return ReviewResponse(ok=False, report=str(e))


@router.get("/design-suggestions")
def get_design_suggestions():
    """Design intent recognition — scan BOM for missing components.
    Returns Markdown text.
    """
    ctrl = get_controller()
    try:
        result = ctrl.get_design_suggestions()
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "result": str(e)}


# ═══════════════════════════════════════════════════════════════
#  Chat / AI
# ═══════════════════════════════════════════════════════════════


@router.post("/chat/send", response_model=ChatResponse)
def chat_send(req: ChatRequest):
    """Non-streaming chat via NLU pipeline (process_input)."""
    ctrl = get_controller()
    try:
        result = ctrl.process_input(req.text)
        return ChatResponse(ok=True, result=result)
    except Exception as e:
        return ChatResponse(ok=False, result=str(e))


@router.post("/image/analyze", response_model=ChatResponse)
def analyze_image(req: ImageRequest):
    """Analyze a multimodal image (PCB screenshot, schematic)."""
    ctrl = get_controller()
    try:
        result = ctrl.process_image_input(req.text, req.image_base64)
        return ChatResponse(ok=True, result=result)
    except Exception as e:
        return ChatResponse(ok=False, result=str(e))


@router.post("/chat/clear", response_model=OkResponse)
def clear_chat():
    """Clear conversation history."""
    ctrl = get_controller()
    ctrl.clear_conversation()
    return OkResponse(ok=True)


@router.post("/assistant/set-active", response_model=OkResponse)
def set_active_assistant(req: AssistantRequest):
    """Switch active assistant persona."""
    ctrl = get_controller()
    try:
        ctrl.set_active_assistant(req.assistant_id)
        return OkResponse(ok=True)
    except Exception as e:
        return OkResponse(ok=False, msg=str(e))


# ═══════════════════════════════════════════════════════════════
#  SSE streaming endpoints
# ═══════════════════════════════════════════════════════════════

from src.api.streaming import stream_chat_handler  # noqa: E402


@router.get("/chat/stream")
def chat_stream(text: str = Query(default=""), agent_mode: bool = Query(default=False)):
    """Streaming chat via SSE.

    Query params:
      text:        the user message
      agent_mode:  if true, use agent_loop (Function Calling); else freeform chat
    """
    return stream_chat_handler(text=text, agent_mode=agent_mode)


# ═══════════════════════════════════════════════════════════════
#  LLM configuration
# ═══════════════════════════════════════════════════════════════


@router.get("/llm/config", response_model=LLMConfigResponse)
def get_llm_config():
    """Get current LLM configuration."""
    from src.config import config

    return LLMConfigResponse(
        ok=True,
        provider=config.llm.provider,
        model=config.llm.model,
        is_configured=config.llm.is_configured,
        provider_label=config.llm.provider_label,
    )


@router.post("/llm/config", response_model=OkResponse)
def update_llm_config(req: LLMConfigRequest):
    """Update LLM provider, key, URL, and model. Persisted to settings.json."""
    ctrl = get_controller()
    try:
        ctrl.reconfigure_llm(req.provider, req.api_key, req.base_url, req.model)
        saved = load_settings()
        saved["llm_provider"] = req.provider
        saved["llm_api_key"] = req.api_key
        saved["llm_base_url"] = req.base_url
        saved["llm_model"] = req.model
        save_settings(saved)
        return OkResponse(ok=True)
    except Exception as e:
        return OkResponse(ok=False, msg=str(e))


@router.post("/llm/test")
def test_llm_connection(req: LLMTestRequest):
    """Test LLM connection with a minimal chat request.

    2026-10-06 修复：这里曾 `from openai import OpenAI` 直接建客户端，有两个坑
    （Eel 侧 main.py 同名函数已修，REST 侧漏改）：
      1. `openai` 不在 requirements.txt（干净环境必 ImportError）；
      2. Claude 的 base_url 是原生 Messages API，套给 OpenAI SDK 必 404。
    现在统一走 AppController._create_llm_client()，协议分支只有一处。
    """
    import time

    try:
        preset = get_provider_preset(req.provider)
        url = req.base_url or preset.base_url
        if not url:
            return {"ok": False, "error": "No API base URL configured"}
        if not req.api_key:
            return {"ok": False, "error": "API key required"}

        client = AppController._create_llm_client(
            req.api_key, url, req.model or preset.default_model, preset.name,
        )
        if client is None:
            return {"ok": False, "error": "无法创建客户端"}

        start = time.time()
        reply = client.chat("Hi", max_tokens=5, temperature=0)
        latency = round((time.time() - start) * 1000)
        return {
            "ok": True,
            "latency": latency,
            "model_used": getattr(client, "model", req.model),
            "protocol": preset.protocol,
            "reply_preview": (reply or "")[:40],
        }
    except Exception as e:
        msg = str(e)
        if len(msg) > 200:
            msg = msg[:200] + "..."
        return {"ok": False, "error": msg}


# ═══════════════════════════════════════════════════════════════
#  Settings
# ═══════════════════════════════════════════════════════════════


@router.get("/settings")
def get_settings():
    """Read all persisted settings."""
    saved = load_settings()
    return {
        "ok": True,
        "provider": saved.get("llm_provider", "deepseek"),
        "api_key": saved.get("llm_api_key", ""),
        "base_url": saved.get("llm_base_url", ""),
        "model": saved.get("llm_model", ""),
        "temperature": saved.get("llm_temperature", 0.7),
        "theme": saved.get("selected_theme", "light"),
        "accent": saved.get("selected_accent", "#5b8def"),
        "font_size": saved.get("font_size", 13),
        "data_dir": str(SETTINGS_DIR),
    }


@router.post("/settings", response_model=OkResponse)
def save_all_settings(req: SettingsRequest):
    """Save all settings and reconfigure LLM."""
    ctrl = get_controller()
    try:
        ctrl.reconfigure_llm(req.provider, req.api_key, req.base_url, req.model)
        saved = load_settings()
        saved["llm_provider"] = req.provider
        saved["llm_api_key"] = req.api_key
        saved["llm_base_url"] = req.base_url
        saved["llm_model"] = req.model
        saved["llm_temperature"] = req.temperature
        saved["selected_theme"] = req.theme
        saved["selected_accent"] = req.accent
        save_settings(saved)
        return OkResponse(ok=True)
    except Exception as e:
        return OkResponse(ok=False, msg=str(e))


@router.post("/clear-all-data", response_model=OkResponse)
def clear_all_data():
    """Remove all local settings and database."""
    import shutil

    try:
        if SETTINGS_DIR.exists():
            shutil.rmtree(str(SETTINGS_DIR))
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        return OkResponse(ok=True)
    except Exception as e:
        return OkResponse(ok=False, msg=str(e))


@router.post("/knowledge/query", response_model=KnowledgeQueryResponse)
def knowledge_query(req: KnowledgeQueryRequest):
    """查询 RAG 知识库 — 获取 IPC 标准、高速设计、SI/PI、EMC 等专业工程知识。

    查询 PCB 设计知识库，返回语义匹配的专业文档片段。
    """
    ctrl = get_controller()
    try:
        result = ctrl.query_knowledge_base(req.query)

        # 同时获取结构化来源用于前端展示
        sources: list[dict] = []
        try:
            from src.rag.retriever import RAGRetriever
            retriever = RAGRetriever()
            raw = retriever.query(req.query, top_k=req.top_k)
            sources = [
                {
                    "title": r["title"],
                    "content": r["content"][:200] + ("..." if len(r["content"]) > 200 else ""),
                    "score": r["score"],
                    "source": r.get("source", ""),
                }
                for r in raw
            ]
        except Exception:
            pass  # 结构化来源非必须，降级为空列表

        return KnowledgeQueryResponse(ok=True, result=result, sources=sources)
    except Exception as e:
        return KnowledgeQueryResponse(ok=False, result=str(e), sources=[])


# ═══════════════════════════════════════════════════════════════
#  Persistence (SQLite session store) — thin wrappers over SessionStore
# ═══════════════════════════════════════════════════════════════

_store: "SessionStore | None" = None


def _get_store() -> SessionStore:
    """惰性单例：不要在 import 时打开数据库。

    模块级 SessionStore() 会在「导入 src.api.endpoints」这一步就去创建
    ~/.eda_ai_assistant/sessions.db（含 WAL 文件），只读/受限环境下 import
    直接失败，把整包测试的收集都拖垮。改成首次用时才建。
    """
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


@router.get("/persist/load-all")
def persist_load_all():
    """Startup snapshot: assistants, conversations, active state."""
    try:
        return {"ok": True, "data": _get_store().load_all()}
    except Exception as e:
        logger.exception("persist_load_all failed")
        return {"ok": False, "msg": str(e)}


@router.post("/persist/assistant")
def persist_save_assistant(req: AssistantSaveRequest):
    try:
        _get_store().save_assistant(req.instance_id, req.type_id, req.name, req.sort_order)
        _get_store().save_state("active_assistant", req.instance_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.delete("/persist/assistant/{instance_id}")
def persist_delete_assistant(instance_id: str):
    try:
        _get_store().delete_assistant(instance_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.post("/persist/conversation")
def persist_save_conversation(req: ConversationSaveRequest):
    try:
        _get_store().save_conversation(req.conv_id, req.instance_id, req.title,
                                workspace_id=req.workspace_id)
        _get_store().save_state("active_conv", req.conv_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.delete("/persist/conversation/{conv_id}")
def persist_delete_conversation(conv_id: str):
    try:
        _get_store().delete_conversation(conv_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.post("/persist/message")
def persist_save_message(req: MessageSaveRequest):
    try:
        _get_store().save_message(req.conv_id, req.role, req.content, req.image or None, req.seq)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.get("/persist/messages/{conv_id}")
def persist_load_messages(conv_id: str):
    try:
        messages = _get_store().load_messages(conv_id)
        return {
            "ok": True,
            "messages": [
                {"role": m.role, "content": m.content, "image": m.image or ""}
                for m in messages
            ],
        }
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.post("/persist/active-state")
def persist_save_active_state(req: ActiveStateRequest):
    try:
        if req.active_assistant:
            _get_store().save_state("active_assistant", req.active_assistant)
        if req.active_conv:
            _get_store().save_state("active_conv", req.active_conv)
        if req.active_workspace:
            _get_store().save_state("active_workspace", req.active_workspace)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ═══════════════════════════════════════════════════════════════
#  Demo data
# ═══════════════════════════════════════════════════════════════


@router.post("/demo/load", response_model=DemoLoadResponse)
def load_demo():
    """一键演示：加载内置示例数据（有缺陷的 MCU 板 BOM + 坐标）。"""
    ctrl = get_controller()
    project_root = Path(__file__).parent.parent.parent
    bom_path = project_root / "tests" / "sample_bom_bad.csv"
    pos_path = project_root / "tests" / "sample_positions.csv"
    try:
        count, msg = ctrl.load_bom(str(bom_path))
        pos_count = 0
        if pos_path.exists():
            pos_count, _ = ctrl.load_positions(str(pos_path))
        return DemoLoadResponse(
            ok=True, count=count, pos_count=pos_count, msg=msg, items=_bom_items(),
        )
    except Exception as e:
        return DemoLoadResponse(ok=False, msg=str(e))


# ═══════════════════════════════════════════════════════════════
#  Chat streaming (POST body variant — cleaner for long Chinese prompts)
# ═══════════════════════════════════════════════════════════════


@router.post("/chat/stream")
def chat_stream_post(req: ChatStreamRequest):
    return stream_chat_handler(text=req.text, agent_mode=req.agent_mode)
