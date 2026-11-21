"""Convierte texto en contornos SVG (paths) a partir de una fuente instalada, con fontTools.

Solo para construir el logotipo: el resultado se guarda como paths, así el SVG final no
depende de que la fuente esté instalada. Inter está bajo SIL Open Font License 1.1, que
permite usar los contornos en un logotipo.
"""

import os
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

CARPETAS = [Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts", Path("C:/Windows/Fonts")]


def fuente(nombre):
    for c in CARPETAS:
        p = c / nombre
        if p.exists():
            return TTFont(str(p))
    raise FileNotFoundError(nombre)


def glifos(font, texto, tam, x=0.0, base=0.0, tracking=0.0, desplazamientos=None):
    """Devuelve (lista de (letra, d), x_final). tam = alto del em en unidades del SVG.

    desplazamientos: dict índice -> (dx, dy) para mover letras sueltas.
    """
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    upm = font["head"].unitsPerEm
    esc = tam / upm
    salida = []
    for i, ch in enumerate(texto):
        nombre = cmap[ord(ch)]
        dx, dy = (desplazamientos or {}).get(i, (0, 0))
        pen = SVGPathPen(gs, ntos=lambda v: ("%.2f" % v).rstrip("0").rstrip("."))
        tp = TransformPen(pen, (esc, 0, 0, -esc, x + dx, base + dy))
        gs[nombre].draw(tp)
        salida.append((ch, pen.getCommands()))
        x += gs[nombre].width * esc + tracking
    return salida, x - tracking


def metricas(font, tam):
    upm = font["head"].unitsPerEm
    os2 = font["OS/2"]
    return {"x": os2.sxHeight * tam / upm, "cap": os2.sCapHeight * tam / upm}
