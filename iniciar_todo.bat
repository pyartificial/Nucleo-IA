@echo off
setlocal enabledelayedexpansion
title Nucleo IA - Iniciando Servidor

cd /d "%~dp0"

echo ===================================================
echo   INICIADOR WINDOWS - Nucleo IA
echo ===================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] No existe el entorno virtual de Núcleo IA.
    echo Ejecuta instalar_nucleo_ia.bat y vuelve a iniciar el servidor.
    pause
    exit /b 1
)
set "PY_BIN=%CD%\venv\Scripts\python.exe"

echo [1/2] Verificando procesos previos...
call detener_todo.bat >nul 2>&1

echo [2/2] Iniciando Servidor Proxy FastAPI con el Python del proyecto...
echo.
echo Presiona Ctrl+C para detener el servidor.
echo ===================================================
echo.

set "PYTHONPATH=%CD%"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

"%PY_BIN%" -m proxy.servidor
if errorlevel 1 (
    echo.
    echo [ERROR] El servidor terminó con un error. Revisa el mensaje anterior.
)
pause
