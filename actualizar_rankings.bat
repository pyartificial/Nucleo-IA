@echo off
title Nucleo IA - Actualizar Rankings
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe granja.py rank
) else (
    python granja.py rank
)
pause
