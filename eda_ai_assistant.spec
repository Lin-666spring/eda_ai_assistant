# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — EDA AI 智能助手 单文件打包"""

import sys
from pathlib import Path

_PROJECT = Path(__file__).parent

a = Analysis(
    ['main.py'],
    pathex=[str(_PROJECT)],
    binaries=[],
    datas=[
        ('web', 'web'),
        ('src', 'src'),
        ('rag_data', 'rag_data'),
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
        'sentence_transformers',
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
