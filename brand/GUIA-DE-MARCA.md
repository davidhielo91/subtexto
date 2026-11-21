# Subtexto — guía de marca

## La idea

**La S está cortada como se cortan los subtítulos: en renglones.**
Subtexto escucha tu video y te devuelve el texto en líneas cortas. El símbolo es una S de tres
renglones con un corte recto en el centro: no dibuja ondas, micrófonos ni el ícono "CC" que usa
toda la categoría.

Construcción (lienzo 256×256): un solo trazo de grosor 36 con puntas redondas, curvas de radio 32,
renglones separados 64, corte recto de 24 en el lomo. Es simétrica al girarla 180°.
Todo se genera con código en `herramientas/construir_marca.py` (no hay archivos dibujados a mano).

## Archivos

| Carpeta | Qué hay | Para qué |
|---|---|---|
| `logo/` | `simbolo*.svg`, `horizontal-*.svg`, `apilado-*.svg`, `palabra-*.svg`, `icono-app*.svg` (+ PNG grandes) | Masters. Usa siempre el SVG si el lugar lo acepta |
| `windows/` | `icono.ico` (16–256 px), `icono.png` (1024), `logo_64.png`, `instalador-panel(-2x).png` | Programa e instalador |
| `web/` | `favicon.ico/.svg`, `favicon-16/32/48.png`, `apple-touch-icon.png`, `icon-192/512.png`, `maskable-512.png`, `site.webmanifest`, `head-snippet.html`, `logo-claro/oscuro.svg`, `og-image.png`, `github-social-preview.png` | Página de descarga y GitHub |
| `redes/` | `perfil.png` (1080), portadas de X (1500×500), Facebook (1640×624) y YouTube (2560×1440) | Redes sociales |
| `presentacion/` | `presentacion.html` y `laminas/` | Presentación con mockups |

Variantes de color en los nombres: **color** (S violeta + texto oscuro, para fondos claros),
**sobre-oscuro** (S violeta + texto claro), **negro**, **blanco** y **violeta** (todo de un color).

## Color

| Nombre | HEX | RGB | CMYK (aprox.) | Uso |
|---|---|---|---|---|
| Violeta | `#8B5CF6` | 139 92 246 | 55 63 0 0 | Color principal: símbolo, botones, placa del ícono |
| Noche | `#111827` | 17 24 39 | 80 70 50 75 | Fondo oscuro (el de la app) y texto sobre claro |
| Nieve | `#F8FAFC` | 248 250 252 | 2 1 0 0 | Texto sobre oscuro |
| Gris | `#94A3B8` | 148 163 184 | 40 25 15 0 | Texto secundario sobre oscuro |
| Coral | `#F59E70` | 245 158 112 | 0 45 55 0 | Acento: solo para "video" |
| Azul | `#38BDF8` | 56 189 248 | 65 10 0 0 | Acento: solo para "audio" |

Pantone más cercano al violeta: 2665 C (pide una prueba impresa antes de producir; los CMYK son aproximados).
Contraste: violeta sobre blanco 4.2:1 y sobre Noche 4.2:1 (suficiente para el logo y textos grandes);
para texto chico sobre violeta usa blanco en negrita o cambia a Noche.
Coral y azul nunca van en el logo: son acentos de la interfaz.

## Tipografía

El nombre está escrito en **Inter Bold** (Rasmus Andersson, SIL Open Font License 1.1: permite usarla en un
logotipo), con el espaciado un poco cerrado (−1.8 %). En los archivos ya está convertida a contornos, así que
no hace falta tener la fuente instalada para usarlos. Para textos de la marca (web, redes): Inter Medium y SemiBold.

## Espacio libre y tamaños mínimos

- **Espacio libre:** alrededor del logo deja como mínimo **la mitad del alto de la S** por cada lado.
  Nada de texto, bordes ni otros logos dentro de ese espacio.
- **Proporciones fijas del logo horizontal:** la S mide 1.4 veces la altura de la mayúscula del nombre y se separa
  de él 0.5 veces esa altura. En el apilado, la S mide 2.4 veces la altura de la mayúscula. No las cambies: usa los archivos.
- **Tamaños mínimos:** símbolo 16 px (de 16 a 32 px usa `simbolo-chico.svg` / `icono-app-chico.svg`,
  con trazo más grueso y el corte más abierto); logo horizontal 96 px de ancho en pantalla o 25 mm impreso;
  apilado 64 px de ancho.

## Fondos

- Fondo claro → `horizontal-color`. Fondo oscuro → `horizontal-sobre-oscuro`.
- Sobre violeta, fotos o fondos con mucho detalle → versión `blanco` (con un velo oscuro si la foto es clara).
- Una sola tinta (sellos, grabado, fax) → `negro` o `blanco`.

## No hacer

- No cerrar el corte de la S ni redondearlo: el corte es la idea.
- No girar, inclinar, estirar ni reflejar la S (reflejada parece un 2 o una Z).
- No agregar sombras, degradados, contornos ni brillos.
- No cambiar el violeta por otro color, ni pintar la S de coral o azul.
- No reescribir "Subtexto" con otra tipografía ni separar el nombre del símbolo con otra distancia.
- No poner el logo violeta sobre fondos de contraste bajo (grises medios, otros violetas).

## Cómo aplicarlo

**Ya está aplicado** al programa, al instalador, al README y a la página de descarga
(https://subtexto.hieloco.de, que vive en un repositorio aparte y usa los archivos de `brand/web/`). Falta lo que no vive en el
código: la imagen social de GitHub (paso 2) y las redes (paso 4). Si cambias el logo, vuelve a aplicarlo así:

1. **Programa e instalador:**
   ```
   python brand/herramientas/construir_marca.py --aplicar
   ```
   Copia `icono.ico`, `icono.png` y `logo_64.png` a `assets/` (mismas rutas que ya usan
   `build/subtexto.spec`, `build/instalador.iss`, `subtexto.pyw` y `crear_acceso_directo.ps1`), y las imágenes
   del panel lateral a `build/`. Después agrega esta línea en `build/instalador.iss`, debajo de
   `WizardSmallImageFile`:
   ```
   WizardImageFile=instalador-panel.png,instalador-panel-2x.png
   ```
   y reconstruye con `build/construir.ps1`. Opcional: reemplaza el contenido de `assets/generar_icono.py` por una
   llamada a `construir_marca.py`, porque el generador viejo dibuja el ícono anterior.
   Windows guarda en caché los íconos: si el acceso directo sigue mostrando el ícono anterior, reinicia el Explorador.
2. **README:** cambia el encabezado por
   ```html
   <h1 align="center">
     <picture>
       <source media="(prefers-color-scheme: dark)" srcset="brand/web/logo-oscuro.svg">
       <img src="brand/web/logo-claro.svg" width="320" alt="Subtexto">
     </picture>
   </h1>
   ```
   y en GitHub, en *Settings → Social preview*, sube `brand/web/github-social-preview.png`.
3. **Página de descarga:** ya hecha en `web/` (Astro). Si cambias el logo, vuelve a copiar los archivos de `brand/web/`
   a `web/public/` y publica con `npm run deploy` dentro de `web/`.
4. **Redes:** `redes/perfil.png` como foto (queda bien en círculo) y la portada de cada red.

## Regenerar

```
python brand/herramientas/construir_marca.py            # todo, solo dentro de brand/
python brand/herramientas/construir_marca.py --sin-png  # solo SVG
```
Necesita Python 3.9+, Pillow, fontTools (`pip install fonttools`), Inter instalada
(https://rsms.me/inter/) y Google Chrome o Microsoft Edge (se usan para pasar los SVG a PNG).
Las medidas del símbolo están en `simbolo()` y en `S_NORMAL`, `S_BLANCA` (más delgada para blanco sobre oscuro)
y `S_CHICA` (para 16–32 px).

## Pendientes

- **Registro de marca:** no se hizo búsqueda de marcas. Antes de usarlo comercialmente, busca "Subtexto" y la S
  en el IMPI (México) / EUIPO / USPTO y haz una búsqueda inversa de imagen del símbolo.
- Revisar el ícono en la barra de tareas y el Explorador con el programa ya instalado (después de `--aplicar`).
