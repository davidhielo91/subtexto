"""Subtexto: interfaz gráfica para transcribir videos y audios con Whisper (Windows).

Doble clic en "Subtexto.bat" (o: .venv\\Scripts\\pythonw subtexto.pyw).
"""

import json
import logging
import logging.handlers
import os
import platform
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import filedialog

# Con pythonw no hay consola: las barras de descarga del modelo fallarían al escribir en ella.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import customtkinter as ctk

from version import REPO, __version__, es_mas_nueva

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None

# ---------- Paleta ----------
FONDO = "#111827"
PANEL = "#1A2333"
PANEL_ALTO = "#243044"
BORDE = "#334155"
VIOLETA = "#8B5CF6"
VIOLETA_HOVER = "#7C3AED"
CORAL = "#F59E70"
AZUL = "#38BDF8"
TEXTO = "#F8FAFC"
TEXTO_SUAVE = "#94A3B8"
VERDE = "#34D399"
ROJO = "#F87171"
ROJO_HOVER = "#EF4444"

MODELOS = {
    "large-v3-turbo  ·  preciso y rápido": "large-v3-turbo",
    "large-v3  ·  máxima precisión, más lento": "large-v3",
    "medium": "medium",
    "small  ·  rápido": "small",
    "base  ·  muy rápido, menos preciso": "base",
}
IDIOMAS = {
    "Detectar automáticamente": None,
    "Español": "es",
    "Inglés": "en",
    "Portugués": "pt",
    "Francés": "fr",
    "Italiano": "it",
    "Alemán": "de",
}
FORMATOS = {
    "Horizontal  ·  YouTube (2 líneas)": "horizontal",
    "Vertical  ·  Reels y TikTok (1 línea)": "vertical",
}
EJEMPLO_PALABRAS_CLAVE = "Opcional: nombres o marcas, ej. Subtexto, IMSS"
TEXTO_CARPETA_DEFECTO = "En la misma carpeta de cada video (por defecto)"
EXT_VIDEO = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv"}
EXT_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}
EXT_MEDIOS = EXT_VIDEO | EXT_AUDIO
EXTENSIONES = " ".join(f"*{e}" for e in sorted(EXT_VIDEO) + sorted(EXT_AUDIO))
CARPETA = Path(__file__).resolve().parent
# Si está instalado con Subtexto-Setup.exe, los modelos descargados quedan junto al .exe.
CARPETA_APP = Path(sys.executable).parent if getattr(sys, "frozen", False) else CARPETA
# Opciones guardadas y registro de errores (para reportar problemas; no guarda el texto transcrito).
ARCHIVO_CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "Subtexto" / "config.json"
CARPETA_REGISTRO = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Subtexto"
URL_RELEASES = f"https://github.com/{REPO}/releases/latest"
URL_API_RELEASES = f"https://api.github.com/repos/{REPO}/releases/latest"
URL_REPORTAR = f"https://github.com/{REPO}/issues/new"

registro = logging.getLogger("subtexto")


def configurar_registro():
    try:
        CARPETA_REGISTRO.mkdir(parents=True, exist_ok=True)
        manejador = logging.handlers.RotatingFileHandler(CARPETA_REGISTRO / "subtexto.log", maxBytes=1_000_000,
                                                         backupCount=2, encoding="utf-8")
    except OSError:
        return
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    registro.addHandler(manejador)
    registro.setLevel(logging.INFO)
    registro.info("Subtexto %s | Windows %s | %s", __version__, platform.version(),
                  "instalado" if getattr(sys, "frozen", False) else "desde el código")


def leer_config():
    try:
        return json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def modelo_inicial():
    """El primer modelo de la lista que ya esté descargado por el instalador (o el primero)."""
    for etiqueta, nombre in MODELOS.items():
        if (CARPETA_APP / "modelos" / nombre / "model.bin").is_file():
            return etiqueta
    return list(MODELOS)[0]


def expandir_rutas(rutas):
    """Videos y audios de lo que se soltó o eligió; de las carpetas toma todo lo que haya adentro.

    Devuelve (archivos, ignorados): ignorados cuenta los archivos sueltos que no son video ni audio
    (lo que no es video dentro de una carpeta se salta sin avisar).
    """
    archivos, ignorados = [], 0
    for r in map(Path, rutas):
        if r.is_dir():
            archivos += sorted((a for a in r.rglob("*") if a.is_file() and a.suffix.lower() in EXT_MEDIOS),
                               key=lambda a: str(a).lower())
        elif r.is_file():
            if r.suffix.lower() in EXT_MEDIOS:
                archivos.append(r)
            else:
                ignorados += 1
    return archivos, ignorados


def recortar(texto, largo):
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


if TkinterDnD:
    class Ventana(ctk.CTk, TkinterDnD.DnDWrapper):
        """Ventana de CustomTkinter con soporte para arrastrar y soltar archivos."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = TkinterDnD._require(self)
else:
    Ventana = ctk.CTk


class FilaArchivo(ctk.CTkFrame):
    """Una fila de la lista: etiqueta VIDEO/AUDIO, nombre, estado y botón para quitar."""

    def __init__(self, master, ruta, al_quitar):
        super().__init__(master, fg_color=PANEL_ALTO, corner_radius=10)
        self.ruta = ruta
        es_audio = Path(ruta).suffix.lower() in EXT_AUDIO
        color = AZUL if es_audio else CORAL

        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text="AUDIO" if es_audio else "VIDEO", width=54, height=22, corner_radius=6,
                     fg_color=color, text_color=FONDO,
                     font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, rowspan=2, padx=(10, 10), pady=10)
        ctk.CTkLabel(self, text=recortar(Path(ruta).name, 42), text_color=TEXTO, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=1, sticky="ew", pady=(8, 0))
        self.estado = ctk.CTkLabel(self, text="En espera", text_color=TEXTO_SUAVE, anchor="w",
                                   font=ctk.CTkFont(size=12))
        self.estado.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        self.boton_quitar = ctk.CTkButton(self, text="✕", width=30, height=30, corner_radius=8,
                                          fg_color="transparent", hover_color=BORDE, text_color=TEXTO_SUAVE,
                                          command=lambda: al_quitar(self))
        self.boton_quitar.grid(row=0, column=2, rowspan=2, padx=(6, 8))

    def poner_estado(self, texto, color=TEXTO_SUAVE):
        self.estado.configure(text=texto, text_color=color)


class App:
    def __init__(self, root):
        self.root = root
        self.cola = queue.Queue()
        self.modelos_cargados = {}
        self.trabajando = False
        self.detener = threading.Event()
        self.cerrando = False
        self.ultima_carpeta = None
        self.carpeta_salida = None  # None = junto a cada video
        self.filas = []
        self.textos = []  # (nombre, texto) de lo transcrito en esta tanda, para "Copiar texto"

        root.title("Subtexto - videos y audios a texto con IA")
        # Lo más alto que quepa en la pantalla (hasta 820), para que la lista de archivos tenga espacio.
        escala = ctk.ScalingTracker.get_window_scaling(root)
        alto = max(640, min(820, int(root.winfo_screenheight() / escala) - 110))
        root.geometry(f"1120x{alto}")
        root.minsize(980, 640)
        root.configure(fg_color=FONDO)
        root.grid_columnconfigure(0, weight=0)
        root.grid_columnconfigure(1, weight=1)
        root.grid_rowconfigure(1, weight=1)

        self._crear_encabezado()
        self._crear_columna_izquierda()
        self._crear_columna_derecha()
        self.aplicar_config(leer_config())

        if TkinterDnD:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", self.soltar_archivos)

        self._actualizar_lista_vacia()
        root.protocol("WM_DELETE_WINDOW", self.cerrar)
        root.after(100, self.procesar_cola)
        threading.Thread(target=self.buscar_actualizacion, daemon=True).start()

    # ---------- construcción de la interfaz ----------
    def _tarjeta(self, master, **grid):
        tarjeta = ctk.CTkFrame(master, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDE)
        tarjeta.grid(**grid)
        return tarjeta

    def _titulo(self, master, texto, color=TEXTO):
        return ctk.CTkLabel(master, text=texto, text_color=color, anchor="w",
                            font=ctk.CTkFont(size=15, weight="bold"))

    def _enlace(self, master, texto, comando, color=TEXTO_SUAVE):
        enlace = ctk.CTkLabel(master, text=texto, text_color=color, cursor="hand2",
                              font=ctk.CTkFont(size=12, underline=True))
        enlace.bind("<Button-1>", lambda _: comando())
        return enlace

    def _crear_encabezado(self):
        enc = ctk.CTkFrame(self.root, fg_color="transparent")
        enc.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 8))
        enc.grid_columnconfigure(1, weight=1)

        # Logo oficial (la S cortada + "Subtexto" en Inter Bold, de brand/). El nombre no se reescribe con
        # otra letra: si la imagen no carga, se muestra solo como texto.
        nombre = ctk.CTkFrame(enc, fg_color="transparent")
        nombre.grid(row=0, column=0, columnspan=2, sticky="w")
        try:
            from PIL import Image
            imagen = Image.open(CARPETA / "assets" / "logo-horizontal.png")
            alto = 34
            logo = ctk.CTkLabel(nombre, text="", image=ctk.CTkImage(
                imagen, size=(round(alto * imagen.width / imagen.height), alto)))
        except Exception:
            logo = ctk.CTkLabel(nombre, text="Subtexto", text_color=TEXTO,
                                font=ctk.CTkFont(size=24, weight="bold"))
        logo.pack(side="left")
        # Espacio libre del logo: la mitad del alto de la S (guía de marca).
        ctk.CTkLabel(nombre, text=f"v{__version__}", text_color=TEXTO_SUAVE,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(18, 0), pady=(10, 0))
        ctk.CTkLabel(enc, text="Videos y audios a texto con IA, en tu computadora. Tus archivos no salen de ella.",
                     text_color=TEXTO_SUAVE, anchor="w",
                     font=ctk.CTkFont(size=13)).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        chips = ctk.CTkFrame(enc, fg_color="transparent")
        chips.grid(row=0, column=2, sticky="e")
        for texto, color in (("VIDEO", CORAL), ("AUDIO", AZUL), ("IA LOCAL", VIOLETA)):
            ctk.CTkLabel(chips, text=texto, height=26, corner_radius=13, fg_color=PANEL_ALTO,
                         text_color=color, font=ctk.CTkFont(size=11, weight="bold"),
                         width=86).pack(side="left", padx=4)
        enlaces = ctk.CTkFrame(enc, fg_color="transparent")
        enlaces.grid(row=1, column=2, sticky="e", padx=4)
        self.enlace_actualizacion = self._enlace(enlaces, "", lambda: webbrowser.open(URL_RELEASES), VERDE)
        self._enlace(enlaces, "Reportar problema", self.reportar_problema).pack(side="right")

    def _crear_columna_izquierda(self):
        izq = ctk.CTkFrame(self.root, fg_color="transparent", width=500)
        izq.grid(row=1, column=0, sticky="nsew", padx=(24, 10), pady=(8, 24))
        izq.grid_columnconfigure(0, weight=1)
        izq.grid_rowconfigure(0, weight=1)

        # --- Archivos ---
        archivos = self._tarjeta(izq, row=0, column=0, sticky="nsew")
        archivos.grid_columnconfigure(0, weight=1)
        archivos.grid_rowconfigure(1, weight=1)
        self._titulo(archivos, "Archivos").grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        self.contador = ctk.CTkLabel(archivos, text="", text_color=TEXTO_SUAVE, font=ctk.CTkFont(size=12))
        self.contador.grid(row=0, column=1, sticky="e", padx=16, pady=(14, 6))

        self.lista = ctk.CTkScrollableFrame(archivos, fg_color=FONDO, corner_radius=10, width=440, height=170,
                                            scrollbar_button_color=BORDE, scrollbar_button_hover_color=VIOLETA)
        self.lista.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16)
        self.lista.grid_columnconfigure(0, weight=1)
        self.vacio = ctk.CTkFrame(self.lista, fg_color="transparent")
        ctk.CTkLabel(self.vacio, text="⇩", text_color=VIOLETA, font=ctk.CTkFont(size=34)).pack()
        ctk.CTkLabel(
            self.vacio, text_color=TEXTO_SUAVE, justify="center", font=ctk.CTkFont(size=13),
            text=("Arrastra aquí tus videos o audios\no usa el botón de abajo" if TkinterDnD
                  else "Usa el botón de abajo para agregar\ntus videos o audios")).pack()

        botones = ctk.CTkFrame(archivos, fg_color="transparent")
        botones.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 14))
        self.boton_agregar = ctk.CTkButton(botones, text="＋  Agregar archivos", height=36, corner_radius=10,
                                           fg_color=PANEL_ALTO, hover_color=BORDE, text_color=TEXTO,
                                           font=ctk.CTkFont(size=13, weight="bold"), command=self.agregar)
        self.boton_agregar.pack(side="left")
        self.boton_vaciar = ctk.CTkButton(botones, text="Quitar todos", height=36, corner_radius=10,
                                          fg_color="transparent", hover_color=PANEL_ALTO, text_color=TEXTO_SUAVE,
                                          command=self.vaciar_lista)
        self.boton_vaciar.pack(side="left", padx=8)

        # --- Opciones ---
        op = self._tarjeta(izq, row=1, column=0, sticky="ew", pady=(14, 0))
        op.grid_columnconfigure(1, weight=1)
        self._titulo(op, "Opciones").grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 8))

        estilo_menu = dict(height=32, corner_radius=10, fg_color=PANEL_ALTO, button_color=BORDE,
                           button_hover_color=VIOLETA, text_color=TEXTO, dropdown_fg_color=PANEL_ALTO,
                           dropdown_hover_color=VIOLETA, dropdown_text_color=TEXTO, dynamic_resizing=False,
                           command=lambda _: self.guardar_config())
        ctk.CTkLabel(op, text="Modelo", text_color=TEXTO_SUAVE).grid(row=1, column=0, sticky="w", padx=16)
        self.modelo = ctk.CTkOptionMenu(op, values=list(MODELOS), **estilo_menu)
        self.modelo.grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=3)
        ctk.CTkLabel(op, text="Idioma", text_color=TEXTO_SUAVE).grid(row=2, column=0, sticky="w", padx=16)
        self.idioma = ctk.CTkOptionMenu(op, values=list(IDIOMAS), **estilo_menu)
        self.idioma.grid(row=2, column=1, sticky="ew", padx=(8, 16), pady=3)
        ctk.CTkLabel(op, text="Subtítulos", text_color=TEXTO_SUAVE).grid(row=3, column=0, sticky="w", padx=16)
        self.formato = ctk.CTkOptionMenu(op, values=list(FORMATOS), **estilo_menu)
        self.formato.grid(row=3, column=1, sticky="ew", padx=(8, 16), pady=3)
        ctk.CTkLabel(op, text="Palabras clave", text_color=TEXTO_SUAVE).grid(row=4, column=0, sticky="w",
                                                                             padx=16)
        self.palabras_clave = ctk.CTkEntry(
            op, height=32, corner_radius=10, fg_color=PANEL_ALTO, border_color=BORDE, text_color=TEXTO,
            placeholder_text=EJEMPLO_PALABRAS_CLAVE,
            placeholder_text_color=TEXTO_SUAVE)
        self.palabras_clave.grid(row=4, column=1, sticky="ew", padx=(8, 16), pady=3)
        self.palabras_clave.bind("<FocusOut>", lambda _: self.guardar_config())

        self.palabras = tk.BooleanVar(value=False)
        self.srt = tk.BooleanVar(value=True)
        self.vtt = tk.BooleanVar(value=False)
        self.texto_limpio = tk.BooleanVar(value=False)
        estilo_switch = dict(progress_color=VIOLETA, button_color=TEXTO, button_hover_color="#E2E8F0",
                             fg_color=BORDE, text_color=TEXTO, font=ctk.CTkFont(size=13),
                             command=self.guardar_config)
        interruptores = ctk.CTkFrame(op, fg_color="transparent")
        interruptores.grid(row=5, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 2))
        for i, (texto, variable) in enumerate((("Subtítulos .srt", self.srt), (".vtt", self.vtt),
                                               ("Texto sin tiempos", self.texto_limpio),
                                               ("Timestamps por palabra", self.palabras))):
            ctk.CTkSwitch(interruptores, text=texto, variable=variable,
                          **estilo_switch).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 18), pady=2)

        ctk.CTkLabel(op, text="Guardar en", text_color=TEXTO_SUAVE).grid(row=6, column=0, sticky="nw",
                                                                         padx=16, pady=(12, 0))
        destino = ctk.CTkFrame(op, fg_color="transparent")
        destino.grid(row=6, column=1, sticky="ew", padx=(8, 16), pady=(10, 14))
        self.etiqueta_salida = ctk.CTkLabel(destino, text=TEXTO_CARPETA_DEFECTO, text_color=TEXTO_SUAVE,
                                            anchor="w", justify="left", wraplength=320)
        self.etiqueta_salida.pack(anchor="w")
        botones_destino = ctk.CTkFrame(destino, fg_color="transparent")
        botones_destino.pack(anchor="w", pady=(4, 0))
        ctk.CTkButton(botones_destino, text="Elegir carpeta…", width=130, height=30, corner_radius=8,
                      fg_color=PANEL_ALTO, hover_color=BORDE, text_color=TEXTO,
                      command=self.elegir_carpeta).pack(side="left")
        self.boton_quitar_carpeta = ctk.CTkButton(
            botones_destino, text="Usar la del video", width=130, height=30, corner_radius=8,
            fg_color="transparent", border_width=1, border_color=BORDE, hover_color=PANEL_ALTO,
            text_color=TEXTO, text_color_disabled="#4B5563", command=self.quitar_carpeta, state="disabled")
        self.boton_quitar_carpeta.pack(side="left", padx=(8, 0))

        # --- Acciones ---
        acciones = ctk.CTkFrame(izq, fg_color="transparent")
        acciones.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        acciones.grid_columnconfigure(0, weight=1)
        self.boton = ctk.CTkButton(acciones, text="", height=46, corner_radius=12, text_color=TEXTO,
                                   text_color_disabled="#C4B5FD", font=ctk.CTkFont(size=16, weight="bold"))
        self.boton.grid(row=0, column=0, sticky="ew")
        self._boton_transcribir()
        self.boton_limpiar = ctk.CTkButton(acciones, text="Limpiar todo", width=120, height=46, corner_radius=12,
                                           fg_color=PANEL, hover_color=PANEL_ALTO, border_width=1,
                                           border_color=BORDE, text_color=TEXTO, command=self.limpiar_todo)
        self.boton_limpiar.grid(row=0, column=1, padx=(10, 0))

    def _crear_columna_derecha(self):
        der = self._tarjeta(self.root, row=1, column=1, sticky="nsew", padx=(10, 24), pady=(8, 24))
        der.grid_columnconfigure(0, weight=1)
        der.grid_rowconfigure(3, weight=1)

        cab = ctk.CTkFrame(der, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
        cab.grid_columnconfigure(0, weight=1)
        self._titulo(cab, "Transcripción en vivo").grid(row=0, column=0, sticky="w")
        self.boton_copiar = ctk.CTkButton(cab, text="⧉  Copiar texto", width=130, height=32, corner_radius=10,
                                          fg_color=PANEL_ALTO, hover_color=BORDE, text_color=TEXTO,
                                          text_color_disabled=BORDE, state="disabled", command=self.copiar_texto)
        self.boton_copiar.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.boton_carpeta = ctk.CTkButton(cab, text="📂  Abrir carpeta del resultado", height=32, corner_radius=10,
                                           fg_color=PANEL_ALTO, hover_color=BORDE, text_color=TEXTO,
                                           text_color_disabled=BORDE, state="disabled",
                                           command=self.abrir_carpeta)
        self.boton_carpeta.grid(row=0, column=2, sticky="e")

        self.estado = ctk.CTkLabel(der, text="Listo. Agrega uno o más archivos.", text_color=TEXTO_SUAVE,
                                   anchor="w", font=ctk.CTkFont(size=13))
        self.estado.grid(row=1, column=0, sticky="ew", padx=18, pady=(10, 4))
        self.barra = ctk.CTkProgressBar(der, height=10, corner_radius=5, fg_color=PANEL_ALTO,
                                        progress_color=VIOLETA)
        self.barra.grid(row=2, column=0, sticky="ew", padx=18)
        self.poner_barra(0)

        self.log = ctk.CTkTextbox(der, fg_color=FONDO, text_color=TEXTO, corner_radius=10, wrap="word",
                                  font=ctk.CTkFont(family="Consolas", size=13), border_spacing=10,
                                  scrollbar_button_color=BORDE, scrollbar_button_hover_color=VIOLETA)
        self.log.grid(row=3, column=0, sticky="nsew", padx=18, pady=(14, 18))
        self.log.tag_config("titulo", foreground=CORAL)
        self.log.tag_config("ok", foreground=VERDE)
        self.log.tag_config("error", foreground=ROJO)
        self.log.tag_config("info", foreground=TEXTO_SUAVE)
        self.log_vacio = True
        self.limpiar_log()

    def _boton_transcribir(self):
        self.boton.configure(text="▶   Transcribir", fg_color=VIOLETA, hover_color=VIOLETA_HOVER,
                             command=self.iniciar, state="normal")

    def _boton_detener(self):
        self.boton.configure(text="■   Detener", fg_color=ROJO, hover_color=ROJO_HOVER,
                             command=self.pedir_detener, state="normal")

    # ---------- opciones guardadas ----------
    def aplicar_config(self, config):
        etiquetas = {nombre: etiqueta for etiqueta, nombre in MODELOS.items()}
        self.modelo.set(etiquetas.get(config.get("modelo"), modelo_inicial()))
        self.idioma.set(config.get("idioma") if config.get("idioma") in IDIOMAS else list(IDIOMAS)[0])
        formatos = {nombre: etiqueta for etiqueta, nombre in FORMATOS.items()}
        self.formato.set(formatos.get(config.get("formato"), list(FORMATOS)[0]))
        if self.palabras_clave.get():
            # Se quita el foco del campo y se vuelve a poner el texto de ejemplo (CustomTkinter no lo hace
            # solo si el campo se vacía desde el código).
            self.root.focus_set()
            self.palabras_clave.delete(0, "end")
            self.palabras_clave.configure(placeholder_text=EJEMPLO_PALABRAS_CLAVE)
        if config.get("palabras_clave"):
            self.palabras_clave.insert(0, str(config["palabras_clave"]))
        self.palabras.set(bool(config.get("palabras", False)))
        self.srt.set(bool(config.get("srt", True)))
        self.vtt.set(bool(config.get("vtt", False)))
        self.texto_limpio.set(bool(config.get("texto_limpio", False)))
        carpeta = config.get("carpeta")
        if carpeta and Path(carpeta).is_dir():
            self.poner_carpeta(carpeta)
        else:
            self.quitar_carpeta()

    def guardar_config(self):
        config = {
            "modelo": MODELOS[self.modelo.get()],
            "idioma": self.idioma.get(),
            "formato": FORMATOS[self.formato.get()],
            "palabras_clave": self.palabras_clave.get().strip(),
            "palabras": self.palabras.get(),
            "srt": self.srt.get(),
            "vtt": self.vtt.get(),
            "texto_limpio": self.texto_limpio.get(),
            "carpeta": self.carpeta_salida,
        }
        try:
            ARCHIVO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            ARCHIVO_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            registro.exception("No se pudo guardar la configuración")

    # ---------- barra y registro ----------
    def poner_barra(self, valor):
        # Con valor 0 la barra redondeada dibuja un puntito; se oculta pintándola del color del fondo.
        self.barra.configure(progress_color=VIOLETA if valor > 0 else PANEL_ALTO)
        self.barra.set(valor)

    def limpiar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "Aquí vas a ver el texto conforme la IA lo va escuchando,\n"
                               "con el minuto y segundo de cada frase.", "info")
        self.log.configure(state="disabled")
        self.log_vacio = True

    def escribir_log(self, texto, etiqueta=None):
        self.log.configure(state="normal")
        if self.log_vacio:
            self.log.delete("1.0", "end")
            self.log_vacio = False
        self.log.insert("end", texto + "\n", etiqueta)
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---------- lista de archivos ----------
    def _actualizar_lista_vacia(self):
        if self.filas:
            self.vacio.grid_forget()
            n = len(self.filas)
            self.contador.configure(text=f"{n} archivo{'s' if n != 1 else ''}")
        else:
            self.vacio.grid(row=0, column=0, sticky="nsew", pady=24)
            self.contador.configure(text="")

    def agregar_rutas(self, rutas):
        if self.trabajando or not rutas:
            return
        archivos, ignorados = expandir_rutas(rutas)
        existentes = {f.ruta for f in self.filas}
        for r in map(str, archivos):
            if r not in existentes:
                fila = FilaArchivo(self.lista, r, self.quitar_fila)
                fila.grid(row=len(self.filas) + 1, column=0, sticky="ew", pady=(0, 8))
                self.filas.append(fila)
                existentes.add(r)
        self._actualizar_lista_vacia()
        if ignorados:
            self.estado.configure(text=f"Se ignoraron {ignorados} archivo(s) que no son video ni audio.",
                                  text_color=CORAL)
        elif not archivos:
            self.estado.configure(text="No encontré videos ni audios ahí.", text_color=CORAL)

    def agregar(self):
        rutas = filedialog.askopenfilenames(
            title="Elige videos o audios",
            filetypes=[("Video o audio", EXTENSIONES), ("Todos los archivos", "*.*")])
        self.agregar_rutas(rutas)

    def soltar_archivos(self, evento):
        self.agregar_rutas(self.root.tk.splitlist(evento.data))

    def quitar_fila(self, fila):
        if self.trabajando:
            return
        fila.destroy()
        self.filas.remove(fila)
        for i, f in enumerate(self.filas):
            f.grid(row=i + 1, column=0, sticky="ew", pady=(0, 8))
        self._actualizar_lista_vacia()

    def vaciar_lista(self):
        if self.trabajando:
            return
        for f in self.filas:
            f.destroy()
        self.filas.clear()
        self._actualizar_lista_vacia()

    # ---------- carpeta de salida ----------
    def poner_carpeta(self, carpeta):
        self.carpeta_salida = str(Path(carpeta))
        self.etiqueta_salida.configure(text=self.carpeta_salida, text_color=TEXTO)
        self.boton_quitar_carpeta.configure(state="normal")

    def elegir_carpeta(self):
        carpeta = filedialog.askdirectory(title="¿Dónde guardo las transcripciones y subtítulos?")
        if carpeta:
            self.poner_carpeta(carpeta)
            self.guardar_config()

    def quitar_carpeta(self):
        self.carpeta_salida = None
        self.etiqueta_salida.configure(text=TEXTO_CARPETA_DEFECTO, text_color=TEXTO_SUAVE)
        self.boton_quitar_carpeta.configure(state="disabled")
        self.guardar_config()

    def limpiar_todo(self):
        """Deja la ventana como recién instalada (el modelo cargado se conserva para ir más rápido)."""
        if self.trabajando:
            return
        self.vaciar_lista()
        self.limpiar_log()
        self.poner_barra(0)
        self.estado.configure(text="Listo. Agrega uno o más archivos.", text_color=TEXTO_SUAVE)
        self.aplicar_config({})
        try:
            ARCHIVO_CONFIG.unlink(missing_ok=True)
        except OSError:
            pass
        self.ultima_carpeta = None
        self.textos = []
        self.boton_carpeta.configure(state="disabled")
        self.boton_copiar.configure(state="disabled")

    # ---------- trabajo en segundo plano ----------
    def _bloquear(self, bloqueado):
        estado = "disabled" if bloqueado else "normal"
        for boton in (self.boton_limpiar, self.boton_agregar, self.boton_vaciar):
            boton.configure(state=estado)
        for fila in self.filas:
            fila.boton_quitar.configure(state=estado)

    def iniciar(self):
        if self.trabajando:
            return
        if not self.filas:
            self.estado.configure(text="Agrega al menos un archivo para transcribir.", text_color=CORAL)
            return
        self.trabajando = True
        self.detener.clear()
        self.textos = []
        self._bloquear(True)
        self._boton_detener()
        self.boton_carpeta.configure(state="disabled")
        self.boton_copiar.configure(state="disabled")
        self.poner_barra(0)
        for fila in self.filas:
            fila.poner_estado("En espera")
        self.guardar_config()
        opciones = dict(
            modelo=MODELOS[self.modelo.get()],
            idioma=IDIOMAS[self.idioma.get()],
            formato=FORMATOS[self.formato.get()],
            palabras_clave=self.palabras_clave.get().strip(),
            palabras=self.palabras.get(),
            srt=self.srt.get(),
            vtt=self.vtt.get(),
            texto_limpio=self.texto_limpio.get(),
            carpeta=self.carpeta_salida,
        )
        # Al registro no van la carpeta ni las palabras clave (pueden ser datos personales).
        registro.info("Inicio: %d archivo(s), %s", len(self.filas),
                      {k: (bool(v) if k == "palabras_clave" else v)
                       for k, v in opciones.items() if k != "carpeta"})
        videos = [f.ruta for f in self.filas]
        threading.Thread(target=self.trabajar, args=(videos, opciones), daemon=True).start()

    def pedir_detener(self):
        self.detener.set()
        self.boton.configure(text="Deteniendo…", state="disabled")
        self.estado.configure(text="Deteniendo: se guarda lo transcrito hasta ahora…", text_color=CORAL)

    def trabajar(self, videos, op):
        enviar = self.cola.put
        try:
            enviar(("estado", "Cargando la IA…"))
            import transcribir  # importación pesada: se hace aquí para que la ventana abra al instante

            modelo = self.modelos_cargados.get(op["modelo"])
            if modelo is None:
                enviar(("log", (f"Cargando modelo '{op['modelo']}'...", "info")))
                # Solo un modelo en memoria a la vez, para no llenar la memoria de la tarjeta de video.
                self.modelos_cargados.clear()
                ultimo_aviso = [0.0]

                def progreso_descarga(bajado, total):
                    ahora = time.monotonic()
                    if ahora - ultimo_aviso[0] >= 0.25 or bajado >= total:
                        ultimo_aviso[0] = ahora
                        enviar(("descarga", (bajado, total)))

                modelo, disp = transcribir.cargar_modelo(
                    op["modelo"], log=lambda m: enviar(("log", (m, "info"))), progreso_descarga=progreso_descarga)
                self.modelos_cargados[op["modelo"]] = modelo
                enviar(("log", (f"Modelo listo en {'la tarjeta NVIDIA' if disp == 'cuda' else 'el procesador'}.",
                                "info")))
                enviar(("progreso", 0))

            total = len(videos)
            errores = 0
            detenido = False
            guardados = 0
            for n, video in enumerate(videos):
                if self.detener.is_set():
                    detenido = True
                    enviar(("fila", (n, "No transcrito (se detuvo)", TEXTO_SUAVE)))
                    continue
                nombre = Path(video).name
                enviar(("estado", f"Transcribiendo {n + 1} de {total}: {nombre}"))
                enviar(("fila", (n, "Leyendo el audio…", VIOLETA)))
                enviar(("log", (f"\n━━ {nombre} ━━", "titulo")))

                def progreso(f, n=n):
                    enviar(("progreso", (n + f) / total))
                    enviar(("fila", (n, f"Transcribiendo… {f:.0%}", VIOLETA)))

                try:
                    resultado = transcribir.transcribir_video(
                        modelo, video, op["modelo"], op["idioma"], op["palabras"], op["srt"], op["vtt"],
                        carpeta=op["carpeta"], log=lambda m: enviar(("log", (m, None))), progreso=progreso,
                        detener=self.detener, palabras_clave=op["palabras_clave"], formato=op["formato"],
                        texto_limpio=op["texto_limpio"])
                    for g in resultado.archivos:
                        enviar(("log", (f"✓ Guardado: {g}", "ok")))
                    if resultado.texto:
                        enviar(("texto", (nombre, resultado.texto)))
                    if resultado.completo:
                        enviar(("fila", (n, "✓ Listo", VERDE)))
                    else:
                        detenido = True
                        enviar(("fila", (n, "Detenido (guardado incompleto)", CORAL)))
                    enviar(("carpeta", str(resultado.archivos[0].parent)))
                    guardados += 1
                except transcribir.Detenido:
                    # Se detuvo mientras leía el audio: todavía no había nada que guardar.
                    detenido = True
                    enviar(("fila", (n, "No transcrito (se detuvo)", TEXTO_SUAVE)))
                    enviar(("log", ("Detenido antes de empezar a transcribir este archivo.", "info")))
                except Exception as e:
                    errores += 1
                    registro.exception("Error con un archivo %s", Path(video).suffix)
                    enviar(("fila", (n, "✕ Error (ver registro)", ROJO)))
                    enviar(("log", (f"ERROR con {nombre}: {e}", "error")))
            if detenido and guardados:
                enviar(("fin", ("Detenido. Se guardó lo transcrito hasta ese momento.", CORAL)))
            elif detenido:
                enviar(("fin", ("Detenido antes de empezar: no se guardó nada.", CORAL)))
            elif errores:
                enviar(("fin", (f"Terminado con {errores} error(es). Revisa el registro.", ROJO)))
            else:
                enviar(("fin", ("✓ Terminado. Tus archivos están listos.", VERDE)))
        except Exception as e:
            registro.exception("Error inesperado")
            enviar(("log", (f"Ocurrió un error: {e}", "error")))
            enviar(("log", ("Si se repite, usa «Reportar problema» (arriba a la derecha) y adjunta el "
                            "archivo subtexto.log.", "info")))
            if not isinstance(e, RuntimeError):
                enviar(("log", (traceback.format_exc(), "info")))
            enviar(("fin", ("Ocurrió un error. Revisa el registro.", ROJO)))

    def procesar_cola(self):
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                if tipo == "log":
                    texto, etiqueta = dato
                    self.escribir_log(texto, etiqueta)
                elif tipo == "estado":
                    self.estado.configure(text=dato, text_color=TEXTO)
                elif tipo == "progreso":
                    self.poner_barra(dato)
                elif tipo == "descarga":
                    bajado, total = dato
                    self.estado.configure(text=f"Descargando modelo: {bajado / 1e6:,.0f} / {total / 1e6:,.0f} MB "
                                               "(solo la primera vez)", text_color=TEXTO)
                    self.poner_barra(bajado / total if total else 0)
                elif tipo == "fila":
                    n, texto, color = dato
                    if n < len(self.filas):
                        self.filas[n].poner_estado(texto, color)
                elif tipo == "texto":
                    self.textos.append(dato)
                    self.boton_copiar.configure(state="normal")
                elif tipo == "carpeta":
                    self.ultima_carpeta = dato
                    self.boton_carpeta.configure(state="normal")
                elif tipo == "actualizacion":
                    self.enlace_actualizacion.configure(text=f"Hay una versión nueva ({dato})")
                    self.enlace_actualizacion.pack(side="right", padx=(0, 14))
                elif tipo == "fin":
                    texto, color = dato
                    self.estado.configure(text=texto, text_color=color)
                    self.trabajando = False
                    self._bloquear(False)
                    self._boton_transcribir()
        except queue.Empty:
            pass
        self.root.after(100, self.procesar_cola)

    # ---------- acciones ----------
    def cerrar(self, limite=None):
        """Si está transcribiendo, primero se detiene para guardar lo avanzado y luego cierra.

        Espera como máximo 20 s (por ejemplo, si está descargando el modelo no hay nada que guardar).
        """
        if not self.trabajando or (limite and time.monotonic() > limite):
            self.root.destroy()
            return
        if limite is None:
            if self.cerrando:
                return  # ya se está cerrando (doble clic en la X)
            self.cerrando = True
            self.pedir_detener()
            self.estado.configure(text="Cerrando: guardando lo transcrito hasta ahora…", text_color=CORAL)
            limite = time.monotonic() + 20
        self.root.after(200, lambda: self.cerrar(limite))

    def abrir_carpeta(self):
        if self.ultima_carpeta:
            os.startfile(self.ultima_carpeta)

    def copiar_texto(self):
        if not self.textos:
            return
        if len(self.textos) == 1:
            texto = self.textos[0][1]
        else:
            texto = "\n\n".join(f"{nombre}\n\n{t}" for nombre, t in self.textos)
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.estado.configure(text="✓ Texto copiado. Pégalo donde quieras (Ctrl+V).", text_color=VERDE)

    def reportar_problema(self):
        webbrowser.open(URL_REPORTAR)
        if CARPETA_REGISTRO.is_dir():
            os.startfile(CARPETA_REGISTRO)

    def buscar_actualizacion(self):
        """Revisa en GitHub si hay una versión nueva. Si no hay internet o falla, no hace nada."""
        try:
            pedido = urllib.request.Request(URL_API_RELEASES, headers={"User-Agent": f"Subtexto/{__version__}"})
            with urllib.request.urlopen(pedido, timeout=5) as r:
                etiqueta = json.load(r).get("tag_name", "")
            if es_mas_nueva(etiqueta):
                self.cola.put(("actualizacion", etiqueta))
        except Exception:
            pass


def main():
    sys.path.insert(0, str(CARPETA))
    configurar_registro()
    try:
        # Para que la barra de tareas muestre el ícono de la app y no el de Python.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Subtexto")
    except Exception:
        pass
    ctk.set_appearance_mode("dark")
    root = Ventana()
    try:
        root.iconbitmap(str(CARPETA / "assets" / "icono.ico"))
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
