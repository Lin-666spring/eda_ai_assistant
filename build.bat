@echo off
echo === EDA AI 智能助手 — 打包（onedir 分发） ===
rem 唯一构建入口：eda_ai_assistant.spec（rag_data、演示 CSV、uvicorn/pynput
rem 等 hiddenimports 都在 spec 里维护；此前 build.bat 的裸 pyinstaller 命令
rem 与 spec 漂移，打包版一键演示必 FileNotFoundError —— 2026-10-07 收敛）。
rem 2026-10-14 分发拍板：onefile 无签名被 Defender 行为拦截不可分发，
rem 产物形态改 onedir，打包后自动出分发 zip。
pip install -r requirements.txt
pyinstaller --noconfirm --clean eda_ai_assistant.spec
if errorlevel 1 (
    echo === 打包失败 ===
    pause
    exit /b 1
)
rem 版本号唯一来源 src/constants.py 的 APP_VERSION，此处只提取不维护
set VER=
for /f "tokens=3" %%v in ('findstr /C:"APP_VERSION = " src\constants.py') do set VER=%%v
set VER=%VER:"=%
echo === 打包完成：dist\EDA_AI_Assistant\EDA_AI_Assistant.exe ===
powershell -NoProfile -Command "Compress-Archive -Path 'dist\EDA_AI_Assistant' -DestinationPath ('dist\EDA_AI_Assistant_v' + '%VER%' + '_win64.zip') -Force"
if errorlevel 1 (
    echo === zip 压缩失败（onedir 目录仍可用） ===
    pause
    exit /b 1
)
echo === 分发包：dist\EDA_AI_Assistant_v%VER%_win64.zip ===
pause
