; Instalador de Subtexto (Inno Setup 6.7+). No se compila a mano: lo hace construir.ps1.
; Instala el programa ya empaquetado por PyInstaller (dist\Subtexto) y, durante la instalación,
; descarga el modelo de IA elegido y las librerías de NVIDIA (ver descargas.iss).

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{3A1D924D-ED23-4BE3-814F-99CE7F085D14}
AppName=Subtexto
AppVersion={#AppVersion}
AppVerName=Subtexto {#AppVersion}
AppPublisher=David Hielo
AppPublisherURL=https://github.com/davidhielo91/subtexto
AppSupportURL=https://github.com/davidhielo91/subtexto/issues
AppUpdatesURL=https://github.com/davidhielo91/subtexto/releases
VersionInfoVersion={#AppVersion}
; Se instala solo para el usuario actual: no pide permisos de administrador y el programa
; puede escribir en su propia carpeta.
PrivilegesRequired=lowest
DefaultDirName={autopf}\Subtexto
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\LICENSE
SetupIconFile=..\assets\icono.ico
UninstallDisplayIcon={app}\Subtexto.exe
UninstallDisplayName=Subtexto
WizardStyle=modern dynamic
WizardSmallImageFile=..\assets\logo_64.png
; Panel lateral de las páginas de bienvenida y final (1x y 2x). Sale de brand\windows\ (ver brand\GUIA-DE-MARCA.md).
WizardImageFile=instalador-panel.png,instalador-panel-2x.png
OutputDir=salida
OutputBaseFilename=Subtexto-Setup
Compression=lzma2/ultra64
SolidCompression=yes
; Las librerías de NVIDIA vienen en archivos .whl (que son .zip).
ArchiveExtraction=full

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
es.GrupoModelo=Modelo de IA que se descarga ahora (puedes usar otros desde el programa; se bajan la primera vez):
es.ModeloTurbo=large-v3-turbo: muy preciso y rápido (1.6 GB) - recomendado
es.ModeloLarge=large-v3: máxima precisión, más lento (3.1 GB)
es.ModeloSmall=small: ligero y rápido, menos preciso (490 MB)
es.ModeloNinguno=No descargar ahora (se descarga la primera vez que transcribas)
es.GrupoGPU=Se detectó una tarjeta de video NVIDIA:
es.GPU=Descargar la aceleración NVIDIA (1.4 GB): transcribe varias veces más rápido

[Tasks]
Name: "modelo_large_v3_turbo"; Description: "{cm:ModeloTurbo}"; GroupDescription: "{cm:GrupoModelo}"; Flags: exclusive
Name: "modelo_large_v3"; Description: "{cm:ModeloLarge}"; GroupDescription: "{cm:GrupoModelo}"; Flags: exclusive unchecked
Name: "modelo_small"; Description: "{cm:ModeloSmall}"; GroupDescription: "{cm:GrupoModelo}"; Flags: exclusive unchecked
Name: "modelo_ninguno"; Description: "{cm:ModeloNinguno}"; GroupDescription: "{cm:GrupoModelo}"; Flags: exclusive unchecked
Name: "gpu"; Description: "{cm:GPU}"; GroupDescription: "{cm:GrupoGPU}"; Check: TieneNvidia
Name: "escritorio"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Al actualizar, quita las librerías de la versión anterior (los modelos y CUDA se conservan).
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "dist\Subtexto\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\AVISOS-DE-TERCEROS.txt"; DestDir: "{app}"; Flags: ignoreversion
#include "descargas.iss"

[Icons]
Name: "{autoprograms}\Subtexto"; Filename: "{app}\Subtexto.exe"; Comment: "Videos y audios a texto con IA local"
Name: "{autodesktop}\Subtexto"; Filename: "{app}\Subtexto.exe"; Comment: "Videos y audios a texto con IA local"; Tasks: escritorio

[Run]
Filename: "{app}\Subtexto.exe"; Description: "{cm:LaunchProgram,Subtexto}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\modelos"
Type: filesandordirs; Name: "{app}\cuda"

[Code]
// El controlador de NVIDIA instala nvcuda.dll en System32: si existe, hay tarjeta NVIDIA.
function TieneNvidia: Boolean;
begin
  Result := FileExists(ExpandConstant('{sys}\nvcuda.dll'));
end;

// Evita volver a descargar un archivo que ya está (por ejemplo, al actualizar Subtexto).
function NoExiste(Ruta: String): Boolean;
begin
  Result := not FileExists(ExpandConstant(Ruta));
end;
