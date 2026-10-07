@echo off
echo === EDA AI 智能助手 — 打包 ===
rem 唯一构建入口：eda_ai_assistant.spec（rag_data、演示 CSV、uvicorn/pynput
rem 等 hiddenimports 都在 spec 里维护；此前 build.bat 的裸 pyinstaller 命令
rem 与 spec 漂移，打包版一键演示必 FileNotFoundError —— 2026-10-07 收敛）。
pip install -r requirements.txt
pyinstaller --noconfirm --clean eda_ai_assistant.spec
echo === 打包完成，产物在 dist\EDA_AI_Assistant.exe ===
pause
