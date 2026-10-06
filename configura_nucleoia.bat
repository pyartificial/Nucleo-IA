@echo off
title Nucleo IA - Configuracion
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\configurar_granja.py
) else (
    python scripts\configurar_granja.py
)
pause
