@echo off
rem Arrastra uno o varios videos sobre este archivo para transcribirlos (sin abrir la interfaz).
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Primero ejecuta instalar.bat
  pause
  exit /b 1
)
if "%~1"=="" (
  echo Arrastra un video sobre este archivo, o usa: transcribir.bat "C:\ruta\video.mp4"
  pause
  exit /b
)
:loop
if "%~1"=="" goto fin
"%~dp0.venv\Scripts\python.exe" "%~dp0transcribir.py" "%~1"
shift
goto loop
:fin
pause
