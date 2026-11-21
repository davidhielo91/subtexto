"""Pruebas de las partes que no necesitan la IA: tiempos, subtítulos, nombres de archivo y versiones."""

import threading
from types import SimpleNamespace

import numpy as np
import pytest

import transcribir
from transcribir import (FORMATOS_SUBTITULOS, armar_subtitulos, es_repeticion, formato_tiempo,
                         palabras_de_segmento, partir_lineas, rutas_libres, texto_srt, texto_vtt, tiempo_corto)
from version import es_mas_nueva, numeros_version


# ---------- tiempos ----------
def test_formato_tiempo():
    assert formato_tiempo(0) == "00:00:00.000"
    assert formato_tiempo(3723.456, ",") == "01:02:03,456"
    assert formato_tiempo(59.9996) == "00:01:00.000"


def test_tiempo_corto():
    assert tiempo_corto(5) == "00:05"
    assert tiempo_corto(754.9) == "12:34"
    assert tiempo_corto(3725) == "1:02:05"


# ---------- subtítulos ----------
def palabras_seguidas(texto, dur=0.3):
    """Palabras sin pausas entre ellas, cada una de 'dur' segundos."""
    return [(i * dur, (i + 1) * dur, p) for i, p in enumerate(texto.split())]


def test_partir_lineas_cabe_en_una():
    assert partir_lineas("Hola a todos", 42) == ["Hola a todos"]


def test_partir_lineas_dos_parejas():
    lineas = partir_lineas("Hoy les voy a enseñar cómo transcribir sus videos con IA", 42)
    assert len(lineas) == 2
    assert all(len(l) <= 42 for l in lineas)
    assert abs(len(lineas[0]) - len(lineas[1])) < 15


def test_subtitulos_respetan_limites():
    texto = ("hoy les voy a enseñar cómo transcribir sus videos con inteligencia artificial y lo mejor "
             "es que todo corre en su propia computadora sin pagar nada y sin subir sus archivos a internet")
    bloques = armar_subtitulos(palabras_seguidas(texto, 0.2))
    assert len(bloques) > 1
    for inicio, fin, t in bloques:
        lineas = t.split("\n")
        assert len(lineas) <= 2
        assert all(len(l) <= 42 for l in lineas)
        assert fin - inicio <= 6.0
    # No se pierde ni se repite ninguna palabra.
    assert " ".join(b[2].replace("\n", " ") for b in bloques) == texto


def test_subtitulos_verticales_una_linea_corta():
    texto = ("hoy les voy a enseñar cómo transcribir sus videos con inteligencia artificial y lo mejor "
             "es que todo corre en su propia computadora")
    bloques = armar_subtitulos(palabras_seguidas(texto, 0.2), **FORMATOS_SUBTITULOS["vertical"])
    for inicio, fin, t in bloques:
        assert "\n" not in t
        assert len(t) <= 24
        assert fin - inicio <= 2.5
    assert " ".join(b[2] for b in bloques) == texto


def test_subtitulos_duran_maximo():
    bloques = armar_subtitulos(palabras_seguidas("uno dos tres cuatro cinco seis siete ocho", 1.0), max_seg=3.0)
    assert all(fin - inicio <= 3.0 for inicio, fin, _ in bloques)


def test_subtitulos_cortan_en_pausa():
    palabras = [(0.0, 0.3, "Hola"), (0.3, 0.6, "a"), (0.6, 0.9, "todos"), (3.0, 3.3, "bienvenidos")]
    bloques = armar_subtitulos(palabras)
    assert [b[2] for b in bloques] == ["Hola a todos", "bienvenidos"]


def test_subtitulos_cortan_al_final_de_oracion():
    bloques = armar_subtitulos(palabras_seguidas("Hola. ¿Cómo están?"))
    assert [b[2] for b in bloques] == ["Hola.", "¿Cómo están?"]


def test_subtitulos_cortan_en_coma_si_ya_van_llenos():
    bloques = armar_subtitulos(palabras_seguidas(
        "y lo mejor es que todo corre en su propia computadora, sin pagar nada y sin subir sus archivos", 0.1))
    assert bloques[0][2].replace("\n", " ") == "y lo mejor es que todo corre en su propia computadora,"
    # Una coma al principio no corta: "Hola," queda con lo que sigue.
    assert armar_subtitulos(palabras_seguidas("Hola, bienvenidos al video"))[0][2] == "Hola, bienvenidos al video"


def test_subtitulos_ignoran_palabras_vacias():
    assert armar_subtitulos([(0, 1, "  "), (1, 2, " hola ")]) == [(1, 2, "hola")]


def test_palabras_de_segmento_reparte_el_tiempo():
    palabras = palabras_de_segmento(10.0, 14.0, "uno dos tres cuatro")
    assert [p[2] for p in palabras] == ["uno", "dos", "tres", "cuatro"]
    assert palabras[0][0] == 10.0
    assert palabras[-1][1] == pytest.approx(14.0)
    assert palabras_de_segmento(0, 1, "   ") == []


def test_srt_y_vtt():
    bloques = [(0.0, 1.5, "Hola"), (61.0, 62.25, "línea uno\nlínea dos")]
    assert texto_srt(bloques) == ("1\n00:00:00,000 --> 00:00:01,500\nHola\n\n"
                                  "2\n00:01:01,000 --> 00:01:02,250\nlínea uno\nlínea dos\n")
    assert texto_vtt(bloques) == ("WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nHola\n\n"
                                  "00:01:01.000 --> 00:01:02.250\nlínea uno\nlínea dos\n")


# ---------- archivos ----------
def test_rutas_libres_sin_conflicto(tmp_path):
    rutas = rutas_libres(tmp_path / "video.txt", [".txt", ".srt"])
    assert rutas == {".txt": tmp_path / "video.txt", ".srt": tmp_path / "video.srt"}


def test_rutas_libres_no_sobrescribe(tmp_path):
    (tmp_path / "video.srt").write_text("subtítulos corregidos a mano")
    (tmp_path / "video (2).txt").write_text("otra")
    rutas = rutas_libres(tmp_path / "video.txt", [".txt", ".srt", ".vtt"])
    # Mismo número para todo el juego, saltando el (2) que ya está ocupado.
    assert rutas[".txt"].name == "video (3).txt"
    assert rutas[".srt"].name == "video (3).srt"
    assert rutas[".vtt"].name == "video (3).vtt"


def test_es_repeticion():
    frase = "Y eso es todo lo que les quería contar hoy"
    anterior = " ".join(frase.lower().split())
    assert es_repeticion(frase, anterior)
    assert es_repeticion("  y  ESO es todo lo que les quería contar hoy ", anterior)
    assert not es_repeticion("Sí.", "sí.")  # frases cortas repetidas son normales
    assert not es_repeticion("Otra frase distinta con muchas palabras aquí", anterior)


# ---------- transcripción completa (con un modelo falso) ----------
class ModeloFalso:
    def __init__(self, segmentos, duracion=30.0):
        self.segmentos = segmentos
        self.duracion = duracion

    def transcribe(self, audio, **kwargs):
        info = SimpleNamespace(language="es", language_probability=0.99, duration=self.duracion)
        return iter(self.segmentos), info


def segmento(inicio, fin, texto):
    return SimpleNamespace(start=inicio, end=fin, text=" " + texto, words=None)


@pytest.fixture
def video(tmp_path, monkeypatch):
    monkeypatch.setattr(transcribir, "extraer_audio", lambda ruta, detener=None: np.zeros(16000, dtype=np.float32))
    ruta = tmp_path / "mi video.mp4"
    ruta.write_bytes(b"")
    return ruta


def test_transcribir_genera_archivos_sin_sobrescribir(video):
    segs = [segmento(0, 2, "Hola a todos."), segmento(5, 7, "Bienvenidos.")]
    r1 = transcribir.transcribir_video(ModeloFalso(segs), video, "prueba", srt=True, vtt=True, log=lambda m: None)
    assert [p.name for p in r1.archivos] == ["mi video.txt", "mi video.srt", "mi video.vtt"]
    assert r1.completo
    assert r1.texto == "Hola a todos.\n\nBienvenidos."  # pausa larga = párrafo nuevo
    assert "[00:00 → 00:02]  Hola a todos." in r1.archivos[0].read_text(encoding="utf-8")
    assert r1.archivos[2].read_text(encoding="utf-8").startswith("WEBVTT")

    r2 = transcribir.transcribir_video(ModeloFalso(segs), video, "prueba", srt=True, log=lambda m: None)
    assert [p.name for p in r2.archivos] == ["mi video (2).txt", "mi video (2).srt"]


def test_transcribir_en_otra_carpeta(video, tmp_path):
    destino = tmp_path / "salida"
    r = transcribir.transcribir_video(ModeloFalso([segmento(0, 1, "Hola.")]), video, srt=False,
                                      carpeta=destino, log=lambda m: None)
    assert r.archivos == [destino / "mi video.txt"]


def test_detener_guarda_incompleto(video):
    detener = threading.Event()
    segs = [segmento(0, 2, "Primera frase."), segmento(2, 4, "Segunda frase."), segmento(4, 6, "Tercera.")]

    def progreso(f):
        if f >= 4 / 30:  # al empezar la segunda frase, el usuario presiona Detener
            detener.set()

    r = transcribir.transcribir_video(ModeloFalso(segs), video, srt=True, log=lambda m: None,
                                      progreso=progreso, detener=detener)
    assert not r.completo
    txt = r.archivos[0].read_text(encoding="utf-8")
    assert "[INCOMPLETO: detenido en 00:04 de 00:30]" in txt
    assert "Segunda frase." in txt
    assert "Tercera." not in txt


def test_error_a_medio_camino_guarda_lo_avanzado(video):
    def segmentos():
        yield segmento(0, 2, "Alcancé a decir esto.")
        raise RuntimeError("falló la IA")

    modelo = ModeloFalso([])
    modelo.segmentos = segmentos()
    with pytest.raises(RuntimeError):
        transcribir.transcribir_video(modelo, video, srt=False, log=lambda m: None)
    txt = video.with_suffix(".txt").read_text(encoding="utf-8")
    assert "Alcancé a decir esto." in txt
    assert "[INCOMPLETO: se interrumpió por un error en 00:02 de 00:30]" in txt


def test_descarta_frases_repetidas(video):
    frase = "Esta es una frase que se repite en bucle"
    segs = [segmento(0, 2, frase), segmento(2, 4, frase), segmento(4, 6, frase)]
    r = transcribir.transcribir_video(ModeloFalso(segs), video, srt=False, log=lambda m: None)
    assert r.archivos[0].read_text(encoding="utf-8").count(frase) == 1


class ModeloQueAnota(ModeloFalso):
    """Guarda las opciones con las que se llamó a transcribe."""

    def transcribe(self, audio, **kwargs):
        self.opciones = kwargs
        return super().transcribe(audio, **kwargs)


def test_palabras_clave_llegan_a_la_ia(video):
    modelo = ModeloQueAnota([segmento(0, 1, "Hola.")])
    transcribir.transcribir_video(modelo, video, srt=False, log=lambda m: None, palabras_clave="  Subtexto, IMSS ")
    assert modelo.opciones["hotwords"] == "Subtexto, IMSS"
    transcribir.transcribir_video(modelo, video, srt=False, log=lambda m: None, palabras_clave="   ")
    assert modelo.opciones["hotwords"] is None


def test_formato_vertical_en_el_srt(video):
    largo = "Hoy les voy a enseñar cómo transcribir sus videos con inteligencia artificial."
    r = transcribir.transcribir_video(ModeloFalso([segmento(0, 6, largo)]), video, srt=True, log=lambda m: None,
                                      formato="vertical")
    srt = r.archivos[1].read_text(encoding="utf-8")
    textos = [b.split("\n", 2)[2].strip() for b in srt.strip().split("\n\n")]
    assert len(textos) > 2
    assert all("\n" not in t and len(t) <= 24 for t in textos)
    with pytest.raises(ValueError):
        transcribir.transcribir_video(ModeloFalso([]), video, log=lambda m: None, formato="cuadrado")


def test_texto_limpio(video):
    segs = [segmento(0, 2, "Hola a todos."), segmento(5, 7, "Bienvenidos.")]
    r = transcribir.transcribir_video(ModeloFalso(segs), video, srt=False, log=lambda m: None, texto_limpio=True)
    assert [a.name for a in r.archivos] == ["mi video.txt", "mi video - texto.txt"]
    assert r.archivos[1].read_text(encoding="utf-8") == "Hola a todos.\n\nBienvenidos.\n"
    # Nunca sobrescribe: el segundo juego usa el mismo número para los dos archivos.
    r2 = transcribir.transcribir_video(ModeloFalso(segs), video, srt=False, log=lambda m: None, texto_limpio=True)
    assert [a.name for a in r2.archivos] == ["mi video (2).txt", "mi video (2) - texto.txt"]


def test_texto_limpio_al_detener_avisa_que_esta_incompleto(video):
    detener = threading.Event()
    segs = [segmento(0, 2, "Primera frase."), segmento(2, 4, "Segunda frase.")]
    r = transcribir.transcribir_video(ModeloFalso(segs), video, srt=False, log=lambda m: None, texto_limpio=True,
                                      progreso=lambda f: f > 0 and detener.set(), detener=detener)
    texto = r.archivos[1].read_text(encoding="utf-8")
    assert texto.startswith("[INCOMPLETO: detenido")
    assert "Primera frase." in texto and "Segunda frase." not in texto


def test_detener_mientras_lee_el_audio(video, monkeypatch):
    detener = threading.Event()

    def leer_audio(ruta, detener=None):
        detener.set()  # el usuario presiona Detener mientras se lee el audio
        return np.zeros(16000, dtype=np.float32)

    monkeypatch.setattr(transcribir, "extraer_audio", leer_audio)
    with pytest.raises(transcribir.Detenido):
        transcribir.transcribir_video(ModeloFalso([segmento(0, 1, "Hola.")]), video, log=lambda m: None,
                                      detener=detener)
    assert not video.with_suffix(".txt").exists()  # no deja archivos vacíos


@pytest.mark.skipif(not transcribir.shutil.which("ffmpeg"), reason="necesita ffmpeg")
def test_ffmpeg_se_detiene_a_medio_camino(tmp_path):
    """Con ffmpeg real: un audio de 10 minutos se deja de leer en cuanto se pide detener."""
    ruta = tmp_path / "largo.wav"
    transcribir.subprocess.run([transcribir.shutil.which("ffmpeg"), "-loglevel", "error", "-f", "lavfi", "-i",
                                "sine=frequency=440:duration=600", str(ruta)], check=True)
    detener = threading.Event()
    detener.set()
    with pytest.raises(transcribir.Detenido):
        transcribir.extraer_audio(ruta, detener)
    audio = transcribir.extraer_audio(ruta)
    assert abs(audio.size - 600 * 16000) < 16000


def test_pyav_lee_y_se_detiene(tmp_path):
    """Sin ffmpeg (como en el programa instalado) el audio se lee con PyAV."""
    av = pytest.importorskip("av")
    ruta = tmp_path / "corto.wav"
    with av.open(str(ruta), "w") as salida:
        pista = salida.add_stream("pcm_s16le", rate=16000, layout="mono")
        cuadro = av.AudioFrame.from_ndarray(np.zeros((1, 16000 * 3), dtype=np.int16), format="s16", layout="mono")
        cuadro.sample_rate = 16000
        for paquete in pista.encode(cuadro):
            salida.mux(paquete)
        for paquete in pista.encode(None):
            salida.mux(paquete)
    audio = transcribir.audio_con_pyav(ruta)
    assert abs(audio.size - 3 * 16000) < 1600
    detener = threading.Event()
    detener.set()
    with pytest.raises(transcribir.Detenido):
        transcribir.audio_con_pyav(ruta, detener)


# ---------- versiones ----------
def test_versiones():
    assert numeros_version("v1.2.10") == (1, 2, 10)
    assert numeros_version("beta") is None
    assert es_mas_nueva("v1.0.1", "1.0.0")
    assert es_mas_nueva("1.1", "1.0.9")
    assert not es_mas_nueva("v1.0.0", "1.0.0")
    assert not es_mas_nueva("1.0", "1.0.0")
    assert not es_mas_nueva("v0.9.9", "1.0.0")
    assert not es_mas_nueva("", "1.0.0")
