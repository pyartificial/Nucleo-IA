@echo off
setlocal
title Nucleo IA - Instalador Maestro Windows
cd /d "%~dp0"

echo ===================================================
echo   INSTALADOR MAESTRO WINDOWS - Nucleo IA
echo ===================================================
echo.

set "PY_EXE="
set "PY_ARGS="

:: Reutilizar el entorno del proyecto, o buscar un Python 3 que realmente arranque.
if exist "venv\Scripts\python.exe" (
    set "PY_EXE=%CD%\venv\Scripts\python.exe"
) else (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 --version >nul 2>&1
        if not errorlevel 1 (
            set "PY_EXE=py"
            set "PY_ARGS=-3"
        )
    )
    if not defined PY_EXE (
        where python >nul 2>&1
        if not errorlevel 1 (
            python --version >nul 2>&1
            if not errorlevel 1 set "PY_EXE=python"
        )
    )
)

:: Si Windows no tiene Python utilizable, instalar Python 3.12 desde python.org.
if not defined PY_EXE (
    echo [INFO] No se encontro un Python funcional. Se instalara Python 3.12.
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ErrorActionPreference='Stop'; $url='https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe'; $dest=Join-Path $env:TEMP 'nucleo-ia-python-installer.exe'; try { Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest; $p=Start-Process -FilePath $dest -ArgumentList '/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1' -Wait -PassThru; if ($p.ExitCode -ne 0) { exit $p.ExitCode } } catch { Write-Error $_; exit 1 } finally { Remove-Item $dest -ErrorAction SilentlyContinue }"
    if errorlevel 1 goto :python_error

    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else if exist "%ProgramFiles%\Python312\python.exe" (
        set "PY_EXE=%ProgramFiles%\Python312\python.exe"
    ) else (
        echo [ERROR] Python termino de instalarse, pero no encuentro python.exe.
        goto :error
    )
)

echo [INFO] Python seleccionado: %PY_EXE% %PY_ARGS%
"%PY_EXE%" %PY_ARGS% --version
if errorlevel 1 goto :python_error

echo.
echo [1/4] Configurando entorno virtual (venv)...
if not exist "venv\Scripts\python.exe" (
    "%PY_EXE%" %PY_ARGS% -m venv venv
    if errorlevel 1 goto :venv_error
)
set "VENV_PY=%CD%\venv\Scripts\python.exe"
if not exist "%VENV_PY%" goto :venv_error

echo.
echo [2/4] Instalando dependencias desde requirements.txt...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :pip_error
if exist "requirements.txt" (
    "%VENV_PY%" -m pip install -r requirements.txt
) else (
    "%VENV_PY%" -m pip install "pydantic>=1.10.19" "fastapi>=0.99.0" "uvicorn>=0.29.0" "httpx>=0.27.0" "python-multipart"
)
if errorlevel 1 goto :pip_error

:: Comprobar lo necesario para importar y arrancar el servidor, incluido multipart.
"%VENV_PY%" -c "import fastapi, uvicorn, httpx, pydantic, multipart, edge_tts"
if errorlevel 1 goto :verify_error
echo   [OK] Dependencias instaladas y verificadas.

echo.
echo [3/4] Inicializando directorios y archivos de configuracion...
if not exist "state" mkdir "state"
if errorlevel 1 goto :files_error
if not exist "state\route_rankings" mkdir "state\route_rankings"
if errorlevel 1 goto :files_error
if not exist "ollama_instances" mkdir "ollama_instances"
if errorlevel 1 goto :files_error
if not exist ".env" if exist ".env.example" (
    copy /y ".env.example" ".env" >nul
    if errorlevel 1 goto :files_error
    echo   [OK] Creado archivo .env inicial.
)

echo.
echo [4/4] Preparando accesos directos de Windows...
if not exist "iniciar_segundo_plano.vbs" goto :files_error
"%VENV_PY%" "scripts\instalar_acceso_servicios.py"
if errorlevel 1 echo [AVISO] No se pudieron crear accesos directos. Podés abrir centro_control.vbs o mis_servicios.vbs.

echo.
echo ===================================================
echo      INSTALACION COMPLETADA EXITOSAMENTE
echo ===================================================
echo.
echo Para iniciar el servidor: iniciar_todo.bat
echo Para iniciarlo oculto: iniciar_segundo_plano.vbs
echo ===================================================
pause
exit /b 0

:python_error
echo [ERROR] No se pudo ejecutar Python. Revisa la instalacion de Python e intentalo otra vez.
goto :error
:venv_error
echo [ERROR] No se pudo crear el entorno virtual venv.
goto :error
:pip_error
echo [ERROR] Fallo pip al instalar dependencias. Revisa la conexion y el error mostrado arriba.
goto :error
:verify_error
echo [ERROR] Falta una dependencia requerida. El servidor no quedo listo; revisa requirements.txt y el error mostrado arriba.
goto :error
:files_error
echo [ERROR] No se pudieron preparar archivos o directorios requeridos.
:error
echo.
echo La instalacion no se completo. Corregi el error y vuelve a ejecutar este instalador.
pause
exit /b 1
