@echo off
echo === EDA AI 智能助手 — 打包 ===
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "EDA_AI_Assistant" ^
    --add-data "web;web" ^
    --add-data "src;src" ^
    --hidden-import pynput ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    main.py
echo === 打包完成，产物在 dist\EDA_AI_Assistant.exe ===
pause
