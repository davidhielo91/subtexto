"""Construye toda la marca de Subtexto a partir de la geometría: masters SVG, ícono de Windows,
íconos web, imágenes para GitHub/redes y las imágenes del instalador.

Uso (desde la raíz del proyecto):
    python brand/herramientas/construir_marca.py            # todo, solo dentro de brand/
    python brand/herramientas/construir_marca.py --sin-png  # solo los SVG (rápido)
    python brand/herramientas/construir_marca.py --aplicar  # además lo pone en el programa
                                                            # (assets/ e imágenes del instalador en build/)

Necesita: Python 3.9+, Pillow, fontTools, la fuente Inter instalada (SIL OFL 1.1,
https://rsms.me/inter/) y Google Chrome o Microsoft Edge (para pasar los SVG a PNG).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from glifos import fuente  # noqa: E402
from trazo import trazo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
MARCA = RAIZ / "brand"
ASSETS = RAIZ / "assets"
BUILD = RAIZ / "build"

# ---- Paleta ---------------------------------------------------------------------------------
VIOLETA = "#8B5CF6"      # principal
NOCHE = "#111827"        # fondo oscuro (el de la app)
PANEL = "#1A2333"
TINTA = "#111827"        # texto sobre claro
NIEVE = "#F8FAFC"        # texto sobre oscuro
GRIS = "#94A3B8"         # texto secundario sobre oscuro
GRIS_CLARO = "#475569"   # texto secundario sobre claro
CORAL = "#F59E70"        # acento (video)
AZUL = "#38BDF8"         # acento (audio)
NEGRO, BLANCO = "#000000", "#FFFFFF"


# ---- Símbolo: la S cortada --------------------------------------------------------------------
def simbolo(w=36, r=32, corte=24, brazo=204):
    """S de tres renglones con un corte recto en el lomo. Lienzo 256×256, simétrica al girar 180°.

    w: grosor · r: radio de las curvas (al eje) · corte: ancho del corte · brazo: x donde termina
    el renglón de arriba (el de abajo es su espejo).
    """
    izq, der, c = 96, 160, 128
    yt = 128 - 2 * r
    arriba = trazo((brazo, yt), 180, [("L", brazo - izq), ("A", r, -180), ("L", c - corte / 2 - izq)], w,
                   tapa_fin="plana")
    abajo = trazo((c + corte / 2, 128), 0, [("L", der - (c + corte / 2)), ("A", r, 180), ("L", brazo - izq)], w,
                  tapa_inicio="plana")
    caja = (min(izq - r - w / 2, 256 - brazo - w / 2), yt - w / 2,
            max(der + r + w / 2, brazo + w / 2), 128 + 2 * r + w / 2)
    return [arriba, abajo], caja


S_NORMAL = dict(w=36, r=32, corte=24, brazo=204)
S_BLANCA = dict(w=34, r=32, corte=26, brazo=204)        # en blanco sobre oscuro se ve más gruesa: se adelgaza
S_CHICA = dict(w=46, r=36, corte=34, brazo=200)         # corte para 16–32 px: más grosor y corte más abierto


# ---- Texto como contornos ------------------------------------------------------------------------
class Texto:
    def __init__(self, archivo, texto, tam, tracking=0.0, kern=None):
        f = fuente(archivo)
        gs, cmap, upm = f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm
        esc = tam / upm
        self.cap = f["OS/2"].sCapHeight * esc
        self.xh = f["OS/2"].sxHeight * esc
        self.d, x = [], 0.0
        bp = BoundsPen(gs)
        for i, ch in enumerate(texto):
            nombre = cmap[ord(ch)]
            x += (kern or {}).get(i, 0) * tam
            pen = SVGPathPen(gs, ntos=lambda v: ("%.2f" % v).rstrip("0").rstrip("."))
            gs[nombre].draw(TransformPen(pen, (esc, 0, 0, -esc, x, 0)))
            gs[nombre].draw(TransformPen(bp, (esc, 0, 0, -esc, x, 0)))
            self.d.append(pen.getCommands())
            x += gs[nombre].width * esc + tracking * tam
        self.x0, self.y0, self.x1, self.y1 = bp.bounds   # y hacia abajo: y0 = arriba (negativo)
        self.ancho = self.x1 - self.x0

    def g(self, x, base, color):
        """Coloca el texto con su borde izquierdo de tinta en x y la línea base en `base`."""
        cuerpo = "".join(f'<path d="{d}"/>' for d in self.d)
        return f'<g fill="{color}" transform="translate({x - self.x0:.2f} {base:.2f})">{cuerpo}</g>'


def palabra(tam=100):
    # Inter Bold con un poco de tracking negativo; pequeños ajustes de pares a ojo.
    return Texto("Inter_24pt-Bold.ttf", "Subtexto", tam, tracking=-0.018, kern={1: -0.01, 4: -0.005, 6: -0.005})


def g_simbolo(params, x, y, alto, color):
    """Coloca el símbolo para que su caja de tinta empiece en (x, y) y mida `alto`."""
    caminos, (bx0, by0, bx1, by1) = simbolo(**params)
    k = alto / (by1 - by0)
    cuerpo = "".join(f'<path d="{d}"/>' for d in caminos)
    return (f'<g fill="{color}" transform="translate({x - bx0 * k:.2f} {y - by0 * k:.2f}) scale({k:.5f})">'
            f'{cuerpo}</g>'), (bx1 - bx0) * k


def ancho_simbolo(params, alto):
    _, (bx0, by0, bx1, by1) = simbolo(**params)
    return (bx1 - bx0) * alto / (by1 - by0)


def svg_doc(ancho, alto, cuerpo, titulo="Subtexto", fondo=None):
    f = f'<rect width="{ancho}" height="{alto}" fill="{fondo}"/>' if fondo else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho:g} {alto:g}" '
            f'width="{ancho:g}" height="{alto:g}" role="img"><title>{titulo}</title>{f}{cuerpo}</svg>\n')


def escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


# ---- Masters del logo ---------------------------------------------------------------------------
# Proporciones fijas del lockup (en unidades de la altura de mayúscula C de la palabra):
#   horizontal: S de 1.4 C de alto, separación 0.5 C, S centrada con la altura de mayúscula.
#   apilado:    S de 2.4 C de alto, separación 0.75 C, todo centrado.
def horizontal(color_s, color_txt, params=S_NORMAL):
    p = palabra(100)
    C = p.cap
    alto_s = 1.4 * C
    sim, ancho_s = g_simbolo(params, 0, 0, alto_s, color_s)
    sep = 0.5 * C
    base = alto_s / 2 + C / 2
    ancho = ancho_s + sep + p.ancho
    return svg_doc(round(ancho, 2), round(alto_s, 2), sim + p.g(ancho_s + sep, base, color_txt))


def apilado(color_s, color_txt, params=S_NORMAL):
    p = palabra(100)
    C = p.cap
    alto_s = 2.4 * C
    ancho_s = ancho_simbolo(params, alto_s)
    ancho = max(p.ancho, ancho_s)
    sim, _ = g_simbolo(params, (ancho - ancho_s) / 2, 0, alto_s, color_s)
    sep = 0.75 * C
    base = alto_s + sep + C
    return svg_doc(round(ancho, 2), round(base, 2), sim + p.g((ancho - p.ancho) / 2, base, color_txt))


def solo_palabra(color):
    p = palabra(100)
    return svg_doc(round(p.ancho, 2), round(p.cap, 2), p.g(0, p.cap, color))


def solo_simbolo(color, params=S_NORMAL, lienzo=256, margen=None):
    """Símbolo centrado en un cuadrado (margen = fracción libre a cada lado)."""
    if margen is None:
        caminos, _ = simbolo(**params)
        cuerpo = "".join(f'<path d="{d}"/>' for d in caminos)
        return svg_doc(256, 256, f'<g fill="{color}">{cuerpo}</g>')
    alto = lienzo * (1 - 2 * margen)
    ancho_s = ancho_simbolo(params, alto)
    sim, _ = g_simbolo(params, (lienzo - ancho_s) / 2, lienzo * margen, alto, color)
    return svg_doc(lienzo, lienzo, sim)


def mosaico(params, lado=256, inset=0.0, radio=0.22, escala=0.6, fondo=VIOLETA, color=BLANCO, sangrado=False):
    """Ícono de app: placa redondeada (o a sangre) con la S en blanco centrada.

    escala = alto de la S / lado de la placa.
    """
    i = lado * inset
    placa_lado = lado - 2 * i
    if sangrado:
        placa = f'<rect width="{lado}" height="{lado}" fill="{fondo}"/>'
    else:
        rr = placa_lado * radio
        placa = (f'<rect x="{i:g}" y="{i:g}" width="{placa_lado:g}" height="{placa_lado:g}" '
                 f'rx="{rr:.2f}" fill="{fondo}"/>')
    alto = placa_lado * escala
    ancho_s = ancho_simbolo(params, alto)
    sim, _ = g_simbolo(params, (lado - ancho_s) / 2, (lado - alto) / 2, alto, color)
    return svg_doc(lado, lado, placa + sim)


# ---- Piezas de comunicación ---------------------------------------------------------------------
LEMA = "Videos y audios a texto con IA, en tu computadora."
LEMA2 = "Gratis · Sin internet · Para Windows"


def lockup_g(x, y, alto_s, color_s, color_txt, params=S_NORMAL):
    """Lockup horizontal colocado en (x, y) con la S de `alto_s`; devuelve (svg, ancho)."""
    p = palabra(100 * alto_s / (1.4 * palabra(100).cap))
    C = p.cap
    sim, ancho_s = g_simbolo(params, x, y, alto_s, color_s)
    sep = 0.5 * C
    return sim + p.g(x + ancho_s + sep, y + alto_s / 2 + C / 2, color_txt), ancho_s + sep + p.ancho


def ancho_lockup(alto_s):
    p = palabra(100 * alto_s / (1.4 * palabra(100).cap))
    return ancho_simbolo(S_NORMAL, alto_s) + 0.5 * p.cap + p.ancho


def pieza_horizontal(ancho, alto, alto_s, lema=True, fondo=NOCHE, chips=True):
    """Imagen para compartir (OG / GitHub / portadas): lockup + lema centrados sobre fondo oscuro."""
    t1 = Texto("Inter_24pt-Medium.ttf", LEMA, alto_s * 0.36) if lema else None
    if t1 and t1.ancho > 0.72 * ancho:      # que el lema no toque los bordes
        t1 = Texto("Inter_24pt-Medium.ttf", LEMA, alto_s * 0.36 * 0.72 * ancho / t1.ancho)
    t2 = Texto("Inter_24pt-SemiBold.ttf", LEMA2, alto_s * 0.26) if lema and chips else None
    al = ancho_lockup(alto_s)
    bloque = alto_s + ((alto_s * 0.55 + t1.cap) if t1 else 0) + ((alto_s * 0.42 + t2.cap) if t2 else 0)
    y = (alto - bloque) / 2
    cuerpo, _ = lockup_g((ancho - al) / 2, y, alto_s, VIOLETA, NIEVE)
    y += alto_s
    if t1:
        y += alto_s * 0.55 + t1.cap
        cuerpo += t1.g((ancho - t1.ancho) / 2, y, GRIS)
    if t2:
        y += alto_s * 0.42 + t2.cap
        cuerpo += t2.g((ancho - t2.ancho) / 2, y, VIOLETA)
    return svg_doc(ancho, alto, cuerpo, fondo=fondo)


def perfil(lado=1080):
    """Foto de perfil: S blanca sobre violeta, segura dentro del círculo."""
    return mosaico(S_BLANCA, lado=lado, sangrado=True, escala=0.5)


def instalador(ancho, alto):
    """Panel lateral del instalador (WizardImageFile): fondo de la app, S violeta y nombre."""
    p = Texto("Inter_24pt-Bold.ttf", "Subtexto", ancho * 0.2, tracking=-0.018)
    alto_s = ancho * 0.42
    ancho_s = ancho_simbolo(S_NORMAL, alto_s)
    y = alto * 0.36 - alto_s / 2
    sim, _ = g_simbolo(S_NORMAL, (ancho - ancho_s) / 2, y, alto_s, VIOLETA)
    base = y + alto_s + p.cap * 1.3 + p.cap
    return svg_doc(ancho, alto, sim + p.g((ancho - p.ancho) / 2, base, NIEVE), fondo=NOCHE)


# ---- Render a PNG con Chrome / Edge (sin dependencias) --------------------------------------------
NAVEGADORES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def navegador():
    for n in NAVEGADORES + [shutil.which("chrome") or "", shutil.which("msedge") or ""]:
        if n and os.path.exists(n):
            return n
    raise SystemExit("No se encontró Chrome ni Edge para pasar los SVG a PNG.")


def render(svg_ruta, png_ruta, ancho, alto=None):
    """Rasteriza el SVG exactamente a ancho×alto (fondo transparente)."""
    alto = alto or ancho
    lienzo_w, lienzo_h = max(ancho, 320), max(alto, 320)
    with tempfile.TemporaryDirectory() as tmp:
        html = Path(tmp) / "p.html"
        shutil.copy(svg_ruta, Path(tmp) / "l.svg")
        html.write_text(
            "<!doctype html><html><head><style>html,body{margin:0;background:transparent;overflow:hidden}"
            f"img{{display:block;width:{ancho}px;height:{alto}px}}</style></head>"
            '<body><img src="l.svg"></body></html>', encoding="utf-8")
        foto = Path(tmp) / "s.png"
        cmd = [navegador(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               "--no-default-browser-check", "--force-device-scale-factor=1",
               "--default-background-color=00000000", f"--window-size={lienzo_w},{lienzo_h}",
               f"--screenshot={foto}", f"--user-data-dir={Path(tmp) / 'perfil'}", html.as_uri()]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        limite = time.time() + 60
        while time.time() < limite and not (foto.exists() and foto.stat().st_size > 0):
            time.sleep(0.2)
        time.sleep(0.3)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        if not foto.exists():
            raise RuntimeError(f"No se pudo renderizar {svg_ruta}")
        Image.open(foto).convert("RGBA").crop((0, 0, ancho, alto)).save(png_ruta, optimize=True)
    return png_ruta


# ---- Construcción ------------------------------------------------------------------------------
def construir(con_png=True, aplicar=False):
    logo, web, redes, win = MARCA / "logo", MARCA / "web", MARCA / "redes", MARCA / "windows"
    for c in (logo, web, redes, win):
        c.mkdir(parents=True, exist_ok=True)

    # 1. Masters
    escribir(logo / "simbolo.svg", solo_simbolo(VIOLETA))
    escribir(logo / "simbolo-negro.svg", solo_simbolo(NEGRO))
    escribir(logo / "simbolo-blanco.svg", solo_simbolo(BLANCO, S_BLANCA))
    escribir(logo / "simbolo-chico.svg", solo_simbolo(VIOLETA, S_CHICA))
    combinaciones = {
        "color": (VIOLETA, TINTA, S_NORMAL),          # sobre fondos claros
        "sobre-oscuro": (VIOLETA, NIEVE, S_NORMAL),   # sobre fondos oscuros
        "negro": (NEGRO, NEGRO, S_NORMAL),
        "blanco": (BLANCO, BLANCO, S_BLANCA),
        "violeta": (VIOLETA, VIOLETA, S_NORMAL),
    }
    for nombre, (cs, ct, prm) in combinaciones.items():
        escribir(logo / f"horizontal-{nombre}.svg", horizontal(cs, ct, prm))
        escribir(logo / f"apilado-{nombre}.svg", apilado(cs, ct, prm))
    for nombre, col in (("color", TINTA), ("sobre-oscuro", NIEVE), ("negro", NEGRO), ("blanco", BLANCO)):
        escribir(logo / f"palabra-{nombre}.svg", solo_palabra(col))
    escribir(logo / "icono-app.svg", mosaico(S_BLANCA, inset=0.03, escala=0.56))
    escribir(logo / "icono-app-chico.svg", mosaico(S_CHICA, inset=0.0, radio=0.2, escala=0.7))

    # 2. Web
    escribir(web / "favicon.svg", mosaico(S_CHICA, radio=0.2, escala=0.7))
    escribir(web / "logo-claro.svg", horizontal(VIOLETA, TINTA))        # encabezado sobre fondo claro
    escribir(web / "logo-oscuro.svg", horizontal(VIOLETA, NIEVE))       # encabezado sobre fondo oscuro
    escribir(web / "og-image.svg", pieza_horizontal(1200, 630, 140))
    escribir(web / "github-social-preview.svg", pieza_horizontal(1280, 640, 145))
    escribir(web / "_apple-touch.svg", mosaico(S_BLANCA, sangrado=True, escala=0.5))
    escribir(web / "_maskable.svg", mosaico(S_BLANCA, sangrado=True, escala=0.42))
    escribir(web / "_icono.svg", mosaico(S_BLANCA, inset=0.0, radio=0.22, escala=0.56))
    escribir(web / "site.webmanifest", json.dumps({
        "name": "Subtexto", "short_name": "Subtexto",
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "theme_color": NOCHE, "background_color": NOCHE, "display": "standalone",
    }, indent=2, ensure_ascii=False) + "\n")
    escribir(web / "head-snippet.html", """<!-- Íconos de Subtexto: copia estos archivos a la raíz del sitio -->
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#111827">
<!-- Vista previa al compartir (usa la URL completa del sitio) -->
<meta property="og:image" content="https://TU-DOMINIO/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
""")

    # 3. Redes
    escribir(redes / "perfil.svg", perfil(1080))
    escribir(redes / "portada-x-1500x500.svg", pieza_horizontal(1500, 500, 120, chips=False))
    escribir(redes / "portada-facebook-1640x624.svg", pieza_horizontal(1640, 624, 130, chips=False))
    # YouTube: la zona segura (visible en todos los dispositivos) es 1546×423 al centro
    escribir(redes / "portada-youtube-2560x1440.svg", pieza_horizontal(2560, 1440, 150, chips=False))

    # 4. Windows
    escribir(win / "instalador-panel.svg", instalador(164, 314))
    escribir(win / "instalador-panel-2x.svg", instalador(328, 628))

    if not con_png:
        print("SVG listos en", MARCA)
        return

    # ---- PNG ----
    print("Renderizando PNG…")
    for nombre in ("simbolo", "horizontal-color", "horizontal-sobre-oscuro", "horizontal-blanco",
                   "apilado-color", "apilado-sobre-oscuro", "icono-app"):
        svg = logo / f"{nombre}.svg"
        ancho = 1024 if nombre.startswith(("simbolo", "icono")) else 1600
        txt = svg.read_text(encoding="utf-8")
        vb = [float(v) for v in txt.split('viewBox="')[1].split('"')[0].split()]
        render(svg, logo / f"{nombre}.png", ancho, round(ancho * vb[3] / vb[2]))

    # Íconos: cada tamaño se rasteriza a su tamaño real; ≤32 px usa el corte chico.
    def icono_png(t):
        fuente_svg = logo / ("icono-app-chico.svg" if t <= 32 else "icono-app.svg")
        return Image.open(render(fuente_svg, Path(tempfile.gettempdir()) / f"subtexto-{t}.png", t))

    tam_ico = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = {t: icono_png(t) for t in tam_ico + [180, 192, 512, 1024]}
    ico = win / "icono.ico"
    imgs[256].save(ico, format="ICO", sizes=[(t, t) for t in tam_ico],
                   append_images=[imgs[t] for t in tam_ico if t != 256])
    imgs[1024].save(win / "icono.png")
    imgs[64].save(win / "logo_64.png")
    render(win / "instalador-panel.svg", win / "instalador-panel.png", 164, 314)
    render(win / "instalador-panel-2x.svg", win / "instalador-panel-2x.png", 328, 628)

    # Web
    imgs_fav = {t: imgs[t] for t in (16, 32, 48)}
    imgs_fav[48].save(web / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)],
                      append_images=[imgs_fav[16], imgs_fav[32]])
    for t in (16, 32, 48):
        imgs[t].save(web / f"favicon-{t}.png")
    render(web / "_icono.svg", web / "icon-192.png", 192)
    render(web / "_icono.svg", web / "icon-512.png", 512)
    render(web / "_apple-touch.svg", web / "apple-touch-icon.png", 180)
    render(web / "_maskable.svg", web / "maskable-512.png", 512)
    render(web / "logo-claro.svg", web / "logo-claro.png", 640, _alto(web / "logo-claro.svg", 640))
    render(web / "logo-oscuro.svg", web / "logo-oscuro.png", 640, _alto(web / "logo-oscuro.svg", 640))
    render(web / "og-image.svg", web / "og-image.png", 1200, 630)
    render(web / "github-social-preview.svg", web / "github-social-preview.png", 1280, 640)

    # Redes
    render(redes / "perfil.svg", redes / "perfil.png", 1080)
    render(redes / "portada-x-1500x500.svg", redes / "portada-x-1500x500.png", 1500, 500)
    render(redes / "portada-facebook-1640x624.svg", redes / "portada-facebook-1640x624.png", 1640, 624)
    render(redes / "portada-youtube-2560x1440.svg", redes / "portada-youtube-2560x1440.png", 2560, 1440)

    if not aplicar:
        print("Listo: todo quedó en brand/. Para ponerlo en el programa: --aplicar")
        return
    # Copiar a las rutas que usa el programa (mismos nombres que antes: el build no cambia).
    # Falta a mano: la línea WizardImageFile en build/instalador.iss (ver brand/GUIA-DE-MARCA.md).
    shutil.copy(ico, ASSETS / "icono.ico")
    shutil.copy(win / "icono.png", ASSETS / "icono.png")
    shutil.copy(win / "logo_64.png", ASSETS / "logo_64.png")
    shutil.copy(win / "instalador-panel.png", BUILD / "instalador-panel.png")
    shutil.copy(win / "instalador-panel-2x.png", BUILD / "instalador-panel-2x.png")
    # Logo horizontal del encabezado de la app (600 px de ancho: se ve nítido hasta al 300 %).
    horizontal = Image.open(MARCA / "logo" / "horizontal-sobre-oscuro.png")
    horizontal.resize((600, round(600 * horizontal.height / horizontal.width)), Image.LANCZOS).save(
        ASSETS / "logo-horizontal.png", optimize=True)
    print("Listo: brand/ y assets/ actualizados.")


def _alto(svg, ancho):
    vb = [float(v) for v in svg.read_text(encoding="utf-8").split('viewBox="')[1].split('"')[0].split()]
    return round(ancho * vb[3] / vb[2])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sin-png", action="store_true", help="solo genera los SVG")
    ap.add_argument("--aplicar", action="store_true",
                    help="copia el ícono a assets/ y las imágenes del instalador a build/")
    a = ap.parse_args()
    construir(con_png=not a.sin_png, aplicar=a.aplicar)
