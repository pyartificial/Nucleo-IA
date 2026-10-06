@echo off
cd /d "%~dp0\.."
set /p ACC_ID="ID de cuenta SiliconFlow [siliconflow_1]: "
if "%ACC_ID%"=="" set ACC_ID=siliconflow_1
set /p API_KEY="API key SiliconFlow: "
if "%API_KEY%"=="" (
    echo [ERROR] Falta la API key
    pause
    exit /b 1
)
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe scripts\gestor_cuentas.py siliconflow "%ACC_ID%" "%API_KEY%"
) else (
    python scripts\gestor_cuentas.py siliconflow "%ACC_ID%" "%API_KEY%"
)
echo [OK] Guardado SiliconFlow: %ACC_ID%
pause
