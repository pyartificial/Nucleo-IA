@echo off
title Nucleo IA - Ajustar Ranking Manual
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\ajustar_ranking_manual.py
) else (
    python scripts\ajustar_ranking_manual.py
)
pause
