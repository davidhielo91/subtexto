"""Subtexto: transcribe el audio de un video o audio usando Whisper (faster-whisper) en tu PC.

Uso:
    python transcribir.py "C:\\ruta\\video.mp4"
    python transcribir.py video.mp4 --salida "D:\\Transcripciones\\video.txt"
    python transcribir.py video.mp4 --modelo large-v3-turbo --idioma es
    python transcribir.py video.mp4 --palabras   # timestamps por palabra
    python transcribir.py video.mp4 --vtt        # también subtítulos .vtt

    python transcribir.py video.mp4 --vertical   # subtítulos de 1 línea corta (Reels, TikTok)
    python transcribir.py video.mp4 --palabras-clave "Subtexto, Ciudad Juárez"

Genera junto al video (sin sobrescribir: si ya existen, usa "video (2).txt", etc.):
    video.txt          -> transcripción con timestamps [mm:ss → mm:ss]
    video.srt          -> subtítulos en líneas cortas (opcional, se desactiva con --sin-srt)
    video.vtt          -> subtítulos para web (opcional, con --vtt)
    video - texto.txt  -> solo el texto, en párrafos y sin tiempos (opcional, con --texto)
"""

import argparse
import io
import logging
import os
import shutil
import site
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# Carpeta del programa: junto a Subtexto.exe si está instalado, o la del código si se corre con Python.
# Ahí el instalador deja los modelos (modelos/) y las librerías de la tarjeta NVIDIA (cuda/).
CARPETA_APP = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
MODELO_POR_DEFECTO = "large-v3-turbo"
# Los mismos archivos que descarga faster-whisper.
ARCHIVOS_MODELO = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
# Cómo se arman los subtítulos: horizontal (YouTube, 2 líneas) o vertical (Reels/TikTok, 1 línea corta).
FORMATOS_SUBTITULOS = {
    "horizontal": dict(max_car=42, max_lineas=2, max_seg=6.0),
    "vertical": dict(max_car=24, max_lineas=1, max_seg=2.5),
}
# Archivo con solo el texto corrido: "mi_video - texto.txt".
SUFIJO_TEXTO = " - texto.txt"

registro = logging.getLogger("subtexto")


class Detenido(Exception):
    """Se pidió detener antes de que hubiera algo que guardar (por ejemplo, mientras se leía el audio)."""


def _se_pidio_detener(detener):
    return detener is not None and detener.is_set()


def registrar_dlls_cuda():
    """Agrega al PATH las DLLs de cuBLAS/cuDNN (del instalador o instaladas por pip)."""
    bases = [CARPETA_APP / "cuda"]
    if hasattr(site, "getsitepackages"):
        bases += [Path(b) for b in site.getsitepackages()]
    for base in bases:
        nvidia = base / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in nvidia.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


registrar_dlls_cuda()


# ---------- formato de tiempos ----------
def formato_tiempo(segundos, sep="."):
    ms = int(round(segundos * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def tiempo_corto(segundos):
    """Minutos:segundos (mm:ss), o h:mm:ss si el video pasa de una hora."""
    total = int(segundos)
    h, resto = divmod(total, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ---------- subtítulos ----------
def palabras_de_segmento(inicio, fin, texto):
    """Respaldo cuando un tramo llega sin tiempos por palabra: reparte el tiempo según el largo de cada una."""
    palabras = texto.split()
    if not palabras:
        return []
    total = sum(len(p) for p in palabras)
    duracion = max(fin - inicio, 0)
    resultado, t = [], inicio
    for p in palabras:
        dt = duracion * len(p) / total
        resultado.append((t, t + dt, p))
        t += dt
    return resultado


def partir_lineas(texto, max_car=42):
    """Parte un texto en líneas de máximo max_car caracteres, lo más parejas posible si son dos."""
    if len(texto) <= max_car:
        return [texto]
    palabras = texto.split()
    # Dos líneas: el corte más cercano a la mitad en el que ambas quepan.
    mejor = None
    for i in range(1, len(palabras)):
        a, b = " ".join(palabras[:i]), " ".join(palabras[i:])
        if len(a) <= max_car and len(b) <= max_car:
            dif = abs(len(a) - len(b))
            if mejor is None or dif < mejor[0]:
                mejor = (dif, [a, b])
    if mejor:
        return mejor[1]
    # Más de dos líneas (o una palabra larguísima): llenado simple.
    lineas, actual = [], ""
    for p in palabras:
        if actual and len(actual) + 1 + len(p) > max_car:
            lineas.append(actual)
            actual = p
        else:
            actual = f"{actual} {p}" if actual else p
    lineas.append(actual)
    return lineas


def armar_subtitulos(palabras, max_car=42, max_lineas=2, max_seg=6.0, pausa=0.7):
    """Agrupa palabras (inicio, fin, texto) en subtítulos cortos: [(inicio, fin, "línea1\\nlínea2"), ...].

    Corta cuando el texto ya no cabe en max_lineas de max_car caracteres, cuando el subtítulo pasaría
    de max_seg segundos, cuando hay una pausa larga, al terminar una oración o en una coma si el
    subtítulo ya va algo lleno (para que no quede "…y lo / mejor es…").
    """
    bloques, actual = [], []

    def cerrar():
        if actual:
            texto = " ".join(p[2] for p in actual)
            bloques.append((actual[0][0], actual[-1][1], "\n".join(partir_lineas(texto, max_car))))
            actual.clear()

    for palabra in palabras:
        inicio, fin, texto = palabra
        texto = texto.strip()
        if not texto:
            continue
        palabra = (inicio, fin, texto)
        if actual:
            anterior = actual[-1]
            hasta_ahora = " ".join(p[2] for p in actual)
            if (inicio - anterior[1] >= pausa
                    or fin - actual[0][0] > max_seg
                    or len(partir_lineas(f"{hasta_ahora} {texto}", max_car)) > max_lineas
                    or anterior[2][-1] in ".?!…"
                    or (anterior[2][-1] in ",;:" and len(hasta_ahora) >= max_car * 0.75)):
                cerrar()
        actual.append(palabra)
    cerrar()
    return bloques


def texto_srt(bloques):
    return "\n".join(f"{i}\n{formato_tiempo(a, ',')} --> {formato_tiempo(b, ',')}\n{t}\n"
                     for i, (a, b, t) in enumerate(bloques, 1))


def texto_vtt(bloques):
    return "WEBVTT\n\n" + "\n".join(f"{formato_tiempo(a)} --> {formato_tiempo(b)}\n{t}\n" for a, b, t in bloques)


# ---------- archivos ----------
def rutas_libres(base, extensiones=(".txt",)):
    """Rutas para cada extensión que no pisen archivos existentes.

    Si "video.txt" (o "video.srt"…) ya existe, prueba "video (2)", "video (3)"… usando el mismo número
    para todo el juego de archivos.
    """
    base = Path(base)
    n = 1
    while True:
        nombre = base.stem if n == 1 else f"{base.stem} ({n})"
        rutas = {ext: base.with_name(nombre + ext) for ext in extensiones}
        if not any(r.exists() for r in rutas.values()):
            return rutas
        n += 1


def es_repeticion(frase, anterior, minimo_palabras=6):
    """Una frase larga idéntica a la anterior casi siempre es un bucle de la IA."""
    normal = " ".join(frase.lower().split())
    return normal == anterior and len(normal.split()) >= minimo_palabras


# ---------- audio ----------
def audio_con_ffmpeg(ffmpeg, ruta, detener=None):
    """Lee el audio con ffmpeg en bloques, para poder detenerlo a medio camino."""
    cmd = [ffmpeg, "-nostdin", "-loglevel", "error", "-i", str(ruta),
           "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    datos = bytearray()
    errores = []
    # Sin CREATE_NO_WINDOW se abre una ventana negra de consola mientras ffmpeg trabaja.
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          creationflags=subprocess.CREATE_NO_WINDOW) as proceso:
        # Los mensajes de error se leen aparte para que ffmpeg nunca se quede esperando.
        lector = threading.Thread(target=lambda: errores.append(proceso.stderr.read()), daemon=True)
        lector.start()
        try:
            while True:
                if _se_pidio_detener(detener):
                    raise Detenido()
                bloque = proceso.stdout.read(1 << 20)  # ~16 segundos de audio
                if not bloque:
                    break
                datos += bloque
        except BaseException:
            proceso.kill()
            raise
        proceso.wait()
        lector.join(timeout=5)
    if proceso.returncode != 0:
        raise RuntimeError(b"".join(errores).decode(errors="ignore").strip())
    return np.frombuffer(bytes(datos[: len(datos) // 4 * 4]), dtype=np.float32)


def audio_con_pyav(ruta, detener=None):
    """Lee el audio con PyAV (la copia de FFmpeg que ya trae faster-whisper)."""
    import av

    with av.open(str(ruta)) as contenedor:
        if not contenedor.streams.audio:
            return np.zeros(0, dtype=np.float32)
        convertidor = av.AudioResampler(format="flt", layout="mono", rate=16000)
        partes = []
        for cuadro in contenedor.decode(audio=0):
            if _se_pidio_detener(detener):
                raise Detenido()
            partes += [c.to_ndarray().reshape(-1) for c in convertidor.resample(cuadro)]
        partes += [c.to_ndarray().reshape(-1) for c in convertidor.resample(None)]
    return np.concatenate(partes) if partes else np.zeros(0, dtype=np.float32)


def extraer_audio(ruta, detener=None):
    """Extrae el audio del video: mono, 16 kHz, float32 (lo que espera Whisper).

    Usa ffmpeg si está instalado; si no, PyAV (así el programa instalado no necesita ffmpeg).
    Si se activa detener (threading.Event) mientras lee, lanza Detenido.
    """
    ffmpeg = shutil.which("ffmpeg")
    try:
        audio = audio_con_ffmpeg(ffmpeg, ruta, detener) if ffmpeg else audio_con_pyav(ruta, detener)
    except Detenido:
        raise
    except Exception as e:
        registro.exception("No se pudo leer el audio")
        raise RuntimeError("No se pudo leer el audio del archivo. Puede estar dañado o no ser un video/audio "
                           f"compatible.\n(detalle: {e})") from e
    if audio.size == 0:
        raise RuntimeError("El archivo no tiene audio (o la pista de audio está vacía).")
    return audio


# ---------- modelo ----------
def _clase_progreso(callback):
    """Clase tipo tqdm que, en vez de dibujar una barra, avisa cuántos bytes van descargados."""
    from tqdm.auto import tqdm

    class Progreso(tqdm):
        def __init__(self, *args, **kwargs):
            kwargs["file"] = io.StringIO()
            kwargs.pop("disable", None)
            super().__init__(*args, **kwargs)

        def update(self, n=1):
            resultado = super().update(n)
            # Solo la barra de bytes escritos (la otra cuenta los bytes de red y la otra archivos).
            if self.unit == "B" and not str(self.desc).startswith("Downloading") and self.total:
                callback(self.n, self.total)
            return resultado

    return Progreso


def ruta_modelo(nombre, progreso_descarga=None, log=print):
    """Carpeta local del modelo. Si no está ni en modelos\\ (instalador) ni en la caché, lo descarga.

    progreso_descarga(bajado, total) recibe los bytes de la descarga, si hay que descargar.
    """
    local = CARPETA_APP / "modelos" / nombre
    if (local / "model.bin").is_file():
        return str(local)

    from faster_whisper.utils import _MODELS
    from huggingface_hub import snapshot_download

    repo = _MODELS.get(nombre)
    if repo is None:
        raise ValueError(f"Modelo desconocido: '{nombre}'. Opciones: {', '.join(_MODELS)}")
    try:
        return snapshot_download(repo, allow_patterns=ARCHIVOS_MODELO, local_files_only=True)
    except Exception:
        pass  # no está en la caché: hay que descargarlo

    log(f"Descargando el modelo '{nombre}' (solo pasa la primera vez que lo usas)...")
    try:
        return snapshot_download(repo, allow_patterns=ARCHIVOS_MODELO,
                                 tqdm_class=_clase_progreso(progreso_descarga) if progreso_descarga else None)
    except Exception as e:
        registro.exception("Falló la descarga del modelo %s", nombre)
        raise RuntimeError(f"No se pudo descargar el modelo '{nombre}'. Revisa tu conexión a internet "
                           f"y vuelve a intentarlo.\n(detalle: {e})") from e


def explicar_error_gpu(e):
    """Traduce un error de la tarjeta de video a algo entendible."""
    texto = str(e).lower()
    if "out of memory" in texto:
        return "La tarjeta de video no tiene memoria suficiente para este modelo (prueba uno más pequeño)."
    if any(p in texto for p in ("cublas", "cudnn", "nvrtc", ".dll", "library", "librería")):
        return ("No encontré las librerías de NVIDIA. Vuelve a abrir el instalador de Subtexto y deja "
                "marcada la opción de aceleración NVIDIA.")
    if any(p in texto for p in ("driver", "no cuda", "cuda-capable", "cuda device")):
        return "No se pudo usar la tarjeta NVIDIA: revisa que sus drivers estén actualizados."
    return f"No se pudo usar la tarjeta NVIDIA ({e})."


def tipos_gpu():
    """Modos de la tarjeta NVIDIA a probar, del más rápido al más compatible ([] si no hay tarjeta)."""
    import ctranslate2

    try:
        if ctranslate2.get_cuda_device_count() == 0:
            return []
        soportados = ctranslate2.get_supported_compute_types("cuda")
    except Exception:
        return []
    return [t for t in ("float16", "int8_float16") if t in soportados] or ["float16", "int8_float16"]


def cargar_modelo(nombre, dispositivo="auto", log=print, progreso_descarga=None):
    """Carga el modelo en la tarjeta NVIDIA si se puede; si no, en el procesador (CPU).

    En la tarjeta prueba primero el modo rápido (float16) y luego el compatible (int8_float16), que sirve
    en tarjetas más viejas.
    """
    from faster_whisper import WhisperModel

    ruta = ruta_modelo(nombre, progreso_descarga, log)
    if dispositivo in ("auto", "cuda"):
        tipos = tipos_gpu() if dispositivo == "auto" else ["float16", "int8_float16"]
        error = None
        for tipo in tipos:
            try:
                modelo = WhisperModel(ruta, device="cuda", compute_type=tipo)
                # Si faltan librerías de CUDA, el error aparece al transcribir y no al cargar:
                # se hace una prueba con 1 segundo de silencio para detectarlo aquí.
                segmentos, _ = modelo.transcribe(np.zeros(16000, dtype=np.float32), language="en")
                list(segmentos)
                if tipo != "float16":
                    log("[aviso] Tu tarjeta no soporta el modo más rápido; uso el modo compatible.")
                registro.info("Modelo %s en CUDA (%s)", nombre, tipo)
                return modelo, "cuda"
            except Exception as e:
                registro.warning("Falló CUDA %s: %s", tipo, e)
                error = e
                # Si faltan librerías, el modo compatible tampoco va a funcionar (si faltó memoria, sí
                # vale la pena: int8_float16 usa como la mitad).
                if any(p in str(e).lower() for p in ("cublas", "cudnn", "nvrtc", ".dll")):
                    break
        if dispositivo == "cuda":
            raise RuntimeError(explicar_error_gpu(error) if error else "No se encontró una tarjeta NVIDIA.")
        if error is not None:
            log(f"[aviso] {explicar_error_gpu(error)} Uso el procesador (más lento).")
    registro.info("Modelo %s en CPU", nombre)
    return WhisperModel(ruta, device="cpu", compute_type="int8"), "cpu"


# ---------- transcripción ----------
@dataclass
class Resultado:
    archivos: list = field(default_factory=list)  # rutas generadas (la primera es el .txt)
    texto: str = ""                                # texto corrido, sin tiempos (para copiar)
    completo: bool = True


def transcribir_video(modelo, video, nombre_modelo="", idioma=None, palabras=False, srt=True, vtt=False,
                      salida=None, carpeta=None, log=print, progreso=None, detener=None,
                      palabras_clave=None, formato="horizontal", texto_limpio=False):
    """Transcribe un video con un modelo ya cargado y guarda los archivos. Devuelve un Resultado.

    salida: ruta del .txt; carpeta: dónde guardar (por defecto, junto al video). Nunca sobrescribe.
    progreso(fraccion) se llama con valores entre 0 y 1 conforme avanza.
    detener: threading.Event; si se activa, se para y se guarda lo transcrito, marcado como incompleto.
    Si se activa mientras se lee el audio (todavía no hay nada que guardar), lanza Detenido.
    palabras_clave: nombres propios o marcas que la IA debe reconocer (ej. "Subtexto, Ciudad Juárez").
    formato: "horizontal" (2 líneas, YouTube) o "vertical" (1 línea corta, Reels/TikTok).
    texto_limpio: guarda también "video - texto.txt" con solo el texto, en párrafos.
    """
    video = Path(video)
    if not video.is_file():
        raise FileNotFoundError(f"No existe el archivo: {video}")
    if formato not in FORMATOS_SUBTITULOS:
        raise ValueError(f"Formato de subtítulos desconocido: '{formato}'. "
                         f"Opciones: {', '.join(FORMATOS_SUBTITULOS)}")
    base = Path(salida) if salida else Path(carpeta or video.parent) / f"{video.stem}.txt"
    base.parent.mkdir(parents=True, exist_ok=True)
    extensiones = [".txt"] + [".srt"] * srt + [".vtt"] * vtt + [SUFIJO_TEXTO] * texto_limpio

    inicio = time.time()
    log("Leyendo el audio…")
    audio = extraer_audio(video, detener)
    if _se_pidio_detener(detener):
        raise Detenido()
    if progreso:
        progreso(0.0)
    palabras_clave = (palabras_clave or "").strip() or None
    segmentos, info = modelo.transcribe(
        audio,
        language=idioma,
        # Nombres propios y marcas: se le dan a la IA como pista en cada tramo del audio.
        hotwords=palabras_clave,
        vad_filter=True,
        # Los subtítulos cortos se arman con el tiempo de cada palabra.
        word_timestamps=palabras or srt or vtt,
        beam_size=5,
        # Sin esto, si la IA se equivoca en un tramo usa ese error como pista para el siguiente
        # y puede quedarse repitiendo la misma frase hasta el final del video.
        condition_on_previous_text=False,
    )
    # Los nombres se eligen justo antes de escribir, para no apartar un "(2)" si se detuvo antes.
    rutas = rutas_libres(base, extensiones)
    log(f"Idioma: {info.language} ({info.language_probability:.0%}) | Duración: {tiempo_corto(info.duration)}")
    registro.info("Transcribiendo %s (%s, %s)", video.suffix, info.language, tiempo_corto(info.duration))

    lineas_txt = []
    todas_palabras = []
    parrafos, frases = [], []
    anterior, fin_anterior = "", 0.0
    repetidos = 0
    interrupcion = None

    try:
        for seg in segmentos:
            if detener is not None and detener.is_set():
                interrupcion = "detenido"
                break
            texto = seg.text.strip()
            rango = f"[{tiempo_corto(seg.start)} → {tiempo_corto(seg.end)}]"
            pct = min(seg.end / info.duration, 1) if info.duration else 0
            if progreso:
                progreso(pct)

            # Red de seguridad contra bucles de la IA.
            if es_repeticion(texto, anterior):
                repetidos += 1
                log(f"  {pct:6.1%} {rango} [descartado: repetía la frase anterior]")
                continue
            anterior = " ".join(texto.lower().split())

            lineas_txt.append(f"{rango}  {texto}")
            if palabras and seg.words:
                for w in seg.words:
                    lineas_txt.append(f"      {tiempo_corto(w.start)}  {w.word.strip()}")
            if seg.words:
                todas_palabras += [(w.start, w.end, w.word) for w in seg.words]
            else:
                todas_palabras += palabras_de_segmento(seg.start, seg.end, texto)
            # Texto corrido: un párrafo nuevo después de una pausa larga.
            if frases and seg.start - fin_anterior > 2.0:
                parrafos.append(" ".join(frases))
                frases = []
            frases.append(texto)
            fin_anterior = seg.end
            log(f"  {pct:6.1%} {rango} {texto}")
    except BaseException as e:
        interrupcion = "detenido" if isinstance(e, KeyboardInterrupt) else "error"
        raise
    finally:
        # Siempre se guarda lo que haya, aunque se detenga o falle a medio camino.
        encabezado = [
            f"Transcripción de: {video.name}",
            f"Idioma: {info.language} | Duración: {tiempo_corto(info.duration)} | Modelo: {nombre_modelo}",
        ]
        if interrupcion:
            motivo = "detenido" if interrupcion == "detenido" else "se interrumpió por un error"
            encabezado.append(f"[INCOMPLETO: {motivo} en {tiempo_corto(fin_anterior)} "
                              f"de {tiempo_corto(info.duration)}]")
        rutas[".txt"].write_text("\n".join(encabezado + [""] + lineas_txt) + "\n", encoding="utf-8")
        bloques = armar_subtitulos(todas_palabras, **FORMATOS_SUBTITULOS[formato])
        if srt:
            rutas[".srt"].write_text(texto_srt(bloques), encoding="utf-8")
        if vtt:
            rutas[".vtt"].write_text(texto_vtt(bloques), encoding="utf-8")
        texto_corrido = "\n\n".join(parrafos + ([" ".join(frases)] if frases else []))
        if texto_limpio:
            aviso = [encabezado[-1], ""] if interrupcion else []
            rutas[SUFIJO_TEXTO].write_text("\n".join(aviso + [texto_corrido]) + "\n", encoding="utf-8")

    if repetidos:
        log(f"Aviso: se descartaron {repetidos} frase(s) repetida(s). Revisa esos minutos en el video.")
    if interrupcion:
        log(f"Detenido: se guardó lo transcrito hasta {tiempo_corto(fin_anterior)}.")
    else:
        if progreso:
            progreso(1.0)
        log(f"Listo en {time.time() - inicio:.1f}s")
    return Resultado(list(rutas.values()), texto_corrido, interrupcion is None)


def main():
    # Si la salida va a un archivo o a una consola sin UTF-8, que las flechas "→" no detengan el programa.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    p = argparse.ArgumentParser(description="Transcribe un video local con IA (Whisper) en tu PC.")
    p.add_argument("video", help="Ruta al archivo de video o audio")
    p.add_argument("--modelo", default=MODELO_POR_DEFECTO,
                   help=f"tiny, base, small, medium, large-v3, large-v3-turbo (default: {MODELO_POR_DEFECTO})")
    p.add_argument("--idioma", default=None, help="Código de idioma, ej. es, en. Por defecto se detecta solo")
    p.add_argument("--dispositivo", default="auto", choices=["auto", "cuda", "cpu"])
    p.add_argument("--salida", default=None, help="Ruta del .txt de salida (default: junto al video)")
    p.add_argument("--palabras", action="store_true", help="Incluir timestamps por palabra en el .txt")
    p.add_argument("--sin-srt", action="store_true", help="No generar archivo .srt")
    p.add_argument("--vtt", action="store_true", help="Generar también subtítulos .vtt")
    p.add_argument("--vertical", action="store_true",
                   help="Subtítulos de 1 línea corta, para video vertical (Reels, TikTok, Shorts)")
    p.add_argument("--texto", action="store_true",
                   help='Guardar también "video - texto.txt": solo el texto, en párrafos y sin tiempos')
    p.add_argument("--palabras-clave", default=None, metavar="TEXTO",
                   help='Nombres propios o marcas que debe reconocer, ej. "Subtexto, Ciudad Juárez"')
    args = p.parse_args()

    if not Path(args.video).is_file():
        sys.exit(f"No existe el archivo: {args.video}")

    print(f"Cargando modelo '{args.modelo}'...")
    try:
        modelo, disp = cargar_modelo(args.modelo, args.dispositivo)
    except (RuntimeError, ValueError) as e:
        sys.exit(str(e))
    print(f"Modelo listo en {disp.upper()}. Transcribiendo: {Path(args.video).name}  (Ctrl+C para detener)")

    try:
        resultado = transcribir_video(modelo, args.video, args.modelo, args.idioma, args.palabras,
                                      not args.sin_srt, args.vtt, args.salida,
                                      palabras_clave=args.palabras_clave,
                                      formato="vertical" if args.vertical else "horizontal",
                                      texto_limpio=args.texto)
    except KeyboardInterrupt:
        sys.exit("\nDetenido. Se guardó lo transcrito hasta ese momento (marcado como INCOMPLETO).")
    except RuntimeError as e:
        sys.exit(str(e))
    for ruta in resultado.archivos:
        print(f"Archivo: {ruta}")


if __name__ == "__main__":
    main()
