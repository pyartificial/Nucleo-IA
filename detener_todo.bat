@echo off
title Nucleo IA - Detener Servidor
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\detener_granja.py
) else (
    python scripts\detener_granja.py
)
