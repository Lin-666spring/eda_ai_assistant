"""
PCB 文件监听器 — 立创 EDA 项目目录自动同步。

监听用户指定的目录，检测 .json / .epro / .epro2 文件变化，
自动触发 PCB 重新加载和规则检查。
"""

import logging
import os
import threading
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
# PollingObserver 而非原生 Observer（2026-10-10 稳定性批）：Windows 原生实现
# 的 ReadDirectoryChangesW 是不可协作的原生阻塞调用 —— main.py 打了 gevent
# monkey-patch 后（threading→greenlet），原生 Observer 的等待循环会把整个
# hub 占死。PollingObserver 纯 Python 轮询（time.sleep），patch 下协作让出，
# 未 patch（测试/回退）下照常真实线程；对「文档目录里 .epro 变没变」1s 级
# 轮询延迟无感。
from watchdog.observers.polling import PollingObserver

from ..constants import WatcherConstants

logger = logging.getLogger(__name__)

# 立创 EDA 默认项目目录候选
DEFAULT_WATCH_PATHS = [
    Path.home() / "Documents" / "LCEDA",
    Path.home() / "Documents" / "EasyEDA",
    Path.home() / "LCEDA",
]

PCB_EXTENSIONS = WatcherConstants.PCB_EXTENSIONS


class PCBFileHandler(FileSystemEventHandler):
    """监听 PCB 文件变化，trailing 防抖。

    P1-12（验收 2026-10-24）：防抖必须尾部触发 —— 原实现是前置触发
    （首个事件立即回调、防抖窗口内的后续事件全部丢弃）：大文件写一半就
    回调（读到半截数据），而代表"完整写入"的最后一个 modify 事件反被
    抑制。改为每次事件重置该文件的静默计时器，写入静默 debounce_sec
    后才回调一次，回调时文件已写完。
    """

    def __init__(self, callback: Callable[[str], None], debounce_sec: float = 2.0):
        super().__init__()
        self._callback = callback
        self._debounce_sec = debounce_sec
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if not src.endswith(PCB_EXTENSIONS):
            return
        with self._lock:
            old = self._timers.pop(src, None)
            if old is not None:
                old.cancel()
            timer = threading.Timer(self._debounce_sec, self._fire, args=(src,))
            timer.daemon = True
            self._timers[src] = timer
        timer.start()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(PCB_EXTENSIONS):
            self.on_modified(event)

    def _fire(self, src: str):
        # 用计时器线程自身做身份核对：cancel 无法拦住已过静默期的计时器，
        # 陈旧计时器靠 "dict 里不是自己" 退避，不会误吞新计时器或双触发。
        with self._lock:
            if self._timers.get(src) is not threading.current_thread():
                return
            del self._timers[src]
        logger.info("PCB file changed: %s", src)
        try:
            self._callback(src)
        except Exception:
            logger.exception("PCB file watcher callback failed: %s", src)

    def cancel_pending(self):
        """丢弃尚未触发的静默计时器（停止监听时调用，防 stop 后仍回调）。"""
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for t in timers:
            t.cancel()


class FileWatcher:
    """文件监听器 — 独立守护线程，不阻塞 GUI。"""

    def __init__(self):
        self._observer: Optional[PollingObserver] = None
        self._handler: Optional[PCBFileHandler] = None
        self._watched_path: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    @property
    def watched_path(self) -> Optional[str]:
        return self._watched_path

    def watch(self, path: str, on_changed: Callable[[str], None]) -> bool:
        """开始监听目录。已运行时先停止旧监听。"""
        self.stop()
        if not os.path.isdir(path):
            logger.warning("Watch path does not exist: %s", path)
            return False
        self._observer = PollingObserver()
        self._handler = PCBFileHandler(on_changed)
        self._observer.schedule(
            self._handler, str(path), recursive=True,
        )
        self._observer.start()
        self._watched_path = path
        logger.info("File watcher started: %s", path)
        return True

    def stop(self):
        if self._observer is None:
            return
        try:
            self._observer.stop()
            self._observer.join(timeout=3)
        except Exception:
            logger.debug("Observer stop raised, ignored", exc_info=True)
        finally:
            # P1-12：trailing 防抖计时器随监听一并取消，避免 stop 后仍回调
            if self._handler is not None:
                self._handler.cancel_pending()
            self._handler = None
            self._observer = None
            self._watched_path = None
            logger.info("File watcher stopped")

    @staticmethod
    def default_watch_path() -> Optional[str]:
        """返回第一个存在的立创 EDA 默认项目目录。"""
        for p in DEFAULT_WATCH_PATHS:
            if p.is_dir():
                return str(p)
        return None
