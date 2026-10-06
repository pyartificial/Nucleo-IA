@echo off
setlocal
title Nucleo IA - Configurar Inicio Automatico
cd /d "%~dp0"

echo ===================================================
echo   CONFIGURAR INICIO AUTOMATICO CON WINDOWS
echo ===================================================
echo.

set "VBS_PATH=%~dp0iniciar_segundo_plano.vbs"

if not exist "%VBS_PATH%" (
    echo [ERROR] No se encontro iniciar_segundo_plano.vbs
    echo Vuelve a copiar o reinstalar Nucleo IA.
    pause
    exit /b 1
)

if not exist "venv\Scripts\pythonw.exe" (
    echo [ERROR] Falta el entorno virtual de Python.
    echo Ejecuta primero instalar_nucleo_ia.bat
    pause
    exit /b 1
)

echo Registrando en el inicio de Windows del usuario actual...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "NucleoIA" /t REG_SZ /d "wscript.exe //B //NoLogo \"%VBS_PATH%\"" /f >nul 2>&1

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo  [OK] Nucleo IA se iniciara automaticamente cada
    echo       vez que inicies sesion en Windows en segundo
    echo       plano (sin abrir ventanas ni CMD).
    echo ===================================================
    echo.
    echo Iniciador registrado: %VBS_PATH%
    echo El inicio ocurre al iniciar sesion con este usuario.
    echo.
) else (
    echo [ERROR] No se pudo agregar la clave de inicio en el registro.
)

pause
