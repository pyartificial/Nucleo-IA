@echo off
setlocal
cd /d "%~dp0"
title Centro de control - Nucleo IA
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "scripts\mis_servicios.py" --serve --panel %*
) else (
    py -3 "scripts\mis_servicios.py" --serve --panel %*
)
exit /b %errorlevel%
