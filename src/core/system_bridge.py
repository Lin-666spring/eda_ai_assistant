"""
系统交互 — 全局热键、系统托盘、窗口模式切换

伴生模式 vs 完整模式:
    伴生模式: 380×520 小窗口，隐藏侧栏和面板，适合在立创EDA旁使用
    完整模式: 1300×840 三栏布局，独立使用时的默认界面
"""

import logging
import threading

logger = logging.getLogger(__name__)

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
#  Global hotkey (pynput)
# ══════════════════════════════════════════════════════

def start_hotkey_listener():
    """在后台线程中启动全局快捷键监听 (Ctrl+Shift+E)"""

    def _run():
        try:
            from pynput.keyboard import GlobalHotKeys

            def on_toggle():
                request_toggle()
                logger.debug("Hotkey: Ctrl+Shift+E → toggle requested")

            with GlobalHotKeys({"<ctrl>+<shift>+e": on_toggle}) as listener:
                logger.info("Global hotkey registered: Ctrl+Shift+E")
                listener.join()
        except ImportError:
            logger.warning("pynput not installed — hotkey unavailable")
        except Exception as e:
            logger.error("Hotkey listener failed: %s", e)

    t = threading.Thread(target=_run, daemon=True, name="hotkey-listener")
    t.start()


# ══════════════════════════════════════════════════════
#  System tray (pystray)
# ══════════════════════════════════════════════════════

_tray_icon = None
_tray_show_callback = None
_tray_exit_callback = None


def start_tray(show_callback=None, exit_callback=None):
    """在后台线程中启动系统托盘图标"""
    global _tray_show_callback, _tray_exit_callback
    _tray_show_callback = show_callback
    _tray_exit_callback = exit_callback

    def _run():
        try:
            from pystray import Icon, Menu, MenuItem
            from PIL import Image, ImageDraw

            # 生成 64×64 纯色图标
            img = Image.new("RGB", (64, 64), "#5b8def")
            draw = ImageDraw.Draw(img)
            draw.text((14, 18), "EDA", fill="white")

            menu = Menu(
                MenuItem("显示/隐藏", _on_tray_show_hide, default=True),
                MenuItem("切换伴生模式", _on_tray_toggle_mode),
                Menu.SEPARATOR,
                MenuItem("退出", _on_tray_exit),
            )

            global _tray_icon
            _tray_icon = Icon("eda_ai_assistant", img, "EDA AI 智能助手", menu)
            logger.info("System tray started")
            _tray_icon.run()
        except ImportError:
            logger.warning("pystray/Pillow not installed — tray unavailable")
        except Exception as e:
            logger.error("Tray icon failed: %s", e)

    t = threading.Thread(target=_run, daemon=True, name="tray-icon")
    t.start()


def _on_tray_show_hide(icon, item):
    if _tray_show_callback:
        _tray_show_callback()
    else:
        request_toggle()


def _on_tray_toggle_mode(icon, item):
    request_toggle()


def _on_tray_exit(icon, item):
    if _tray_exit_callback:
        _tray_exit_callback()
    icon.stop()


def stop_tray():
    """停止托盘图标"""
    global _tray_icon
    if _tray_icon:
        _tray_icon.stop()
        _tray_icon = None
