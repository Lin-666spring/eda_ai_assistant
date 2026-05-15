"""
EDA AI 智能助手 — 应用入口
面向立创EDA的AI智能辅助设计软件
"""

import sys
import logging
from pathlib import Path

# 将项目根目录加入 Python 路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.gui.main_window import MainWindow


def setup_logging():
    """配置日志"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    # Ensure stdout can handle emoji/unicode on Windows terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    """应用主入口"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("启动 EDA AI 智能助手...")

    # 高 DPI 适配
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("EDA AI 智能助手")
    app.setOrganizationName("JLU-测控")

    # 创建并显示主窗口
    window = MainWindow()
    window.show()

    logger.info("主窗口已启动")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
