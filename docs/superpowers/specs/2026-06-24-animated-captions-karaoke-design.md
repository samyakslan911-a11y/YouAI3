# Captions Animadas Word-Level (ASS Karaoke)

**Fecha:** 2026-06-24  
**Estado:** Aprobado  
**Prioridad:** #1 del roadmap de mejoras

---

## Objetivo

Reemplazar el sistema de captions SRT estático por captions animadas en formato ASS (Advanced SubStation Alpha) con efectos de karaoke word-level. Cada palabra se anima al ritmo del audio — aumenta retención y diferencia el producto de competidores básicos.

---

## Contexto

El pipeline actual genera archivos `.srt` con frases (subtítulos) o palabras individuales (CapCut). Los quema en el video via `ffmpeg subtitles=file.srt:force_style='...'`. El resultado es texto estático: aparece, se queda fijo, desaparece. No hay animación de entrada ni highlight por palabra.

Herramientas como Captions.ai cobran $12/mes exclusivamente por este efecto. Lo implementamos internamente sin dependencias externas usando libass, que ya está instalado en Railway vía `ffmpeg`.

---

## Dos estilos nuevos

### `"capcut"` (mejorado)
Una palabra a la vez, centrada en pantalla. Añade animación de escala (118%) y fade-in de 80ms al aparecer cada palabra.

```
{\an5\fscx118\fscy118\fad(80,60)}REVELACIÓN
```

- Alineación: centro de pantalla (`\an5`)
- Fuente: 88px Liberation Sans Bold
- Color: blanco con sombra negra 4px
- Animación: aparece al 118% de escala + fade 80ms entrada / 60ms salida

### `"karaoke"` (nuevo)
Frases de 4 palabras en la parte baja. La palabra activa se "pinta" de amarillo con wipe de izquierda a derecha (`\kf`) sincronizado con el audio.

```
{\kf42}ESTO {\kf38}ES {\kf55}LO {\kf61}VIRAL
```

- Alineación: abajo centro (`\an2`)
- Fuente: 72px Liberation Sans Bold
- Color activo: amarillo `&H0000FFFF`
- Color inactivo: blanco
- Animación: wipe `\kf` por palabra (duración proporcional a su duración en audio)
- Sombra: 3px negro

---

## Cambios técnicos

### `src/services/editor.py`

**1. Tipo `CaptionStyle`** — añade `"karaoke"`:
```python
CaptionStyle = Literal["capcut", "karaoke", "subtitles", "none"]
```

**2. `_ass_header(style: CaptionStyle) -> str`** (función nueva)
Genera el bloque `[Script Info]` + `[V4+ Styles]` del archivo ASS con los parámetros correctos por estilo. PlayResX=1080, PlayResY=1920.

Campos clave del estilo ASS:
- `PrimaryColour` — color del texto activo (blanco `&H00FFFFFF` o amarillo `&H0000FFFF`)
- `SecondaryColour` — color antes del karaoke wipe (blanco `&H00FFFFFF`)
- `OutlineColour` — sombra negra `&H00000000`
- `Bold=-1` — negrita
- `Alignment` — 5 (centro) para capcut, 2 (abajo centro) para karaoke
- `MarginV` — 200px para capcut (empuja hacia centro), 80px para karaoke

**3. `_build_ass(word_events, style) -> Path`** (función nueva)
Genera el archivo `.ass` completo en `/tmp`.

- Para `"capcut"`: un `Dialogue` por palabra con tag `{\an5\fscx118\fscy118\fad(80,60)}PALABRA`
- Para `"karaoke"`: un `Dialogue` por chunk de 4 palabras con `{\kf<cs>}PALABRA` por cada una. Duración en centisegundos = `round(word_duration * 100)`.

Tiempos en formato ASS: `H:MM:SS.cs` (centisegundos, no milisegundos como SRT).

**4. `_build_srt()` — sin cambios**
Se mantiene para el estilo `"subtitles"`. Sin tocar.

**5. `process_segment()` — lógica de despacho actualizada**
```python
if caption_style in ("capcut", "karaoke"):
    word_events = _interpolate_word_timing(all_segments, start, end)
    srt_path = _build_ass(word_events, caption_style)   # devuelve .ass
elif caption_style == "subtitles":
    word_events = _interpolate_word_timing(all_segments, start, end)
    srt_path = _build_srt(word_events, caption_style)   # devuelve .srt
```

**6. `cut_and_format()` — detección de formato**
```python
if srt_path and srt_path.exists():
    if srt_path.suffix == ".ass":
        filter_complex += f";[out]ass={srt_str}[final]"
    else:
        force_style = _caption_force_style(caption_style, font_path)
        filter_complex += f";[out]subtitles={srt_str}:force_style='{force_style}'[final]"
```
El filtro `ass=` no necesita `force_style` porque el ASS lleva los estilos embebidos.

`_caption_force_style()` — se mantiene sin cambios, solo se usa para `"subtitles"`.

---

## Cambios en `web/app/page.tsx`

Selector de caption style: añade botón **"Karaoke"** entre "CapCut" y "Subtítulos".

```
[CapCut] [Karaoke] [Subtítulos] [Ninguno]
```

---

## Sin cambios en

- `api_server.py` — ya acepta `caption_style` como string
- `requirements-prod.txt` — libass ya está en el sistema vía ffmpeg
- `Dockerfile` — sin cambios

---

## Parámetros de estilo ASS — tabla completa

| Parámetro | CapCut | Karaoke |
|-----------|--------|---------|
| Fuente | Liberation Sans | Liberation Sans |
| Tamaño | 88 | 72 |
| Bold | -1 | -1 |
| PrimaryColour | `&H00FFFFFF` | `&H0000FFFF` (amarillo) |
| SecondaryColour | `&H00FFFFFF` | `&H00FFFFFF` |
| OutlineColour | `&H00000000` | `&H00000000` |
| BackColour | `&H80000000` | `&H80000000` |
| Outline | 4 | 3 |
| Shadow | 1 | 0 |
| Alignment | 5 (centro) | 2 (abajo) |
| MarginV | 200 | 80 |
| Tag por palabra | `{\an5\fscx118\fscy118\fad(80,60)}` | `{\kf<cs>}` |

---

## Flujo completo

```
word_events (timing interpolado)
    ↓
_build_ass(word_events, "karaoke")
    → genera /tmp/captions_<id>.ass
    → [Script Info] + [V4+ Styles] + [Events] con \kf tags
    ↓
cut_and_format(..., srt_path=ass_file, ...)
    → detecta .ass → usa filtro `ass=file.ass`
    → ffmpeg/libass renderiza karaoke en el video
    ↓
clip_final.mp4 con captions animadas
```

---

## Criterios de completitud

- `"capcut"` genera `.ass` con escala+fade visible en el video final
- `"karaoke"` genera `.ass` con wipe amarillo sincronizado con el audio
- `"subtitles"` sigue funcionando igual (SRT sin cambios)
- El filtro `ass=` funciona en Railway (libass disponible vía ffmpeg)
- Botón "Karaoke" visible en la UI
