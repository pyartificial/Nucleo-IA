@echo off
setlocal enabledelayedexpansion
title Nucleo IA - Desactivar Inicio Automatico
cd /d "%~dp0"

echo ===================================================
echo   DESACTIVAR INICIO AUTOMATICO CON WINDOWS
echo ===================================================
echo.

reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "NucleoIA" /f >nul 2>&1

if %errorlevel% equ 0 (
    echo [OK] El inicio automatico con Windows ha sido desactivado con exito.
) else (
    echo [INFO] No habia ninguna entrada de inicio automatico activa o ya fue removida.
)

echo.
pause
