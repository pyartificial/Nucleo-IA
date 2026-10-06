@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta Google Gemini [google_1]: "
if "%ACC_ID%"=="" set ACC_ID=google_1
set /p API_KEY="API key Google Gemini: "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py google "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py google "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado Google Gemini: %ACC_ID%
pause
