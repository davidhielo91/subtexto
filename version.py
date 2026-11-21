"""Versión de Subtexto: única fuente para la app y el instalador (build/construir.ps1 la lee de aquí)."""

__version__ = "1.1.1"
REPO = "davidhielo91/subtexto"


def numeros_version(texto):
    """'v1.2.0' -> (1, 2, 0). Devuelve None si no parece una versión."""
    partes = str(texto).strip().lstrip("vV").split(".")
    try:
        return tuple(int(p) for p in partes)
    except ValueError:
        return None


def es_mas_nueva(remota, actual=__version__):
    """True si la versión remota (por ejemplo, la etiqueta del release 'v1.1.0') es mayor que la actual."""
    a, b = numeros_version(remota), numeros_version(actual)
    if a is None or b is None:
        return False
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))
