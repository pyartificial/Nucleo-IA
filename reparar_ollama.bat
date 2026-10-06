@echo off
setlocal
title Nucleo IA - Reparar cuenta Ollama
cd /d "%~dp0"
echo ================================================================
echo   NUCLEO IA - REPARAR UNA CUENTA OLLAMA
echo ================================================================
echo.
set "PY="
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo [ERROR] No se encontro Python. Ejecuta instalar_nucleo_ia.bat primero.
  pause
  exit /b 1
)
if exist "venv\Scripts\python.exe" (
  "%CD%\venv\Scripts\python.exe" scripts\reparar_ollama.py
) else if /i "%PY%"=="py -3" (
  py -3 scripts\reparar_ollama.py
) else (
  python scripts\reparar_ollama.py
)
echo.
pause
