@echo off
setlocal enabledelayedexpansion
title Agregar Cuenta TokenRouter - Nucleo IA

echo ======================================================
echo    AGREGAR CUENTA TOKENROUTER
echo ======================================================

set ACC_ID=tokenrouter_1
set /p USER_ID="ID de cuenta TokenRouter [%ACC_ID%]: "
if not "%USER_ID%"=="" set ACC_ID=%USER_ID%

set /p API_KEY="API key TokenRouter: "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key.
    pause
    exit /b 1
)

if exist "%~dp0..\venv\Scripts\python.exe" (
    "%~dp0..\venv\Scripts\python.exe" "%~dp0gestor_cuentas.py" tokenrouter "%ACC_ID%" "%API_KEY%"
) else (
    python "%~dp0gestor_cuentas.py" tokenrouter "%ACC_ID%" "%API_KEY%"
)

echo.
echo [OK] Guardado TokenRouter: %ACC_ID%
pause
