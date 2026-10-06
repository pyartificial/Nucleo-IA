@echo off
setlocal
cd /d "%~dp0"
title Mis servicios - Nucleo IA
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" "scripts\mis_servicios.py" --serve
    if errorlevel 1 pause
    exit /b
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "scripts\mis_servicios.py" --serve
    if errorlevel 1 pause
    exit /b
)
where python >nul 2>&1
if not errorlevel 1 (
    python "scripts\mis_servicios.py" --serve
    if errorlevel 1 pause
    exit /b
)
echo Falta Python. Abri instalar_nucleo_ia.bat y despues volve a Mis servicios.
pause
exit /b 1
