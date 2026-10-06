@echo off
setlocal
set "ROOT=%~dp0.."
set "ACC_ID=tokenharbor_1"
echo Agregar cuenta Token Harbor (%ACC_ID%)
echo Aviso: las rutas :free pueden retener prompts y respuestas segun su politica.
set /p API_KEY="API key Token Harbor (thk_...): "
if "%API_KEY%"=="" (
  echo [ERROR] Falta la API key.
  exit /b 1
)
if exist "%ROOT%\venv\Scripts\python.exe" (
  "%ROOT%\venv\Scripts\python.exe" "%ROOT%\scripts\gestor_cuentas.py" tokenharbor "%ACC_ID%" "%API_KEY%"
) else (
  python "%ROOT%\scripts\gestor_cuentas.py" tokenharbor "%ACC_ID%" "%API_KEY%"
)
if errorlevel 1 exit /b %errorlevel%
echo [OK] Token Harbor guardado. Actualiza los rankings para probar las rutas :free.
