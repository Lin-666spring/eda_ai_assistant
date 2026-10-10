# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — EDA AI 智能助手 单文件打包"""

import sys
from pathlib import Path

# 注意：spec 由 PyInstaller exec 执行，没有 __file__；用注入的 SPECPATH。
_PROJECT = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(_PROJECT)],
    binaries=[],
    datas=[
        ('web', 'web'),
        ('src', 'src'),
        ('rag_data', 'rag_data'),
        # 2026-10-10 依赖批：模型词表随包（base.py 的 _model_dir 走 _MEIPASS/data）。
        # torch 本体不进 exe（体积），ML 分类在打包版按设计走规则回退 —— 见蓝图。
        ('data/component_model.pt', 'data'),
        ('data/vocab.json', 'data'),
        # 一键演示的内置样例 —— main.py / src/api/endpoints.py 都按
        # 「根目录/tests/」找这两个文件，不打包则打包版演示必然失败
        ('tests/sample_bom_bad.csv', 'tests'),
        ('tests/sample_positions.csv', 'tests'),
    ],
    hiddenimports=[
        'eel',
        'gevent',
        'geventwebsocket',
        'bottle',
        'bottle_websocket',
        'pandas',
        'openpyxl',
        'xlrd',
        'jinja2',
        'requests',
        'dotenv',
        'chromadb',
        # sentence_transformers 已删（2026-10-10 依赖批）：全仓库零 import、
        # requirements 亦无此包，纯 spec 漂移。
        # 托盘/全局热键（system_bridge.py 内的函数级导入，显式声明防漏）
        'pynput',
        'pystray',
        'PIL',
        # v0.7.1: LCEDA 插件 API 服务器
        'fastapi',
        'uvicorn',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette',
        'sse_starlette',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='EDA_AI_Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
