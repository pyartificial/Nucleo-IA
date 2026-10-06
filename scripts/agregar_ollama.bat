@echo off
cd /d "%~dp0\.."
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\agregar_ollama.py %*
) else (
    python scripts\agregar_ollama.py %*
)
pause
