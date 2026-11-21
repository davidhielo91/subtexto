# Construye el instalador de Windows: build\salida\Subtexto-Setup.exe
#
# Uso (desde la carpeta del proyecto):
#   powershell -ExecutionPolicy Bypass -File build\construir.ps1
#
# La versión sale de version.py (la misma que muestra la app): para publicar una nueva, cámbiala ahí.
# Necesita: Python 3.9+ (py o python) e Inno Setup 6.7+ (winget install JRSoftware.InnoSetup).

$ErrorActionPreference = "Stop"
$build = $PSScriptRoot
$raiz = Split-Path -Parent $build
$Version = [regex]::Match((Get-Content (Join-Path $raiz "version.py") -Raw), '__version__\s*=\s*"([^"]+)"').Groups[1].Value
if (-not $Version) { throw "No se encontró __version__ en version.py" }
Write-Host "Subtexto $Version" -ForegroundColor Cyan
$venv = Join-Path $build ".venv"
$py = Join-Path $venv "Scripts\python.exe"

function Ejecutar {
    param([string]$Programa, [string[]]$Argumentos)
    & $Programa @Argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falló: $Programa $($Argumentos -join ' ')" }
}

function Paso([string]$Texto) { Write-Host "`n==> $Texto" -ForegroundColor Cyan }

# 1. Entorno limpio solo con las librerías base (sin las de NVIDIA: esas se bajan al instalar).
if (-not (Test-Path $py)) {
    Paso "Creando entorno de construcción"
    if (Get-Command py -ErrorAction SilentlyContinue) { Ejecutar py @("-3", "-m", "venv", $venv) }
    else { Ejecutar python @("-m", "venv", $venv) }
}
Paso "Instalando librerías"
Ejecutar $py @("-m", "pip", "install", "--upgrade", "pip", "--quiet")
Ejecutar $py @("-m", "pip", "install", "-r", (Join-Path $raiz "requirements.txt"), "pyinstaller", "--quiet")

# 2. Programa empaquetado (Python incluido) en build\dist\Subtexto.
Paso "Empaquetando con PyInstaller"
Ejecutar $py @("-m", "PyInstaller", (Join-Path $build "subtexto.spec"), "--noconfirm",
    "--distpath", (Join-Path $build "dist"), "--workpath", (Join-Path $build "work"))

# 3. Lista de descargas (modelos y NVIDIA) con sus SHA-256.
Paso "Preparando la lista de descargas"
Ejecutar $py @((Join-Path $build "generar_descargas.py"))

# 4. Instalador.
Paso "Compilando el instalador"
$iscc = @(
    (Get-Command iscc -ErrorAction SilentlyContinue).Source,
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) { throw "No se encontró Inno Setup. Instálalo con: winget install JRSoftware.InnoSetup" }
Ejecutar $iscc @("/Q", "/DAppVersion=$Version", (Join-Path $build "instalador.iss"))

$setup = Join-Path $build "salida\Subtexto-Setup.exe"
Write-Host ("`nListo: {0} ({1:N0} MB)" -f $setup, ((Get-Item $setup).Length / 1MB)) -ForegroundColor Green
