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
rem 装机形态：检测到 Inno Setup 编译器就出 setup 包（eda_ai_assistant.iss；
rem 未装 ISCC 时跳过，zip 即分发物）
set ISCC=
rem 装机包需 Inno Setup 6+（Unicode 版）；5.x ANSI 编译器会把 iss 中文按 GBK 误读出乱码
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe
if defined ISCC (
    "%ISCC%" /DAPP_VERSION=%VER% eda_ai_assistant.iss
    echo === 装机包：dist\EDA_AI_Assistant_v%VER%_setup.exe ===
) else (
    echo === 未检测到 Inno Setup，跳过装机包 ===
)
pause
