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

    def _on_token(token: str) -> None:
        """Called by the controller for each token chunk."""
        try:
            queue.put_nowait({"event": "token", "data": token})
        except asyncio.QueueFull:
            pass  # Should not happen with unlimited queue

    loop = asyncio.get_running_loop()

    if agent_mode:
        task = loop.run_in_executor(
            None, controller.agent_loop, text, _on_token, 5
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
