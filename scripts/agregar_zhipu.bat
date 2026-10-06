@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta Zhipu AI [zhipu_1]: "
if "%ACC_ID%"=="" set ACC_ID=zhipu_1
set /p API_KEY="API key Zhipu AI: "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py zhipu "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py zhipu "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado Zhipu AI: %ACC_ID%
pause
