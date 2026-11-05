@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo Запуск DeepSeek-to-Qwen...
python -m streamlit run app.py
pause