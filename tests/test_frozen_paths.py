"""frozen（PyInstaller 打包版）模式路径契约回归

打包版的项目根是 ``sys._MEIPASS`` —— onefile 解包临时目录，进程退出即清空。
一切**会写盘**的东西都必须落 ``app_home()``（~/.eda_ai_assistant，可
EDA_AI_HOME 覆盖），否则"写完就没"：导出文件消失、日志丢失、RAG 索引每次
启动重算。只读资源（web/、rag_data 文档、演示 CSV）留在 _MEIPASS。

回归背景（2026-10-07）：spec 打包版实测任务中发现三处写盘路径在 frozen 下
都指向 _MEIPASS。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.constants import app_home


def _freeze(monkeypatch, tmp_path):
    """让代码以为自己跑在 PyInstaller onefile 里"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_MEIPASS"), raising=False)
    monkeypatch.setenv("EDA_AI_HOME", str(tmp_path / "home"))


def test_default_output_dir_frozen(monkeypatch, tmp_path):
    from src.core.controller import default_output_dir

    _freeze(monkeypatch, tmp_path)
    assert default_output_dir() == tmp_path / "home" / "output"


def test_rag_persist_dir_frozen(monkeypatch, tmp_path):
    """向量索引必须落用户目录；文档源（_MEIPASS/rag_data）保持只读。"""
    from src.rag.indexer import default_persist_dir

    _freeze(monkeypatch, tmp_path)
    assert default_persist_dir() == tmp_path / "home" / "rag_index"


def test_rag_persist_dir_dev(monkeypatch, tmp_path):
    """开发模式维持仓库内 rag_data/（既有行为，索引与文档同目录）。"""
    from src.rag import indexer

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert Path(indexer.DEFAULT_PERSIST_DIR) == PROJECT_ROOT / "rag_data"


def test_manifest_follows_index_not_docs(monkeypatch, tmp_path):
    """controller 建索引时 manifest 要跟索引同目录 —— 打包版里若放
    rag_data（_MEIPASS 内）退出即丢，增量索引永远失效、每次启动全量重索引。
    （dev 模拟下 __file__ 仍指仓库，故只断言 manifest 落点这一契约。）"""
    from src.core import controller as ctrl_mod

    _freeze(monkeypatch, tmp_path)
    # DEFAULT_PERSIST_DIR 是 indexer 的 import 期常量；真实 frozen 进程里
    # import 时 frozen 本就为 True（由 default_persist_dir() 解析到用户目录，
    # 见 test_rag_persist_dir_frozen）。这里 patch 掉它，验证 controller 把
    # manifest 放在「索引目录」而非「文档目录」的接线本身。
    monkeypatch.setattr(
        ctrl_mod, "DEFAULT_PERSIST_DIR", str(tmp_path / "home" / "rag_index"))
    captured = {}

    class _StubIndexer:
        chunk_count = 0

        def __init__(self, persist_dir=None):
            pass

        def index_directory(self, dir_path, manifest_path=None):
            captured["manifest_path"] = manifest_path
            return {"indexed": 0, "skipped": 0, "errors": []}

    monkeypatch.setattr(ctrl_mod, "RAGIndexer", _StubIndexer)
    assert ctrl_mod.AppController(api_key="")._ensure_rag_indexed() is True

    assert Path(captured["manifest_path"]) == tmp_path / "home" / "rag_index" / ".index_manifest.json"
