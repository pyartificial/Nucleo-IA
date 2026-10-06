@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta Groq [groq_1]: "
if "%ACC_ID%"=="" set ACC_ID=groq_1
set /p API_KEY="API key Groq (gsk_...): "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py groq "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py groq "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado Groq: %ACC_ID%
pause
