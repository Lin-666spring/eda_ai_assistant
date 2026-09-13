# -*- coding: utf-8 -*-
"""模型目录 — 直接问厂商「你现在有哪些模型」。

为什么需要它：`LLM_PROVIDER_PRESETS.models` 是手写的兜底清单，厂商一发新版
就过时（2026-09 核对时发现 deepseek-v4-flash 已退役、gpt-5.5 已被 GPT-5.6
取代、claude-opus-4-8 归入 Legacy）。与其追着发版更新常量，不如运行时调
厂商自己的 `GET /models` 拿权威列表。

两家协议：
- OpenAI 兼容（DeepSeek / OpenAI / Qwen / GLM / Kimi / 豆包 / MiniMax /
  硅基流动 / Gemini 的 OpenAI 端点）: `GET {base_url}/models`
  header: `Authorization: Bearer <key>`
- Anthropic 原生 Messages API: `GET https://api.anthropic.com/v1/models`
  header: `x-api-key` + `anthropic-version`

两条路径都只读、免费（不消耗 token）。
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from ..constants import ProviderPreset, get_provider_preset

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT = 15

# 明显不是对话模型的条目（嵌入/语音/图像/审核/重排），从可选项里剔掉
_NON_CHAT_MARKERS = (
    "embedding", "embed", "rerank", "tts", "whisper", "audio", "speech",
    "moderation", "dall-e", "image-", "-image", "vision-exp", "ocr",
    "stable-diffusion", "flux", "bge-", "clip", "codex-mini",
)


def _is_chat_model(model_id: str) -> bool:
    lowered = model_id.lower()
    return not any(marker in lowered for marker in _NON_CHAT_MARKERS)


def models_endpoint(preset: ProviderPreset, base_url: str = "") -> str:
    """推导模型列表端点。

    Anthropic 预设的 base_url 指向 `.../v1/messages`，列表在同级 `/v1/models`；
    其余厂商直接用 `{base_url}/models`。
    """
    url = (base_url or preset.base_url or "").rstrip("/")
    if preset.protocol == "anthropic":
        if url.endswith("/messages"):
            url = url[: -len("/messages")]
        return f"{url}/models"
    return f"{url}/models"


def _headers(preset: ProviderPreset, api_key: str) -> dict:
    if preset.protocol == "anthropic":
        return {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _extract_ids(payload: object) -> list[str]:
    """从各家五花八门的响应里抠出模型 id 列表。

    兼容三种常见形态：
      {"data": [{"id": "..."}]}          OpenAI / Anthropic / 智谱 / Kimi
      {"models": [{"name": "..."}]}      少数网关
      {"data": ["模型名", ...]}           更简化的实现
    """
    if not isinstance(payload, dict):
        return []
    raw = payload.get("data")
    if raw is None:
        raw = payload.get("models")
    if not isinstance(raw, list):
        return []

    ids: list[str] = []
    for item in raw:
        if isinstance(item, str):
            ids.append(item)
        elif isinstance(item, dict):
            mid = item.get("id") or item.get("name") or item.get("model")
            if isinstance(mid, str) and mid:
                ids.append(mid)
    # 去重且保持原顺序
    seen: set[str] = set()
    return [m for m in ids if not (m in seen or seen.add(m))]


def list_models(
    provider: Optional[str],
    api_key: str,
    base_url: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """实时拉取某厂商可用的模型列表。

    Returns:
        {"ok": True, "provider": ..., "models": [...], "count": N}
        {"ok": False, "provider": ..., "error": "...", "models": []}
    """
    preset = get_provider_preset(provider)
    if not api_key:
        return {"ok": False, "provider": preset.name, "models": [],
                "error": "未配置 API Key，无法拉取模型列表"}

    url = models_endpoint(preset, base_url)
    if not url.startswith("http"):
        return {"ok": False, "provider": preset.name, "models": [],
                "error": f"API 地址无效: {url or '(空)'}"}

    try:
        resp = requests.get(url, headers=_headers(preset, api_key), timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except requests.HTTPError as e:
        detail = ""
        try:
            detail = (e.response.text or "")[:200]
        except Exception:  # pragma: no cover - 响应体不可读
            pass
        logger.warning("list_models HTTP error %s: %s %s", url, e, detail)
        return {"ok": False, "provider": preset.name, "models": [],
                "error": _friendly_http_error(e, preset)}
    except ValueError as e:
        # ⚠️ 必须排在 RequestException 之前：requests 的 JSONDecodeError
        #    同时继承 RequestException 和 ValueError，放在后面会被误报成「无法连接」。
        return {"ok": False, "provider": preset.name, "models": [],
                "error": f"响应不是合法 JSON：{e}"}
    except requests.RequestException as e:
        logger.warning("list_models request failed %s: %s", url, e)
        return {"ok": False, "provider": preset.name, "models": [],
                "error": f"无法连接 {url}：{e}"}

    ids = [m for m in _extract_ids(payload) if _is_chat_model(m)]
    if not ids:
        return {"ok": False, "provider": preset.name, "models": [],
                "error": "厂商返回了空的模型列表"}

    # 默认模型排最前，其余保持厂商顺序
    default = preset.default_model
    if default in ids:
        ids = [default] + [m for m in ids if m != default]

    return {"ok": True, "provider": preset.name, "models": ids, "count": len(ids),
            "endpoint": url}


def _friendly_http_error(error: requests.HTTPError, preset: ProviderPreset) -> str:
    status = getattr(error.response, "status_code", None)
    if status == 401:
        return f"API Key 无效或已过期（401）— 可在 {preset.key_url or '厂商控制台'} 重新生成"
    if status == 403:
        return "API Key 无权访问该厂商（403）"
    if status == 404:
        return "模型列表端点不存在（404）— 该厂商可能不支持 GET /models，请手动填写模型名"
    if status == 429:
        return "请求过于频繁（429），稍后再试"
    return f"拉取失败（HTTP {status}）"


def fallback_models(provider: Optional[str]) -> list[str]:
    """离线兜底清单：预设里手写的 models，加上 default_model 保证非空。"""
    preset = get_provider_preset(provider)
    models = list(preset.models)
    if preset.default_model and preset.default_model not in models:
        models.insert(0, preset.default_model)
    return models
