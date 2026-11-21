# Instala Subtexto con un solo comando (PowerShell):
#   irm https://raw.githubusercontent.com/davidhielo91/subtexto/main/instalar.ps1 | iex
#
# Descarga la ultima version del instalador desde GitHub Releases y lo abre.
# (Este archivo va sin acentos para que se vea bien en cualquier version de PowerShell.)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # sin la barra de progreso la descarga es mucho mas rapida
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$url = "https://github.com/davidhielo91/subtexto/releases/latest/download/Subtexto-Setup.exe"
$setup = Join-Path $env:TEMP "Subtexto-Setup.exe"

Write-Host "Descargando Subtexto..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $url -OutFile $setup -UseBasicParsing
Unblock-File $setup

Write-Host "Abriendo el instalador: ahi eliges el modelo de IA y se descarga todo." -ForegroundColor Cyan
Start-Process -FilePath $setup -Wait
Remove-Item $setup -ErrorAction SilentlyContinue
Write-Host "Listo. Busca 'Subtexto' en el menu Inicio." -ForegroundColor Green
