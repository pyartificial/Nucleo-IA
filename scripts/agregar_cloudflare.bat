@echo off
cd /d "%~dp0\.."
set /p ACC_ID="Account ID Cloudflare: "
set /p API_KEY="API Token Cloudflare Workers AI: "
if "%ACC_ID%"=="" (
    echo [ERROR] Falta Account ID
    pause
    exit /b 1
)
if "%API_KEY%"=="" (
    echo [ERROR] Falta API Token
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py cloudflare "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py cloudflare "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado Cloudflare: %ACC_ID%
pause
