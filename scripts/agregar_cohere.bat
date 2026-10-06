@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta Cohere [cohere_1]: "
if "%ACC_ID%"=="" set ACC_ID=cohere_1
set /p API_KEY="API key Cohere: "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py cohere "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py cohere "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado Cohere: %ACC_ID%
pause
