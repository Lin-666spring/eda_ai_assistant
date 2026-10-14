# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — EDA AI 智能助手 onedir 分发打包

2026-10-14 分发拍板：onefile 无签名 exe 被 Defender 行为拦截（引导器解压
%TEMP%\\_MEIxxxx 被拒，静默死无日志），不可分发 ⇒ 正式分发走 onedir
（zip / Inno Setup 装机二选一）。exe 映像名保持 EDA_AI_Assistant.exe，
与用户侧 `Add-MpPreference -ExclusionProcess` 排除名对上（onedir 诊断版
的 _onedir 后缀名不要再出现）。
"""

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
        # torch 本体不进 exe（体积红线不变）。
        ('data/component_model.pt', 'data'),
        ('data/vocab.json', 'data'),
        # 2026-10-14 BERT 批：意图分类底座 rbt3 ONNX 随包（nlu_engine 优先加载；
        # 用户决定推翻「exe 不带意图模型」现状）。onnxruntime+tokenizers 作运行时
        # 栈（hiddenimports），torch/transformers 仍只在 dev 侧。产物缺失时引擎
        # 自动回退 TextCNN/embedding+关键词，缺文件不致命。
        ('data/models/intent_bert/model.onnx', 'data/models/intent_bert'),
        ('data/models/intent_bert/vocab.txt', 'data/models/intent_bert'),
        ('data/models/intent_bert/intent_config.json', 'data/models/intent_bert'),
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
        # chromadb 遥测走 importlib 懒加载，PyInstaller 分析不到（2026-10-14
        # 打包验证：frozen 下 RAG 初始化报 No module named
        # chromadb.telemetry.product.posthog），显式补上
        'chromadb.telemetry.product.posthog',
        # 2026-10-14 BERT 批：意图模型运行时栈（rbt3 ONNX 推理 + WordPiece 分词）。
        # 二者是 chromadb 的传递依赖但走懒加载，不显式声明 PyInstaller 分析不到。
        'onnxruntime',
        'tokenizers',
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

# onedir：EXE 只含引导器+脚本（exclude_binaries），二进制/数据落 COLLECT 的
# _internal\。主进程红线不变：main.py 顶部 --eda-bridge-slave 分发、
# 托盘/热键在桥接子进程，spec 侧无需感知。
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='EDA_AI_Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='EDA_AI_Assistant',
)
