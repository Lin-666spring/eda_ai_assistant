"""
PCB 文件监听器 — 立创 EDA 项目目录自动同步。

监听用户指定的目录，检测 .json / .epro 文件变化，
自动触发 PCB 重新加载和规则检查。
"""

import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# 立创 EDA 默认项目目录候选
DEFAULT_WATCH_PATHS = [
    Path.home() / "Documents" / "LCEDA",
    Path.home() / "Documents" / "EasyEDA",
    Path.home() / "LCEDA",
]

PCB_EXTENSIONS = (".json", ".epro")


class PCBFileHandler(FileSystemEventHandler):
    """监听 PCB 文件变化，带防抖。"""

    def __init__(self, callback: Callable[[str], None], debounce_sec: float = 2.0):
        super().__init__()
        self._callback = callback
        self._debounce_sec = debounce_sec
        self._last_events: dict[str, float] = {}

    def on_modified(self, event):
        if event.is_directory:
            return
        src = event.src_path
        if not src.endswith(PCB_EXTENSIONS):
            return
        now = time.time()
        last = self._last_events.get(src, 0)
        if now - last < self._debounce_sec:
            return
        self._last_events[src] = now
        logger.info("PCB file changed: %s", src)
        self._callback(src)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(PCB_EXTENSIONS):
            self.on_modified(event)


class FileWatcher:
    """文件监听器 — 独立守护线程，不阻塞 GUI。"""

    def __init__(self):
        self._observer: Optional[Observer] = None
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
        self._observer = Observer()
        self._observer.schedule(
            PCBFileHandler(on_changed), str(path), recursive=True,
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
