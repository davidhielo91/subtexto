"""Convierte trazos (línea central + grosor) en contornos SVG rellenos, sin strokes.

Un trazo se describe con un punto de inicio, un rumbo inicial (grados, 0 = este, 90 = sur;
coordenadas SVG con y hacia abajo) y una lista de tramos:
    ("L", largo)              recta
    ("A", radio, giro)        arco; giro > 0 gira en sentido horario en pantalla
El resultado es un contorno exacto: los desplazamientos de rectas y arcos circulares
siguen siendo rectas y arcos, así que el SVG final tiene pocos nodos y curvas limpias.
"""

import math


def _fmt(v):
    v = round(v, 3)
    return ("%g" % v) if v != int(v) else str(int(v))


def _pt(p):
    return f"{_fmt(p[0])} {_fmt(p[1])}"


def trazo(inicio, rumbo, tramos, grosor, tapa_inicio="redonda", tapa_fin="redonda"):
    """Devuelve el atributo d de un contorno cerrado para el trazo."""
    w = grosor / 2
    x, y = inicio
    th = math.radians(rumbo)
    # Para cada tramo guardamos lo necesario para recorrer los dos bordes.
    lado_a = []   # (tipo, punto_final, radio, sweep, large)
    lado_b = []
    def normal(t):
        return (-math.sin(t), math.cos(t))
    n = normal(th)
    a0 = (x + w * n[0], y + w * n[1])
    b0 = (x - w * n[0], y - w * n[1])
    puntos_b = [b0]
    for tr in tramos:
        if tr[0] == "L":
            largo = tr[1]
            x += largo * math.cos(th)
            y += largo * math.sin(th)
            n = normal(th)
            lado_a.append(("L", (x + w * n[0], y + w * n[1])))
            lado_b.append(("L", (x - w * n[0], y - w * n[1])))
        else:
            _, r, giro = tr
            k = 1 if giro > 0 else -1
            n = normal(th)
            cx, cy = x + k * r * n[0], y + k * r * n[1]
            th2 = th + math.radians(giro)
            n2 = normal(th2)
            x, y = cx - k * r * n2[0], cy - k * r * n2[1]
            large = 1 if abs(giro) > 180 else 0
            sweep = 1 if k > 0 else 0
            ra = r - k * w   # el lado A está del lado del centro cuando k > 0
            rb = r + k * w
            lado_a.append(("A", (x + w * n2[0], y + w * n2[1]), abs(ra), sweep, large))
            lado_b.append(("A", (x - w * n2[0], y - w * n2[1]), abs(rb), sweep, large))
            th = th2
        puntos_b.append(lado_b[-1][1])

    d = [f"M{_pt(a0)}"]
    for seg in lado_a:
        if seg[0] == "L":
            d.append(f"L{_pt(seg[1])}")
        else:
            _, p, r, sw, lg = seg
            d.append(f"A{_fmt(r)} {_fmt(r)} 0 {lg} {sw} {_pt(p)}")
    # tapa final: de A a B por delante
    fin_b = puntos_b[-1]
    if tapa_fin == "redonda":
        d.append(f"A{_fmt(w)} {_fmt(w)} 0 0 0 {_pt(fin_b)}")
    else:
        d.append(f"L{_pt(fin_b)}")
    # lado B hacia atrás
    for i in range(len(lado_b) - 1, -1, -1):
        seg = lado_b[i]
        destino = puntos_b[i]
        if seg[0] == "L":
            d.append(f"L{_pt(destino)}")
        else:
            _, p, r, sw, lg = seg
            d.append(f"A{_fmt(r)} {_fmt(r)} 0 {lg} {1 - sw} {_pt(destino)}")
    if tapa_inicio == "redonda":
        d.append(f"A{_fmt(w)} {_fmt(w)} 0 0 0 {_pt(a0)}")
    d.append("Z")
    return "".join(d)


def pastilla(x1, x2, y, grosor):
    """Barra horizontal con puntas redondas (línea de subtítulo)."""
    return trazo((x1, y), 0, [("L", x2 - x1)], grosor)


def anillo(cx, cy, r, grosor):
    """Anillo (usar con fill-rule evenodd)."""
    ro, ri = r + grosor / 2, r - grosor / 2
    def circ(rr):
        return (f"M{_fmt(cx - rr)} {_fmt(cy)}A{_fmt(rr)} {_fmt(rr)} 0 1 0 {_fmt(cx + rr)} {_fmt(cy)}"
                f"A{_fmt(rr)} {_fmt(rr)} 0 1 0 {_fmt(cx - rr)} {_fmt(cy)}Z")
    return circ(ro) + circ(ri)


def svg(caminos, ancho=256, alto=256, color="#000", titulo="Subtexto", evenodd=False):
    regla = ' fill-rule="evenodd"' if evenodd else ""
    cuerpo = "".join(f'<path d="{d}"/>' for d in caminos)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" role="img">'
            f'<title>{titulo}</title><g fill="{color}"{regla}>{cuerpo}</g></svg>\n')
