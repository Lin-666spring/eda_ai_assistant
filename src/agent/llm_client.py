"""
通用 LLM API 客户端 — 兼容 OpenAI/DeepSeek/通义千问/智谱/Kimi 等厂商

支持两种配置方式：
1. 厂商预设：设置 LLM_PROVIDER=deepseek 自动填入 base_url 和 model
2. 手动指定：直接设置 LLM_BASE_URL / LLM_MODEL 覆盖预设
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Generator, Callable

import requests

from ..constants import LLM_PROVIDER_PRESETS, DEFAULT_PROVIDER

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════
#  数据类
# ══════════════════════════════════════════════════════

@dataclass
class ChatRequest:
    """一次对话请求的参数对象"""
    messages: list[dict]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False

    def build_payload(self, model: str, **extra_fields) -> dict:
        """构建 API 请求体"""
        base = {
            "model": model,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": self.stream,
        }
        base.update(extra_fields)
        return base


@dataclass
class StreamToken:
    """流式响应的单个 token"""
    content: str = ""
    is_done: bool = False


# ══════════════════════════════════════════════════════
#  纯函数：响应解析
# ══════════════════════════════════════════════════════

def _extract_reply_text(response: dict) -> str:
    """从 API 响应中提取回复文本"""
    return response["choices"][0]["message"]["content"]


def _parse_tool_call_from_response(response: dict) -> dict:
    """从 API 响应中解析 Function Calling 结果"""
    tool_calls = response["choices"][0]["message"].get("tool_calls", [])
    if not tool_calls:
        return {"name": "", "arguments": {}}
    func = tool_calls[0]["function"]
    return {
        "name": func["name"],
        "arguments": json.loads(func["arguments"]),
    }


def _parse_stream_line(line: str) -> StreamToken:
    """解析单行 SSE 数据，返回 StreamToken"""
    if not line or not line.startswith("data: "):
        return StreamToken()
    data_str = line[6:]
    if data_str == "[DONE]":
        return StreamToken(is_done=True)
    try:
        data = json.loads(data_str)
        delta = data["choices"][0].get("delta", {})
        return StreamToken(content=delta.get("content", ""))
    except (json.JSONDecodeError, KeyError, IndexError):
        return StreamToken()


# ══════════════════════════════════════════════════════
#  厂商预设解析
# ══════════════════════════════════════════════════════

def resolve_provider(
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """解析厂商预设：provider 提供默认值，base_url/model 可覆盖"""
    preset = LLM_PROVIDER_PRESETS.get((provider or DEFAULT_PROVIDER).lower())
    if preset is None:
        preset = LLM_PROVIDER_PRESETS[DEFAULT_PROVIDER]
    return (
        base_url or preset.base_url,
        model or preset.default_model,
    )


# ══════════════════════════════════════════════════════
#  客户端
# ══════════════════════════════════════════════════════

class LLMClient:
    """通用大语言模型 API 客户端 — 兼容 OpenAI/DeepSeek/通义千问/智谱/Kimi 等"""

    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    DEFAULT_MODEL = "deepseek-chat"
    HISTORY_MAX_TURNS = 20
    API_ENDPOINT = "/chat/completions"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tool_executor: Optional[Callable[[str, dict], str]] = None,
    ):
        self.api_key = api_key
        resolved_url, resolved_model = resolve_provider(provider, base_url, model)
        self.base_url = resolved_url
        self.model = resolved_model
        self.provider_name = provider or DEFAULT_PROVIDER
        self._history: list[dict] = []
        self.tool_executor = tool_executor

    @property
    def provider_label(self) -> str:
        """当前厂商的可读名称"""
        return self.provider_name

    # ── 公开方法 ──

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        use_history: bool = False,
    ) -> str:
        """单轮对话（use_history=True 时附带已记录的历史）"""
        request = self._prepare_request(
            user_message, system_prompt, temperature, max_tokens, stream,
            use_history=use_history,
        )
        reply = self._execute(request)
        self._record_turn(user_message, reply)
        return reply

    def chat_with_history(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """带历史的多轮对话"""
        request = self._prepare_request(
            user_message, system_prompt, temperature, max_tokens,
            use_history=True,
        )
        reply = self._execute(request)
        self._record_turn(user_message, reply)
        return reply

    def chat_stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
        use_history: bool = False,
    ) -> str:
        """流式对话（use_history=True 时附带已记录的历史）"""
        request = self._prepare_request(
            user_message, system_prompt, stream=True, use_history=use_history,
        )
        reply = self._execute_stream(request, on_token)
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
        """多模态对话 — 发送文本 + 图片给视觉 LLM

        Args:
            user_message: 用户文本（如 "帮我分析这张PCB"）
            image_b64: Base64 编码的图片 (data URI 或纯 base64)
            system_prompt: 系统提示词
        """
        request = self._prepare_multimodal_request(
            user_message, image_b64, system_prompt, temperature, max_tokens,
        )
        reply = self._execute(request)
        self._record_turn(user_message, reply)
        return reply

    def _prepare_multimodal_request(
        self,
        user_message: str,
        image_b64: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatRequest:
        """构建多模态请求 — content 数组格式"""
        # 确保 image 是完整的 data URI
        if not image_b64.startswith("data:"):
            image_b64 = f"data:image/png;base64,{image_b64}"

        # 构建 content 数组
        content: list[dict] = [
            {"type": "text", "text": user_message},
            {"type": "image_url", "image_url": {"url": image_b64}},
        ]

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        return ChatRequest(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

    # [PLANNED] Agent Loop 接入 — 见 src/agent/tools.py 集成点注释
    def function_call(
        self,
        user_message: str,
        functions: list[dict],
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Function Calling — 已就绪，待 Agent Loop 接入"""
        request = self._prepare_request(user_message, system_prompt)
        payload = request.build_payload(
            self.model,
            tools=[{"type": "function", "function": f} for f in functions],
            tool_choice="auto",
        )
        response = self._post(payload)
        return _parse_tool_call_from_response(response)

    def chat_with_tools(
        self,
        user_message: str,
        functions: list[dict],
        system_prompt: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
        use_history: bool = False,
        max_iterations: int = 5,
    ) -> str:
        """多轮 Function Calling Agent Loop

        LLM 在每轮中决定调用工具或直接回复文本。工具执行结果会
        作为 tool 消息追加回对话，LLM 可以基于结果继续推理。

        Args:
            user_message: 用户输入
            functions: OpenAI 兼容的 function definitions
            system_prompt: 系统提示词
            on_token: 流式输出回调（最终文本回复时模拟流式 token 输出）
            use_history: 是否附带历史对话
            max_iterations: 最大工具调用轮数（防止无限循环）

        Returns:
            LLM 的最终文本回复
        """
        if self.tool_executor is None:
            raise RuntimeError(
                "LLMClient.tool_executor not set — Agent Loop requires a tool executor. "
                "Pass tool_executor=<callable> to LLMClient(...) or set client.tool_executor manually."
            )

        # 构建初始 messages（含历史 + 当前用户输入）
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if use_history:
            messages.extend(self._history[-self.HISTORY_MAX_TURNS * 2:])
        messages.append({"role": "user", "content": user_message})

        iteration = 0
        last_results: list[str] = []  # 收集所有工具执行结果

        while iteration < max_iterations:
            iteration += 1
            payload = self._build_tool_payload(messages, functions)
            response = self._post(payload)
            msg = response["choices"][0]["message"]

            # 情况1：LLM 要求调用工具
            if msg.get("tool_calls"):
                # 记录 assistant 消息（含 tool_calls）
                messages.append({
                    "role": "assistant",
                    "content": msg.get("content"),
                    "tool_calls": msg["tool_calls"],
                })

                for tc in msg["tool_calls"]:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        func_args = {}
                    try:
                        result = self.tool_executor(func_name, func_args)
                        last_results.append(f"[{func_name}] {result}")
                        logger.info(
                            "Agent tool: %s(%s) → %s",
                            func_name,
                            json.dumps(func_args, ensure_ascii=False),
                            result[:120],
                        )
                    except Exception as exc:
                        result = f"工具执行失败: {exc}"
                        logger.error("Tool %s failed: %s", func_name, exc)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                continue  # 回到循环顶部，让 LLM 消化工具结果

            # 情况2：LLM 返回纯文本（最终回复）
            full_text = msg.get("content", "")
            if on_token and full_text:
                # 模拟流式输出：字符级分块
                chunk_size = 3
                for i in range(0, len(full_text), chunk_size):
                    on_token(full_text[i:i + chunk_size])
            self._record_turn(user_message, full_text)
            return full_text

        # 超出 max_iterations → 返回工具执行结果摘要
        logger.warning(
            "Agent loop hit max_iterations=%d after %d tool calls",
            max_iterations, iteration,
        )
        summary = "⚠️ 已达到最大操作步数限制。以下是我已完成的操作：\n\n"
        summary += "\n".join(f"{i}. {r}" for i, r in enumerate(last_results, 1))
        if on_token:
            for i in range(0, len(summary), 3):
                on_token(summary[i:i + 3])
        self._record_turn(user_message, summary)
        return summary

    def _build_tool_payload(self, messages: list[dict], functions: list[dict]) -> dict:
        """构建带 tools 参数的 API 请求体"""
        # 转换 function definitions 为 tools 格式
        tools = [{"type": "function", "function": f["function"]} for f in functions]
        return {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
            "stream": False,
            "tools": tools,
            "tool_choice": "auto",
        }

    def clear_history(self):
        self._history.clear()

    def get_history(self) -> list[dict]:
        return self._history.copy()

    # ── 内部：请求准备 ──

    def _prepare_request(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        use_history: bool = False,
    ) -> ChatRequest:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if use_history:
            messages.extend(self._history[-self.HISTORY_MAX_TURNS * 2:])
        messages.append({"role": "user", "content": user_message})

        return ChatRequest(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

    # ── 内部：执行 ──

    def _execute(self, request: ChatRequest) -> str:
        """执行非流式请求"""
        payload = request.build_payload(self.model)
        response = self._post(payload)
        return _extract_reply_text(response)

    def _execute_stream(
        self,
        request: ChatRequest,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """执行流式请求"""
        tokens: list[str] = []
        for line in self._post_stream_lines(request):
            token = _parse_stream_line(line)
            if token.is_done:
                break
            if token.content:
                tokens.append(token.content)
                if on_token:
                    on_token(token.content)
        return "".join(tokens)

    # ── 内部：HTTP ──

    def _post(self, payload: dict) -> dict:
        """发送 POST 请求，返回解析后的 JSON"""
        headers = self._build_headers()
        url = f"{self.base_url}{self.API_ENDPOINT}"
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as error:
            logger.error(f"LLM API 请求失败 ({self.base_url}): {error}")
            raise

    def _post_stream_lines(self, request: ChatRequest) -> Generator[str, None, None]:
        """发送流式 POST 请求，逐行 yield"""
        headers = self._build_headers()
        url = f"{self.base_url}{self.API_ENDPOINT}"
        payload = request.build_payload(self.model)
        try:
            resp = requests.post(
                url, headers=headers, json=payload, stream=True, timeout=120
            )
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if raw_line:
                    yield raw_line.decode("utf-8")
        except requests.RequestException as error:
            logger.error(f"LLM 流式请求失败 ({self.base_url}): {error}")
            raise

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _record_turn(self, user_message: str, assistant_reply: str):
        """记录一轮对话到历史"""
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant", "content": assistant_reply})
