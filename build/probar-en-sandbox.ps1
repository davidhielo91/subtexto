# Prueba el instalador en una PC limpia: abre Windows Sandbox con build\salida en el escritorio.
#
# Uso (desde la carpeta del proyecto, después de build\construir.ps1):
#   powershell -ExecutionPolicy Bypass -File build\probar-en-sandbox.ps1
#
# Windows Sandbox viene en Windows 10/11 Pro, pero hay que activarlo una vez (como administrador y reiniciando):
#   Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All
#
# Adentro del Sandbox no hay tarjeta NVIDIA: sirve para probar la instalación, la descarga del modelo y el
# modo procesador, como en una computadora sin tarjeta de video. Al cerrarlo se borra todo.

$ErrorActionPreference = "Stop"
$salida = Join-Path $PSScriptRoot "salida"
if (-not (Test-Path (Join-Path $salida "Subtexto-Setup.exe"))) {
    throw "No existe build\salida\Subtexto-Setup.exe. Primero corre build\construir.ps1"
}
if (-not (Get-Command WindowsSandbox.exe -ErrorAction SilentlyContinue)) {
    throw ("Windows Sandbox no está activado. Actívalo (como administrador) y reinicia:`n" +
           "  Enable-WindowsOptionalFeature -Online -FeatureName Containers-DisposableClientVM -All")
}

$escritorio = "C:\Users\WDAGUtilityAccount\Desktop\Subtexto"
$config = @"
<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$salida</HostFolder>
      <SandboxFolder>$escritorio</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>explorer.exe $escritorio</Command>
  </LogonCommand>
</Configuration>
"@
$wsb = Join-Path $env:TEMP "subtexto-sandbox.wsb"
Set-Content -Path $wsb -Value $config -Encoding UTF8
Write-Host "Abriendo Windows Sandbox. Instala con Subtexto-Setup.exe (en la carpeta que se abre) y transcribe algo."
Start-Process $wsb
