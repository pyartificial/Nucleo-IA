@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta OpenRouter [openrouter_1]: "
if "%ACC_ID%"=="" set ACC_ID=openrouter_1
set /p API_KEY="API key OpenRouter (%ACC_ID%): "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
set /p URL_APP="URL app (opcional): "
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py openrouter "%ACC_ID%" "%API_KEY%" "%URL_APP%"
) else (
    python scripts\gestor_cuentas.py openrouter "%ACC_ID%" "%API_KEY%" "%URL_APP%"
)
echo [OK] Guardado OpenRouter: %ACC_ID%
pause
