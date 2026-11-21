"""Genera build/descargas.iss: la lista de archivos que el instalador baja de internet.

Modelos: de Hugging Face, fijados a una versión (commit) para que las URLs nunca cambien.
CUDA (solo NVIDIA): las DLLs oficiales de NVIDIA publicadas en PyPI (archivos .whl, que son .zip).
Cada archivo lleva su SHA-256 para que el instalador verifique que bajó completo y sin alteraciones.
"""

import hashlib
import json
import urllib.request
from pathlib import Path

# Nombre que usa Subtexto -> repositorio en Hugging Face (los mismos que usa faster-whisper).
MODELOS = {
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "large-v3": "Systran/faster-whisper-large-v3",
    "small": "Systran/faster-whisper-small",
}
# Versiones probadas con ctranslate2 4.x. Para cada una: (paquete/versión, una DLL que indica
# que ya está instalada y no hay que volver a bajarla al actualizar).
CUDA = {
    "cublas": ("nvidia-cublas-cu12/12.9.2.10", "nvidia/cublas/bin/cublas64_12.dll"),
    "cudnn": ("nvidia-cudnn-cu12/9.27.0.42", "nvidia/cudnn/bin/cudnn64_9.dll"),
    "nvrtc": ("nvidia-cuda-nvrtc-cu12/12.9.86", "nvidia/cuda_nvrtc/bin/nvrtc64_120_0.dll"),
}
ARCHIVOS_MODELO = {"config.json", "model.bin", "preprocessor_config.json", "tokenizer.json",
                   "vocabulary.json", "vocabulary.txt"}


def abrir(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "subtexto-build"}),
                                  timeout=60)


def leer_json(url):
    with abrir(url) as r:
        return json.load(r)


def sha256_de_url(url):
    h = hashlib.sha256()
    with abrir(url) as r:
        for bloque in iter(lambda: r.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def win(ruta):
    return ruta.replace("/", "\\")


def linea(url, destino, nombre, hash_, tamano, tarea, si_falta, extra=""):
    return (f'Source: "{url}"; DestName: "{nombre}"; DestDir: "{win(destino)}"; Hash: "{hash_}"; '
            f'ExternalSize: {tamano}; Tasks: {tarea}; Check: NoExiste(\'{win(si_falta)}\'); '
            f'Flags: external download ignoreversion{extra}')


def main():
    lineas = ["; Archivo generado por generar_descargas.py. No editar a mano.", "[Files]"]

    for nombre, repo in MODELOS.items():
        sha = leer_json(f"https://huggingface.co/api/models/{repo}/revision/main")["sha"]
        destino = f"{{app}}/modelos/{nombre}"
        tarea = "modelo_" + nombre.replace("-", "_").replace(".", "")
        for f in leer_json(f"https://huggingface.co/api/models/{repo}/tree/{sha}"):
            if f["path"] not in ARCHIVOS_MODELO:
                continue
            url = f"https://huggingface.co/{repo}/resolve/{sha}/{f['path']}"
            hash_ = f["lfs"]["oid"] if f.get("lfs") else sha256_de_url(url)
            lineas.append(linea(url, destino, f["path"], hash_, f["size"], tarea, f"{destino}/{f['path']}"))
        print(f"Modelo {nombre}: {repo}@{sha[:7]}")

    for nombre, (paquete, dll) in CUDA.items():
        datos = leer_json(f"https://pypi.org/pypi/{paquete}/json")
        rueda = next(u for u in datos["urls"] if u["filename"].endswith("win_amd64.whl"))
        lineas.append(linea(rueda["url"], "{app}/cuda", f"{nombre}.zip", rueda["digests"]["sha256"],
                            rueda["size"], "gpu", f"{{app}}/cuda/{dll}",
                            " extractarchive recursesubdirs createallsubdirs"))
        print(f"CUDA {nombre}: {rueda['filename']} ({rueda['size'] / 1e6:.0f} MB)")

    salida = Path(__file__).with_name("descargas.iss")
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Escrito: {salida}")


if __name__ == "__main__":
    main()
