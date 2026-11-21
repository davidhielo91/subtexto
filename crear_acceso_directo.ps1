# Crea un acceso directo "Subtexto" en el escritorio que abre la interfaz grafica.
$proyecto = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = Join-Path $proyecto ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Host "No se encontro el entorno .venv. Ejecuta primero instalar.bat" -ForegroundColor Red
    exit 1
}
$escritorio = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell
$acceso = $shell.CreateShortcut((Join-Path $escritorio "Subtexto.lnk"))
$acceso.TargetPath = $pythonw
$acceso.Arguments = "`"$(Join-Path $proyecto 'subtexto.pyw')`""
$acceso.WorkingDirectory = $proyecto
$acceso.IconLocation = "$(Join-Path $proyecto 'assets\icono.ico'),0"
$acceso.Description = "Transcribe videos y audios con IA local (Whisper)"
$acceso.Save()
Write-Host "Acceso directo creado en el escritorio: Subtexto" -ForegroundColor Green
