"""P1-10 回归（2026-10-08）：import main 不得有落盘/建客户端副作用。

之前 main.py 模块级 `controller = AppController()` + `_store = SessionStore()`：
导入期就建 LLM 客户端/路由，SessionStore._ensure_db 更是当场创建 sessions.db。
现在改为 get_controller()/get_store() 惰性单例 —— EDA_AI_HOME 指向的临时目录
在 import 后不应出现 sessions.db，首次调用 get_store() 后才落盘。
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_PROBE = (
    "import main;"
    "from src.core.persistence import DB_PATH;"
    "print('AFTER_IMPORT=' + str(DB_PATH.exists()), flush=True);"
    "main.get_store();"
    "print('AFTER_GET_STORE=' + str(DB_PATH.exists()), flush=True);"
    "c = main.get_controller();"
    "print('CTRL_TYPE=' + type(c).__name__, flush=True)"
)


def test_import_main_defers_db_and_controller(tmp_path):
    """import main 后无 sessions.db；get_store()/get_controller() 才初始化。"""
    env = {**os.environ, "EDA_AI_HOME": str(tmp_path), "PYTHONPATH": str(PROJECT_ROOT)}
    r = subprocess.run(
        [sys.executable, "-c", _PROBE],
        env=env, cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "AFTER_IMPORT=False" in r.stdout, f"import 期就建了库：{r.stdout}"
    assert "AFTER_GET_STORE=True" in r.stdout, f"get_store() 后该落盘：{r.stdout}"
    assert "CTRL_TYPE=AppController" in r.stdout
