@echo off
setlocal
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta xKiro [xkiro_1]: "
if "%ACC_ID%"=="" set ACC_ID=xkiro_1
set /p API_KEY="API key xKiro (sk-xt-...): "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py xkiro "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py xkiro "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado xKiro: %ACC_ID%
pause
