"""
系统交互 — 全局热键、系统托盘（独立桥接子进程承载）

伴生模式 vs 完整模式:
    380×520 小窗口（隐藏侧栏和面板，适合在立创EDA旁使用） vs 1300×840 三栏布局

2026-10-14 打包验证批 —— 架构变更：托盘+热键整体搬进独立桥接子进程。

为什么: pynput/pystray 的 Win32 消息泵线程与 gevent hub（eel 服务器主循环）
    不兼容 —— 同进程内任何消息泵线程一启动，hub 主线程即从解释器线程表消失
    （faulthandler 全线程栈实证），HTTP 服务接受连接但永不响应，前端永远
    空白。gevent 26.5/24.11 双后端（libuv/libev）皆然，与启动顺序无关。
    消息泵挪出主进程后互不相干。

通信协议（marker 文件，位于 app_home()/bridge/）:
    slave 写 toggle.flag → 主进程 watcher 线程消费 → request_toggle()
    slave 写 exit.flag   → 主进程 watcher 消费 → 落盘后退出
    主进程把自身 pid 传给 slave；slave 看门狗每 2s 探活，父进程消失即自杀；
    主进程退出时 terminate slave。spawn 失败/中途死亡只降级（无托盘无热键），
    主功能不受影响。

伴生模式状态机（主进程侧，与旧版一致）:
    request_toggle()  置位切换请求（热键/托盘/桥接消费时）
    consume_toggle()  JS 轮询消费，返回是否有待处理切换
"""

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 桥接 marker 目录（主进程与 slave 共用）──

_BRIDGE_SUBDIR = "bridge"
_TOGGLE_FLAG = "toggle.flag"
_EXIT_FLAG = "exit.flag"


def _bridge_dir() -> Path:
    from src.constants import app_home

    return app_home() / _BRIDGE_SUBDIR


# ══════════════════════════════════════════════════════
#  Mode state
# ══════════════════════════════════════════════════════

_companion_mode = False
_toggle_requested = False


def is_companion_mode() -> bool:
    return _companion_mode


def request_toggle() -> bool:
    """热键触发 → 设置切换请求标志，返回是否已排入"""
    global _toggle_requested
    _toggle_requested = True
    return True


def consume_toggle() -> bool:
    """JS 轮询 → 消费并返回是否有待处理的切换请求"""
    global _toggle_requested
    if _toggle_requested:
        _toggle_requested = False
        global _companion_mode
        _companion_mode = not _companion_mode
        return True
    return False


# ══════════════════════════════════════════════════════
#  桥接子进程（主进程侧）
# ══════════════════════════════════════════════════════

_bridge_proc: subprocess.Popen | None = None
_bridge_stop = threading.Event()


def _entry_script() -> str:
    """桥接 slave 的入口脚本路径（开发态 = main.py；打包态 = exe 自身）。

    打包态 sys.executable 即产品 exe，argv 带 --eda-bridge-slave 重入
    main.py 顶部的 slave 分发；开发态用 python main.py 同参数。
    """
    if getattr(sys, "frozen", False):
        return sys.executable
    return str(Path(__file__).resolve().parents[2] / "main.py")


def start_bridge_slave() -> bool:
    """拉起托盘+热键桥接子进程 + marker watcher 线程。成功返回 True。

    子进程命令行: <entry> --eda-bridge-slave <bridge_dir> <parent_pid>
    entry 在打包态是 exe 自身、开发态是 main.py —— main.py 顶部在 gevent
    patch 之前分发该参数，slave 全程无 gevent，消息泵随便跑。
    """
    global _bridge_proc, _bridge_stop
    if _bridge_proc is not None and _bridge_proc.poll() is None:
        return True
    _bridge_stop.clear()

    bridge_dir = _bridge_dir()
    try:
        bridge_dir.mkdir(parents=True, exist_ok=True)
        creationflags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        _bridge_proc = subprocess.Popen(
            [sys.executable, _entry_script(),
             "--eda-bridge-slave", str(bridge_dir), str(os.getpid())],
            creationflags=creationflags,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        logger.warning("桥接子进程拉起失败，托盘/热键不可用: %s", e)
        return False

    watcher = threading.Thread(target=_watch_bridge_markers, daemon=True,
                               name="bridge-marker-watcher")
    watcher.start()
    logger.info("System bridge slave started (pid=%s)", _bridge_proc.pid)
    return True


def stop_bridge_slave() -> None:
    """终止桥接子进程（主进程退出时调用；slave 侧另有父进程看门狗兜底）"""
    global _bridge_proc
    _bridge_stop.set()
    if _bridge_proc is not None and _bridge_proc.poll() is None:
        _bridge_proc.terminate()
        try:
            _bridge_proc.wait(timeout=3)
        except Exception:
            _bridge_proc.kill()
    _bridge_proc = None


def _watch_bridge_markers() -> None:
    """消费 slave 写来的 marker：toggle → 切换请求；exit → 落盘退出。

    纯文件 I/O 的守护线程（无消息泵，与 hub 兼容——warm_up 线程同款先例）。
    """
    while not _bridge_stop.wait(0.5):
        d = _bridge_dir()
        toggle = d / _TOGGLE_FLAG
        try:
            if toggle.exists():
                toggle.unlink(missing_ok=True)
                request_toggle()
            exit_flag = d / _EXIT_FLAG
            if exit_flag.exists():
                exit_flag.unlink(missing_ok=True)
                logger.info("桥接子进程请求退出，应用关闭")
                logging.shutdown()
                os._exit(0)
        except Exception as e:
            logger.debug("bridge marker 处理异常: %s", e)


# ══════════════════════════════════════════════════════
#  桥接子进程（slave 侧 —— 全程无 gevent）
# ══════════════════════════════════════════════════════

def run_bridge_slave() -> None:
    """slave 入口：argv = [--eda-bridge-slave, bridge_dir, parent_pid]

    由 main.py 顶部在 gevent patch 之前分发进来。托盘+热键跑在原生线程里，
    另起父进程看门狗（每 2s OpenProcess 探活，父不在即自杀，防孤儿托盘）。
    """
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")
    args = sys.argv
    try:
        idx = args.index("--eda-bridge-slave")
        bridge_dir = Path(args[idx + 1])
        parent_pid = int(args[idx + 2])
    except (IndexError, ValueError):
        print("用法: <entry> --eda-bridge-slave <bridge_dir> <parent_pid>",
              file=sys.stderr)
        sys.exit(2)

    bridge_dir.mkdir(parents=True, exist_ok=True)

    watchdog = threading.Thread(target=_watch_parent, args=(parent_pid,),
                                daemon=True, name="bridge-parent-watchdog")
    watchdog.start()

    threading.Thread(target=_slave_hotkey, daemon=True,
                     name="bridge-hotkey").start()
    _slave_tray(bridge_dir)   # 托盘在当前线程跑消息循环（slave 主循环）
    # 托盘退出（用户点「退出」）→ _write_exit_flag 已置位；等 watchdog 收尾
    time.sleep(5)


def _write_flag(name: str) -> None:
    try:
        (_bridge_dir() / name).write_text(
            time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    except OSError as e:
        logging.getLogger(__name__).warning("写 marker %s 失败: %s", name, e)


def _watch_parent(parent_pid: int) -> None:
    """父进程看门狗：OpenProcess 探活，父消失（句柄打不开）即自杀。"""
    import ctypes

    k32 = ctypes.windll.kernel32
    SYNCHRONIZE = 0x00100000
    while True:
        handle = k32.OpenProcess(SYNCHRONIZE, False, int(parent_pid))
        if not handle:
            logging.getLogger(__name__).info("父进程已退出，slave 跟随退出")
            os._exit(0)
        k32.CloseHandle(handle)
        time.sleep(2)


def _slave_hotkey() -> None:
    try:
        from pynput.keyboard import GlobalHotKeys

        def on_toggle():
            _write_flag(_TOGGLE_FLAG)

        with GlobalHotKeys({"<ctrl>+<shift>+e": on_toggle}) as listener:
            logging.getLogger(__name__).info("Global hotkey registered: Ctrl+Shift+E")
            listener.join()
    except ImportError:
        logging.getLogger(__name__).warning("pynput 未安装 — 热键不可用")
    except Exception as e:
        logging.getLogger(__name__).error("Hotkey listener failed: %s", e)


def _slave_tray(bridge_dir: Path) -> None:
    try:
        from pystray import Icon, Menu, MenuItem
        from PIL import Image, ImageDraw

        # 应用图标（web/img/app_icon.png，eel 资源在 frozen 下随 _MEIPASS 解包）
        root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) \
            else Path(__file__).resolve().parents[2]
        icon_file = root / "web" / "img" / "app_icon.png"
        if icon_file.is_file():
            img = Image.open(icon_file)
        else:                       # 兜底：PCB 绿底字标
            img = Image.new("RGB", (64, 64), "#0b542a")
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), "TW", fill="white")

        def _show_hide(icon, item):
            _write_flag(_TOGGLE_FLAG)

        def _toggle_mode(icon, item):
            _write_flag(_TOGGLE_FLAG)

        def _exit(icon, item):
            _write_flag(_EXIT_FLAG)
            icon.stop()

        menu = Menu(
            MenuItem("显示/隐藏", _show_hide, default=True),
            MenuItem("切换伴生模式", _toggle_mode),
            Menu.SEPARATOR,
            MenuItem("退出", _exit),
        )
        icon = Icon("eda_ai_assistant", img, "TraceWise", menu)
        logging.getLogger(__name__).info("System tray started")
        icon.run()
    except ImportError:
        logging.getLogger(__name__).warning("pystray/Pillow 未安装 — 托盘不可用")
    except Exception as e:
        logging.getLogger(__name__).error("Tray icon failed: %s", e)
