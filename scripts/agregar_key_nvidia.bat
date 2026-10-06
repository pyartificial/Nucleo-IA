@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta NVIDIA [nvidia_1]: "
if "%ACC_ID%"=="" set ACC_ID=nvidia_1
set /p API_KEY="API key NVIDIA NIM (%ACC_ID%): "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py nvidia "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py nvidia "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado NVIDIA: %ACC_ID%
pause
