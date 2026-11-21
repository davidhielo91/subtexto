@echo off
rem Abre la interfaz grafica de Subtexto.
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Primero ejecuta instalar.bat
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0subtexto.pyw"
