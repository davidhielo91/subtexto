@echo off
setlocal
cd /d "%~dp0"
title Instalador - Subtexto
echo.
echo  ==============================================
echo     Instalador de Subtexto
echo  ==============================================
echo.

rem ---------- 1. Python ----------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY goto sin_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto sin_python
for /f "delims=" %%v in ('%PY% --version') do echo  [OK] %%v encontrado

rem ---------- 2. Entorno virtual ----------
if exist ".venv\Scripts\python.exe" (
    echo  [OK] Entorno .venv ya existe
) else (
    echo  Creando entorno .venv ...
    %PY% -m venv .venv
    if errorlevel 1 goto error
)
set "VPY=.venv\Scripts\python.exe"

rem ---------- 3. Librerias ----------
echo.
echo  Instalando librerias (puede tardar unos minutos)...
"%VPY%" -m pip install --upgrade pip --quiet
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto error

where nvidia-smi >nul 2>nul
if errorlevel 1 (
    echo.
    echo  [i] No se detecto tarjeta NVIDIA: la IA usara el procesador ^(CPU^).
    echo      Funciona igual, solo que mas lento.
) else (
    echo.
    echo  [OK] Tarjeta NVIDIA detectada. Instalando librerias de GPU ^(~1.4 GB^)...
    "%VPY%" -m pip install -r requirements-gpu.txt
    if errorlevel 1 goto error
)

rem ---------- 4. ffmpeg ----------
echo.
where ffmpeg >nul 2>nul
if not errorlevel 1 (
    echo  [OK] ffmpeg encontrado
    goto acceso
)
echo  [!] No se encontro ffmpeg ^(se necesita para leer el audio de los videos^).
where winget >nul 2>nul
if errorlevel 1 goto ffmpeg_manual
choice /c SN /m "  Instalarlo ahora con winget"
if errorlevel 2 goto ffmpeg_manual
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
if errorlevel 1 goto ffmpeg_manual
echo  [OK] ffmpeg instalado. Cierra y vuelve a abrir las ventanas de terminal para que lo detecten.
goto acceso

:ffmpeg_manual
echo  Instala ffmpeg manualmente: https://ffmpeg.org/download.html
echo  o en una terminal: winget install Gyan.FFmpeg

rem ---------- 5. Acceso directo ----------
:acceso
echo.
choice /c SN /m "  Crear acceso directo en el escritorio"
if errorlevel 2 goto fin
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear_acceso_directo.ps1"

:fin
echo.
echo  ==============================================
echo   Listo. Para usarlo:
echo    - Doble clic en Subtexto.bat ^(o en el acceso directo^)
echo    - La primera transcripcion descarga el modelo de IA ^(hasta 3 GB^)
echo  ==============================================
echo.
pause
exit /b 0

:sin_python
echo  [X] No se encontro Python 3.9 o superior.
echo      Descargalo de https://www.python.org/downloads/
echo      Al instalar, marca la casilla "Add python.exe to PATH".
echo      O en una terminal: winget install Python.Python.3.12
echo.
pause
exit /b 1

:error
echo.
echo  [X] Algo fallo durante la instalacion. Revisa los mensajes de arriba.
pause
exit /b 1
