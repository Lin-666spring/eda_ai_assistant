"""
Anthropic Claude 原生 API 客户端 — Messages API

Anthropic 使用自己的 Messages API 格式，不是 OpenAI 兼容的。
本模块封装了 Anthropic 原生协议，对外提供与 LLMClient 统一的方法签名。

Anthropic Messages API 文档: https://docs.anthropic.com/en/api/messages

关键差异:
- Endpoint: POST /v1/messages
- Auth: x-api-key header
- Version: anthropic-version: 2023-06-01
- system 是顶层字段，不是 message role
- content 是 content_block 数组
- 流式使用 SSE，事件格式不同
- Tool use 使用 content block 而非 OpenAI tool_calls 格式
"""

import json
import logging
import threading
import time
from typing import Optional, Callable

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"

# P1-2（验收 2026-10-24）：429/5xx 是瞬态失败（限流/网关抖动），一次失败就断掉
# 整轮对话不可接受 —— 退避 1.5s/4s 重试至多 2 次；4xx 参数类错误重试无意义。
# 口径对齐 llm_client._open 的同款常量。
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRY_DELAYS = (1.5, 4.0)


class AnthropicClient:
    """Claude Messages API 客户端 — 与 LLMClient 保持统一接口"""

    HISTORY_MAX_TURNS = 20

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tool_executor: Optional[Callable[[str, dict], str]] = None,
    ):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")
        if not self.base_url.endswith("/messages"):
            self.base_url += "/messages"
        self.model = model or "claude-opus-4-8"
        self.provider_name = provider or "claude"
        self.tool_executor = tool_executor
        self._history: list[dict] = []
        # P1-2（验收 2026-10-24）：_history 并发保护 —— 会话租借场景下多线程
        # 共享同一客户端实例，历史读写需互斥（对齐 llm_client._history_lock）。
        self._history_lock = threading.Lock()

    @property
    def provider_label(self) -> str:
        return self.provider_name

    # ── Headers ──

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    # ══════════════════════════════════════════
    #  公开方法 — 与 LLMClient 统一签名
    # ══════════════════════════════════════════

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        use_history: bool = False,
    ) -> str:
        messages = self._build_messages(user_message, use_history)
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = self._api_call(payload)
        reply = self._extract_text(resp)
        self._record_turn(user_message, reply)
        return reply

    def chat_stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
        use_history: bool = False,
    ) -> str:
        messages = self._build_messages(user_message, use_history)
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": 0.7,
            "messages": messages,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        reply = self._api_stream(payload, on_token)
        self._record_turn(user_message, reply)
        return reply

    def chat_multimodal(
        self,
        user_message: str,
        image_b64: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        # Claude 的图片格式
        if not image_b64.startswith("data:"):
            image_b64 = f"data:image/png;base64,{image_b64}"

        # 解析 media_type 和 base64 data
        if image_b64.startswith("data:"):
            header, data = image_b64.split(",", 1)
            media_type = header.split(":")[1].split(";")[0]
        else:
            media_type = "image/png"
            data = image_b64

        content = [
            {"type": "text", "text": user_message},
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": data,
                },
            },
        ]

        messages = [{"role": "user", "content": content}]
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = self._api_call(payload)
        reply = self._extract_text(resp)
        self._record_turn(user_message, reply)
        return reply

    def chat_with_tools(
        self,
        user_message: str,
        functions: list[dict],
        system_prompt: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
        use_history: bool = False,
        max_iterations: int = 5,
    ) -> str:
        """多轮 Tool Use Agent Loop (Anthropic 原生格式)

        Anthropic 的 tool use 与 OpenAI function calling 有格式差异:
        - tools 数组直接放顶层，不需要 {"type": "function", "function": {...}} 嵌套
        - LLM 返回 content 中包含 type='tool_use' 的 block
        - 用户必须返回 type='tool_result' 的 block
        """
        # 转换 OpenAI function definitions → Anthropic tool format
        tools = self._convert_functions_to_tools(functions)
        messages = self._build_messages(user_message, use_history)

        last_results: list[str] = []
        resp: Optional[dict] = None
        for _ in range(max_iterations):
            payload = {
                "model": self.model,
                "max_tokens": 4096,
                "temperature": 0.7,
                "messages": messages,
                "stream": False,
            }
            if system_prompt:
                payload["system"] = system_prompt
            if tools:
                payload["tools"] = tools

            resp = self._api_call(payload)
            stop_reason = resp.get("stop_reason", "")

            # 检查是否需要调用工具
            if stop_reason == "tool_use":
                # 解析 tool_use blocks
                tool_blocks = [b for b in resp.get("content", []) if b.get("type") == "tool_use"]
                if not tool_blocks:
                    break

                # 将 assistant 消息（含 tool_use blocks）加入历史
                messages.append({"role": "assistant", "content": resp["content"]})

                # 执行每个 tool call
                tool_results = []
                for tb in tool_blocks:
                    tool_name = tb.get("name", "")
                    tool_input = tb.get("input", {})
                    tool_id = tb.get("id", "")

                    # P1-1（验收 2026-10-24）：单个工具异常不能终止整个 Agent
                    # Loop —— 对齐 llm_client.chat_with_tools 的口径，把错误
                    # 文本作为 tool_result 回传，让 LLM 自行消化后继续推理。
                    try:
                        if self.tool_executor:
                            result_text = self.tool_executor(tool_name, tool_input)
                        else:
                            result_text = json.dumps({"error": "no tool executor"}, ensure_ascii=False)
                    except Exception as exc:
                        result_text = f"工具执行失败: {exc}"
                        logger.error("Tool %s failed: %s", tool_name, exc)

                    last_results.append(f"[{tool_name}] {result_text}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_text,
                    })

                # 将 tool_result 加入消息
                messages.append({"role": "user", "content": tool_results})
                continue  # 回到循环顶部，让 LLM 消化工具结果

            # end_turn / stop 或其他 — LLM 给出最终回复
            reply = self._extract_text(resp)
            self._record_turn(user_message, reply)
            return reply

        # P1-2（验收 2026-10-24）：迭代耗尽不能返回空串 —— stop_reason 仍为
        # tool_use 时 extract_text 得到 ""，调用方无从得知 Agent 做到了哪一步。
        # 对齐 llm_client 同场景：优先返回最后一轮的文本，没有文本则返回
        # 已执行操作的摘要，并把摘要记入历史。
        final_text = self._extract_text(resp) if resp is not None else ""
        if final_text:
            self._record_turn(user_message, final_text)
            return final_text
        logger.warning(
            "Anthropic agent loop hit max_iterations=%d after %d tool calls",
            max_iterations, len(last_results),
        )
        summary = "已达到最大操作步数限制。以下是我已完成的操作：\n\n"
        summary += "\n".join(f"{i}. {r}" for i, r in enumerate(last_results, 1))
        self._record_turn(user_message, summary)
        return summary

    def function_call(
        self,
        user_message: str,
        functions: list[dict],
        system_prompt: Optional[str] = None,
    ) -> dict:
        """单次 Function/Tool Calling"""
        tools = self._convert_functions_to_tools(functions)
        messages = [{"role": "user", "content": user_message}]
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0,
            "messages": messages,
            "tools": tools,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        resp = self._api_call(payload)
        tool_blocks = [b for b in resp.get("content", []) if b.get("type") == "tool_use"]
        if tool_blocks:
            tb = tool_blocks[0]
            return {"name": tb.get("name", ""), "arguments": tb.get("input", {})}
        return {"name": "", "arguments": {}}

    def clear_history(self):
        with self._history_lock:
            self._history = []

    def get_history(self) -> list[dict]:
        with self._history_lock:
            return self._history.copy()

    def seed_history(self, turns: list[dict]) -> None:
        """用给定轮次替换本客户端历史（会话租借：继承共享历史快照）"""
        with self._history_lock:
            self._history = list(turns)

    def extend_history(self, turns: list[dict]) -> None:
        """追加轮次（会话租借：把本次会话的新增轮次合并回共享历史）"""
        with self._history_lock:
            self._history.extend(turns)

    def list_models(self) -> dict:
        """实时拉取 Anthropic 可用模型（GET /v1/models，只读免费）。

        注意 self.base_url 指向 `.../v1/messages`，列表端点是同级 `/v1/models`，
        由 model_catalog.models_endpoint() 负责推导。
        """
        from .model_catalog import list_models as _list_models
        return _list_models(self.provider_name, self.api_key, self.base_url)

    # ══════════════════════════════════════════
    #  内部方法
    # ══════════════════════════════════════════

    def _build_messages(self, user_message: str, use_history: bool = False) -> list[dict]:
        messages = []
        if use_history:
            with self._history_lock:
                messages.extend(self._history[-self.HISTORY_MAX_TURNS * 2:])
        messages.append({"role": "user", "content": user_message})
        return messages

    def _record_turn(self, user_msg: str, reply: str):
        with self._history_lock:
            self._history.append({"role": "user", "content": user_msg})
            self._history.append({"role": "assistant", "content": reply})
            if len(self._history) > self.HISTORY_MAX_TURNS * 2:
                self._history = self._history[-self.HISTORY_MAX_TURNS * 2:]

    def _api_call(self, payload: dict) -> dict:
        """调用 Anthropic Messages API (非流式)"""
        try:
            r = self._post_with_retry(payload, timeout=120)
            return r.json()
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = e.response.text[:500]
            except Exception:
                pass
            logger.error("Anthropic API error: %s — %s", e, detail)
            raise

    def _post_with_retry(self, payload: dict, timeout: int, stream: bool = False):
        """POST 请求，429/5xx 按 _RETRY_DELAYS 退避重试（P1-2，对齐 llm_client）"""
        for attempt in range(len(_RETRY_DELAYS) + 1):
            try:
                r = requests.post(
                    self.base_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=timeout,
                    stream=stream,
                )
                r.raise_for_status()
                return r
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                if status in _RETRYABLE_STATUS and attempt < len(_RETRY_DELAYS):
                    logger.warning(
                        "Anthropic API %s（第 %d 次失败），%.1fs 后重试: %s",
                        self.base_url, attempt + 1, _RETRY_DELAYS[attempt], status,
                    )
                    time.sleep(_RETRY_DELAYS[attempt])
                    continue
                raise

    def _api_stream(
        self, payload: dict, on_token: Optional[Callable[[str], None]] = None
    ) -> str:
        """调用 Anthropic Messages API (流式 SSE)"""
        full_text = []
        try:
            r = self._post_with_retry(payload, timeout=300, stream=True)

            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # Anthropic SSE: data: {...}
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        event_type = event.get("type", "")
                        if event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    full_text.append(text)
                                    if on_token:
                                        on_token(text)
                        elif event_type in ("message_stop", "message_delta"):
                            pass  # 流结束标记
                        elif event_type == "content_block_start":
                            pass  # 块开始
                    except json.JSONDecodeError:
                        continue

            return "".join(full_text)
        except Exception as e:
            logger.exception("Anthropic stream error")
            raise

    def _extract_text(self, response: dict) -> str:
        """从 Anthropic 响应中提取文本"""
        content = response.get("content", [])
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return "\n".join(texts) if texts else ""

    def _convert_functions_to_tools(self, functions: list[dict]) -> list[dict]:
        """将 OpenAI function definitions 转换为 Anthropic tool 格式

        OpenAI: {type: "function", function: {name, description, parameters}}
        Anthropic: {name, description, input_schema}
        """
        tools = []
        for f in functions:
            func = f.get("function", f)  # 兼容两种嵌套
            tools.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
            })
        return tools
