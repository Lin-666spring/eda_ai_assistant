"""
SSE (Server-Sent Events) streaming bridge.

The controller methods (chat_message_stream, agent_loop) are synchronous
and use a callback pattern:  controller.method(text, on_token=fn).

This module bridges that callback pattern into async SSE via an asyncio
Queue + ThreadPoolExecutor, so FastAPI can serve streaming responses
without modifying any controller code.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional

from sse_starlette.sse import EventSourceResponse

from src.api.server import get_controller

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  Core bridge: sync callback → async queue → SSE
# ═══════════════════════════════════════════════════════════════


async def _stream_chat_sse(text: str, agent_mode: bool = False):
    """Async generator that yields SSE events for a streaming chat request.

    1. Creates an asyncio.Queue
    2. Defines on_token that pushes {"event":"token","data":t} into the queue
    3. Runs the controller method in a thread-pool executor
    4. Enumerates queue items until the controller task completes
    5. Yields the final {"event":"done","data":full_text} event
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()
    controller = get_controller()
    loop = asyncio.get_running_loop()

    def _enqueue(event: dict) -> None:
        """执行器线程回调统一入口。

        2026-10-06 修复：controller 的 on_token/on_tool_call 跑在线程池线程里，
        而 asyncio.Queue 非线程安全 —— 之前直接 put_nowait 有竞态（并发多路
        流式请求时可能丢事件或损坏内部 deque）。现在 call_soon_threadsafe
        跳回事件循环线程入队。
        """
        try:
            loop.call_soon_threadsafe(queue.put_nowait, event)
        except RuntimeError:
            pass  # 客户端断开导致 loop 已关，丢弃残余 token 即可

    def _on_token(token: str) -> None:
        """Called by the controller for each token chunk."""
        _enqueue({"event": "token", "data": token})

    def _on_tool_call(name: str, args: dict) -> None:
        """Called by agent_loop before each tool execution."""
        _enqueue({
            "event": "tool_call",
            "data": json.dumps({"name": name, "args": args}, ensure_ascii=False),
        })

    if agent_mode:
        task = loop.run_in_executor(
            None, controller.agent_loop, text, _on_token, 5, _on_tool_call
        )
    else:
        task = loop.run_in_executor(
            None, controller.chat_message_stream, text, _on_token
        )

    # Drain the queue, yielding SSE events, until the task finishes.
    done = False
    while not done:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.05)
            yield event
        except asyncio.TimeoutError:
            if task.done():
                done = True
                # 排干残余事件再收尾：最后一个 token 的入队回调可能还挂在
                # 事件循环 ready 队列里，让一拍 + 取尽队列，避免尾部丢失。
                await asyncio.sleep(0)
                while not queue.empty():
                    yield queue.get_nowait()
                try:
                    full_text = task.result()
                except Exception as exc:
                    logger.exception("Streaming controller task failed")
                    yield {"event": "error", "data": str(exc)}
                    return
                yield {"event": "done", "data": full_text}


# ═══════════════════════════════════════════════════════════════
#  Route handler (called from endpoints.py)
# ═══════════════════════════════════════════════════════════════


def stream_chat_handler(text: str = "", agent_mode: bool = False):
    """Return an EventSourceResponse for the /chat/stream endpoint."""
    return EventSourceResponse(_stream_chat_sse(text=text, agent_mode=agent_mode))
