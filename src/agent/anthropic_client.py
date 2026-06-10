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
from typing import Optional, Callable

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"


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

        for iteration in range(max_iterations):
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

                    # 执行工具 (复用 controller 的 dispatch)
                    if self.tool_executor:
                        result_text = self.tool_executor(tool_name, tool_input)
                    else:
                        result_text = json.dumps({"error": "no tool executor"}, ensure_ascii=False)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_text,
                    })

                # 将 tool_result 加入消息
                messages.append({"role": "user", "content": tool_results})

            elif stop_reason == "end_turn":
                # LLM 完成回复
                reply = self._extract_text(resp)
                self._record_turn(user_message, reply)
                return reply
            else:
                # stop 或其他 — 尝试提取文本
                reply = self._extract_text(resp)
                self._record_turn(user_message, reply)
                return reply

        return self._extract_text(resp) if 'resp' in dir() else "(Agent loop max iterations reached)"

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
        self._history = []

    # ══════════════════════════════════════════
    #  内部方法
    # ══════════════════════════════════════════

    def _build_messages(self, user_message: str, use_history: bool = False) -> list[dict]:
        messages = []
        if use_history:
            for turn in self._history[-self.HISTORY_MAX_TURNS * 2:]:
                messages.append(turn)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _record_turn(self, user_msg: str, reply: str):
        self._history.append({"role": "user", "content": user_msg})
        self._history.append({"role": "assistant", "content": reply})
        if len(self._history) > self.HISTORY_MAX_TURNS * 2:
            self._history = self._history[-self.HISTORY_MAX_TURNS * 2:]

    def _api_call(self, payload: dict) -> dict:
        """调用 Anthropic Messages API (非流式)"""
        try:
            r = requests.post(
                self.base_url,
                headers=self._headers(),
                json=payload,
                timeout=120,
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            detail = ""
            try:
                detail = e.response.text[:500]
            except Exception:
                pass
            logger.error("Anthropic API error: %s — %s", e, detail)
            raise

    def _api_stream(
        self, payload: dict, on_token: Optional[Callable[[str], None]] = None
    ) -> str:
        """调用 Anthropic Messages API (流式 SSE)"""
        full_text = []
        try:
            r = requests.post(
                self.base_url,
                headers=self._headers(),
                json=payload,
                timeout=300,
                stream=True,
            )
            r.raise_for_status()

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
