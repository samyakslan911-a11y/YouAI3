# Captions + Face Tracking — Spec de Diseño
**Fecha:** 2026-06-24
**Proyecto:** YouAI3
**Estado:** Aprobado

---

## Contexto

YouAI3 genera clips 9:16 desde videos YouTube. Hoy el crop es siempre centrado y las captions son texto estático del hook quemado sin timing. El resultado se ve amateurish: si el hablante no está al centro, sale cortado, y sin subtítulos sincronizados el clip muere en feed sin audio.

---

## Objetivo

1. **Face tracking suave:** el crop 9:16 sigue la cara activa con EMA, sin saltos bruscos.
2. **Captions quemadas con timing:** dos estilos seleccionables — CapCut (una palabra grande) y Subtítulos (3-4 palabras, inferior).
3. **Toggle en UI:** el usuario elige estilo de captions y activa/desactiva face tracking antes de procesar.

---

## Arquitectura

### Módulos modificados

| Archivo | Cambio |
|---|---|
| `src/services/editor.py` | Face tracking + nueva lógica de captions por timing |
| `src/services/transcriber.py` | Añadir timing por palabra via interpolación |
| `api_server.py` | Nuevos campos en `ProcessRequest` |
| `web/app/page.tsx` | Toggle de captions y face tracking en ProcessSection |
| `requirements-prod.txt` | Añadir `opencv-python-headless` |
| `Dockerfile` | Añadir `fonts-liberation` |

---

## Face Tracking

### Función: `_detect_face_track(video_path, start, end) → int`

**Entrada:** path al video original, timestamps del segmento
**Salida:** offset X en píxeles para el crop (relativo al centro)

**Algoritmo:**
1. Samplear 20 frames distribuidos uniformemente dentro de `[start, end]`
2. Detectar caras con OpenCV DNN (`res10_300x300_ssd_iter_140000.caffemodel`) — más robusto que Haar cascades, funciona con perfiles y caras parciales
3. Por cada frame: si hay cara, registrar centro X. Si no, marcar como `None`
4. Aplicar Exponential Moving Average (α=0.15) sobre la serie de centros X, ignorando `None`
5. Retornar offset = `media_suavizada - centro_video`
6. **Fallback:** si < 30% de los frames tienen cara detectada, retornar `0` (crop centrado)

### Modificación: `cut_and_format(video_path, start, end, output_path, face_x_offset=0)`

El filtro ffmpeg actual:
```
[0:v]scale=1080:1920:...,crop=1080:1920[bg];
[0:v]scale=...[fg];
[bg][fg]overlay=(W-w)/2:(H-h)/2
```

Con face tracking: el `overlay` del foreground se ajusta en X según `face_x_offset`, clampado para no salir del frame.

---

## Captions con Timing

### Timing por palabra: `_interpolate_word_timing(segments, clip_start, clip_end) → list[WordEvent]`

Los segmentos de transcripción tienen `start`, `end`, `text` a nivel de frase. Para timing por palabra:

1. Filtrar segmentos que intersectan `[clip_start, clip_end]`
2. Para cada segmento: dividir `text` en palabras, distribuir proporcionalmente en el rango `[seg.start, seg.end]`
3. Normalizar timestamps: restar `clip_start` para que el clip empiece en 0
4. Retornar lista de `{word, start, end}` en segundos relativos al clip

**Limitación conocida:** el timing es aproximado (no word-level real). Suficiente para sincronización visual; se puede mejorar en el futuro con Whisper word-level.

### Generación de SRT: `_build_srt(word_events, style) → Path`

Escribe archivo `.srt` temporal en `/tmp`.

**Estilo CapCut:**
- Una palabra por entrada SRT
- Cada entrada dura exactamente la duración de esa palabra
- `force_style`: `FontSize=72,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=4,Shadow=1,MarginV=200,Alignment=2`

**Estilo Subtítulos:**
- Agrupar palabras en chunks de 4
- Cada chunk dura la suma de sus palabras
- `force_style`: `FontSize=48,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=3,MarginV=80,Alignment=2`

### Quemado: integración en `cut_and_format()`

Agregar filtro `subtitles=<srt_path>:force_style='...'` al final del filter_complex, tras el overlay. El archivo SRT se elimina al finalizar.

---

## API

### `ProcessRequest` (api_server.py)

```python
class ProcessRequest(BaseModel):
    url: str
    dry_run: bool = False
    caption_style: Literal["capcut", "subtitles", "none"] = "capcut"
    face_track: bool = True
```

### Flujo en `_run_pipeline()`

`process_segment()` recibe `caption_style` y `face_track` y los pasa a `editor`.

---

## UI

### ProcessSection — nuevos controles

Antes del botón "Generar clips", dos controles en línea:

```
[ 🎯 Face tracking  ●──  ON ]   [ CC  CapCut ▾ ]
```

- Face tracking: toggle on/off (default ON)
- Captions: dropdown `CapCut / Subtítulos / Sin captions` (default CapCut)

Los valores se incluyen en el body del POST a `/api/jobs`.

---

## Dependencias

**`requirements-prod.txt`:**
```
opencv-python-headless>=4.8.0
```

**`Dockerfile`:**
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
```

El modelo DNN de OpenCV (`res10_300x300_ssd_iter_140000`) se descarga una vez en Railway al primer uso y se cachea en `/tmp`. Pesa ~10MB.

---

## Casos límite

| Caso | Comportamiento |
|---|---|
| Sin cara detectable en el clip | Crop centrado (fallback silencioso) |
| Transcripción vacía para el segmento | Estilo `none` automático para ese clip |
| SRT file error | Log warning, continuar sin captions |
| OpenCV no disponible | Importar solo si `face_track=True`, fallar con mensaje claro |

---

## Criterios de éxito

- Clips con cara: el sujeto aparece centrado en ≥90% de los frames
- Captions CapCut: palabras visibles, sincronizadas ±0.5s con el audio
- Sin regresión: clips existentes sin face_track siguen funcionando igual
- Tiempo extra de procesamiento por clip: < 30s (muestreo + SRT generation)
