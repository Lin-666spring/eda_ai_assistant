"""
启动时序 — 两段式加载（小窗先出，正式界面后到）

为什么有它:
    以前 main() 是「先把重活干完，再开窗口」——RAG 建索引、热键、托盘全跑完，
    屏幕上才出现第一个像素；用户双击之后只能盯着桌面，不知道程序在干什么。
    现在改成: 浏览器窗口先开成 480×340 的小窗显示加载态，重活丢到后台线程，
    关键步骤一完成，前端就把窗口展开成 1300×840 的正式界面。

BootSequencer 只管「现在到哪一步了」，不碰 UI、不碰 eel，方便单测:
    * critical 步骤决定 ready —— 前端据此决定何时展开正式界面；
    * 非 critical 步骤（知识库预热）只影响 warm，不挡界面，
      否则首次启动会卡在索引上十几秒。

约定: **failed 也算「结束」**。启动步骤都是尽力而为的附属功能（热键/托盘/索引），
      任何一个失败都不该把用户永远关在小窗里。失败原因记进 errors，前端照常展开。
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

logger = logging.getLogger(__name__)

# 步骤状态
PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"

_FINISHED = (DONE, FAILED)


@dataclass(frozen=True)
class BootStep:
    """一个启动步骤。

    key:      机器可读标识（前端 / 日志用）
    label:    加载界面上显示的中文文案
    critical: True 表示「没跑完就不展开正式界面」
    """

    key: str
    label: str
    critical: bool = False


# 默认步骤：热键 + 托盘是正式界面可用之前必须就位的；
# 知识库预热是纯后台，放进 ready 会让首次启动白等十几秒。
DEFAULT_STEPS: tuple[BootStep, ...] = (
    BootStep("services", "正在注册全局热键与系统托盘", critical=True),
    BootStep("knowledge", "正在预热知识库", critical=False),
)


class BootSequencer:
    """启动步骤状态机（线程安全）。

    典型用法（main.py）::

        boot = BootSequencer()
        boot.start()                       # 标记「走的是两段式启动」
        threading.Thread(target=worker).start()
        ...
        with boot.step("services"):
            start_hotkey_listener()
            start_tray(...)
    """

    def __init__(self, steps: tuple[BootStep, ...] = DEFAULT_STEPS) -> None:
        self._lock = threading.RLock()
        self._steps = list(steps)
        self._labels = {s.key: s.label for s in self._steps}
        self._critical = {s.key: s.critical for s in self._steps}
        self._state = {s.key: PENDING for s in self._steps}
        self._errors: dict[str, str] = {}
        self._started = False
        self._t0: float | None = None

    # ── 生命周期 ──────────────────────────────────────

    def start(self) -> None:
        """标记启动开始（幂等）。前端只在 started 为真时才等后端。"""
        with self._lock:
            if self._started:
                return
            self._started = True
            self._t0 = time.monotonic()

    def begin(self, key: str) -> None:
        with self._lock:
            if key in self._state and self._state[key] == PENDING:
                self._state[key] = RUNNING
                logger.debug("Boot step begin: %s", key)

    def done(self, key: str) -> None:
        with self._lock:
            if key not in self._state:
                return
            if self._state[key] != FAILED:      # 失败就是失败，别被后到的 done 洗掉
                self._state[key] = DONE
            logger.debug("Boot step done: %s", key)

    def fail(self, key: str, error: object = None) -> None:
        with self._lock:
            if key not in self._state:
                return
            self._state[key] = FAILED
            if error is not None:
                self._errors[key] = str(error)
            logger.warning("Boot step failed: %s (%s)", key, error)

    @contextmanager
    def step(self, key: str) -> Iterator[None]:
        """把一段启动代码包成一步。

        **异常不向外抛**：启动步骤都是尽力而为的附属功能，失败只记账 + 记日志，
        主流程继续（用户不该因为托盘图标画不出来就卡在加载界面）。
        """
        self.begin(key)
        try:
            yield
        except Exception as e:                  # noqa: BLE001 — 见 docstring
            logger.exception("Boot step %s raised", key)
            self.fail(key, e)
        else:
            self.done(key)

    # ── 查询 ──────────────────────────────────────────

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    @property
    def ready(self) -> bool:
        """关键步骤都结束了（成功或失败）→ 可以展开正式界面。"""
        with self._lock:
            return all(self._state[k] in _FINISHED
                       for k, crit in self._critical.items() if crit)

    @property
    def warm(self) -> bool:
        """所有步骤都结束了（含后台预热）。"""
        with self._lock:
            return all(s in _FINISHED for s in self._state.values())

    @property
    def current(self) -> tuple[str, str]:
        """(key, label) —— 正在跑的步骤；没有正在跑的则给下一个待办；全完则空。"""
        with self._lock:
            for s in self._steps:
                if self._state[s.key] == RUNNING:
                    return s.key, s.label
            for s in self._steps:
                if self._state[s.key] == PENDING:
                    return s.key, s.label
            return "", ""

    def status(self) -> dict:
        """给前端轮询的快照（JSON 友好）。"""
        with self._lock:
            finished = sum(1 for s in self._state.values() if s in _FINISHED)
            total = len(self._state) or 1
            key, label = self.current
            if not label:
                label = "即将就绪"
            elapsed_ms = int((time.monotonic() - self._t0) * 1000) if self._t0 else 0
            return {
                "started": self._started,
                "ready": self.ready,
                "warm": self.warm,
                "percent": int(finished * 100 / total),
                "step": key,
                "text": label,
                "elapsed_ms": elapsed_ms,
                "steps": [
                    {
                        "key": s.key,
                        "label": s.label,
                        "critical": s.critical,
                        "state": self._state[s.key],
                    }
                    for s in self._steps
                ],
                "errors": dict(self._errors),
            }
