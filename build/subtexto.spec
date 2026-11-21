# Receta de PyInstaller: convierte Subtexto en dist\Subtexto\Subtexto.exe (Python y librerías incluidos).
# No se usa directo: lo llama construir.ps1.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

RAIZ = Path(SPECPATH).parent

datas = [(str(RAIZ / "assets"), "assets")]
binaries = []
hiddenimports = ["transcribir", "version"]
for paquete in ("customtkinter", "tkinterdnd2", "ctranslate2"):
    d, b, h = collect_all(paquete)
    datas += d
    binaries += b
    hiddenimports += h
datas += collect_data_files("faster_whisper")  # incluye el modelo de detección de voz (VAD)

a = Analysis(
    [str(RAIZ / "subtexto.pyw")],
    pathex=[str(RAIZ)],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "pandas", "scipy", "IPython", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Subtexto",
    icon=str(RAIZ / "assets" / "icono.ico"),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Subtexto", upx=False)
