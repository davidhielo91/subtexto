"""Regenera el ícono y el logo de Subtexto (la S cortada en renglones) y los copia aquí.

Uso: python assets/generar_icono.py
Crea toda la marca en brand/ y copia al programa: assets/icono.ico (16–256 px), assets/icono.png (1024 px),
assets/logo_64.png, assets/logo-horizontal.png y las imágenes del panel del instalador en build/.

El dibujo vive en brand/herramientas/construir_marca.py. Necesita Pillow, fontTools, la fuente Inter
instalada y Google Chrome o Microsoft Edge (ver brand/GUIA-DE-MARCA.md).
"""

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--aplicar"]
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "brand" / "herramientas" / "construir_marca.py"),
                   run_name="__main__")
