# Slides Generator

**Fecha:** 2026-06-24
**Estado:** Aprobado
**Prioridad:** #2 del roadmap

---

## Objetivo

Generar sets de slides educativos sobre plantas de interior, cactus y suculentas:
- 10 imágenes 1080x1350 (Instagram carrusel)
- 1 video 1080x1920 (Shorts/TikTok/Reels)

Cada slide tiene imagen que coincide exactamente con su contenido, layout adaptativo según densidad de texto, y el sistema aprende de métricas reales para mejorar con el tiempo.

---

## Arquitectura

```
POST /api/slides  {topic, style, series_part?}
        ↓
slides_generator.py  (orquestador)
    ├── slides_content.py    → Gemini genera 10 slides con layout_hint por slide
    ├── slides_imager.py     → iNaturalist + Pexels + Gemini Vision elige foto
    ├── slides_composer.py   → Pillow compone según layout_hint
    └── slides_video.py      → ffmpeg Ken Burns + crossfade → MP4 1080x1920

output/slides/{slug}/
    ├── images/  01.png … 10.png
    ├── video.mp4
    └── metadata.json  (hashtags, hook_variants, design_id, image_sources)
```

---

## Pipeline de imagen precisa

### Fuentes por orden de prioridad

1. **iNaturalist API** — fotos etiquetadas por especie exacta (gratis, sin key)
   - Endpoint: `https://api.inaturalist.org/v1/observations?taxon_name={species}&photos=true&quality_grade=research`
   - Devuelve fotos con coordenadas de calidad "research" — verificadas por expertos
   - Ideal para slides de especie específica ("Echeveria subsessilis", "Mammillaria gracilis")

2. **Pexels API** — fotos lifestyle y estéticas (gratis, key requerida: `PEXELS_API_KEY`)
   - Endpoint: `GET /v1/search?query={query}&per_page=8&orientation=portrait`
   - Ideal para slides de ambiente ("suculenta en ventana", "terrario en sala")

3. **Fallback** — gradiente del estilo si ambas APIs fallan

### Gemini Vision como curador

Por cada slide, el pipeline descarga 5-8 fotos candidatas y Gemini Vision elige la mejor evaluando:
- Composición (regla de tercios, espacio para texto)
- Iluminación (natural preferida, sin flash duro)
- Fondo (limpio o bokeh, sin distracciones)
- Coincidencia con el contenido del slide

```python
def pick_best_photo(candidates: list[Path], slide_content: dict) -> Path:
    # Gemini Vision recibe todas las fotos + el texto del slide
    # Devuelve el índice de la mejor foto y justificación
```

### Identificación de especie

Gemini extrae el nombre científico del contenido del slide:
- "Echeveria — absorbe CO₂ de noche" → `taxon_name=Echeveria`
- "Cactus de navidad" → `taxon_name=Schlumbergera`
- "Cómo regar suculentas" → no hay especie → usar Pexels lifestyle

---

## Contenido generado por Gemini

Schema que Gemini devuelve por set:

```json
{
  "title": "5 suculentas que purifican el aire",
  "hook_variants": ["hook A", "hook B", "hook C"],
  "slides": [
    {
      "index": 0,
      "type": "hook",
      "layout": "hero",
      "headline": "5 suculentas que\npurifican el aire 🌵",
      "body": "",
      "image_type": "lifestyle",
      "image_query": "succulents collection bright window",
      "species": null
    },
    {
      "index": 3,
      "type": "value",
      "layout": "split",
      "headline": "Echeveria",
      "body": "Absorbe CO₂ de noche mediante\nmetabolismo CAM. Ideal en dormitorio.\nRegar cada 2 semanas en verano.",
      "image_type": "species",
      "image_query": "echeveria succulent",
      "species": "Echeveria"
    },
    {
      "index": 8,
      "type": "pattern_interrupt",
      "layout": "quote",
      "headline": "Las plantas de interior\nreducen el estrés 37%",
      "body": "Universidad de Exeter, 2024",
      "image_type": "lifestyle",
      "image_query": "person relaxing plants indoor",
      "species": null
    }
  ],
  "hashtags": {
    "instagram": ["#suculentas", "#plantasdeinterior", "#cactus"],
    "tiktok": ["#plantitas", "#suculentasdeinstagram"],
    "pinterest": ["succulents indoor", "cactus care tips"]
  }
}
```

**Regla de layout automático:**
- `body` vacío o ≤ 5 palabras → `layout: "hero"`
- `body` 1-2 oraciones → `layout: "split"`
- `body` con bullets/datos técnicos → `layout: "card"`
- `type: "pattern_interrupt"` → `layout: "quote"`

---

## 4 Layouts adaptativos (Pillow)

### `hero` — imagen protagonista
```
┌─────────────────────┐
│                     │
│   [FOTO FULL]       │
│                     │
│                     │
│                     │
│  ░░░░░░░░░░░░░░░░░  │ ← overlay 25% solo en franja texto
│  HEADLINE GRANDE    │
│  ─────              │
└─────────────────────┘
```
- Overlay: solo franja inferior 35% (gradiente 0→70%)
- Headline: bold 82px, blanco
- Sin body
- Texto centrado verticalmente en franja

### `split` — foto + lectura
```
┌─────────────────────┐
│                     │
│   [FOTO 55%]        │
│                     │
├─────────────────────┤
│ ░░░░░░░░░░░░░░░░░░░ │ ← área de lectura overlay 85%
│ Headline 68px       │
│ ─────               │
│ Body text 36px      │
│ en múltiples líneas │
│ sin límite          │
└─────────────────────┘
```
- Foto: crop centro-superior, 55% del alto
- Área de lectura: overlay sólido 85% en 45% inferior
- Headline: 68px, body: 36px sin límite de líneas

### `card` — tarjeta flotante
```
┌─────────────────────┐
│  [FOTO FULL+BLUR]   │
│  ┌───────────────┐  │
│  │ Headline 62px │  │
│  │ ─────         │  │
│  │ • Punto 1     │  │
│  │ • Punto 2     │  │
│  │ • Punto 3     │  │
│  └───────────────┘  │
│                     │
└─────────────────────┘
```
- Fondo: foto con Gaussian blur radius 8
- Tarjeta: rectángulo redondeado, negro/color 80% opacidad
- Soporta bullet points (body con líneas `• `)
- Headline: 62px, bullets: 34px

### `quote` — texto protagonista
```
┌─────────────────────┐
│                     │
│  [FOTO MUY BLURRED] │
│  ┌ " ─────────────┐ │
│  │  TEXTO GRANDE  │ │
│  │  EN CENTRADO   │ │
│  └ ─────────────" ┘ │
│  fuente / dato      │
│                     │
└─────────────────────┘
```
- Fondo: foto con blur radius 12 + overlay 60%
- Sin tarjeta — texto directamente sobre fondo
- Headline: 86px, muy centrado verticalmente
- Attribution: 32px abajo del acento

---

## Estilos visuales (4 paletas)

Encima de los layouts, cada estilo aplica sus colores y fuentes:

| Parámetro | terracota | botanico | aesthetic | dark_jungle |
|-----------|-----------|----------|-----------|-------------|
| Overlay color | #4B1A0A | #0A231A | #3C2545 | #030C06 |
| Accent | #D78A48 | #B6943A | #D7AFC8 | #4BC873 |
| Text primary | #FFF5E1 | #F2EECB | #FCF5FA | #FFFFFF |
| Font headline | Arial Bold | Arial Bold | Segoe UI Semibold | Arial Bold |
| Size headline (hero) | 82 | 78 | 72 | 86 |

---

## Memoria de diseño (auto-mejora)

Tabla nueva en `output/jobs.db`:

```sql
CREATE TABLE IF NOT EXISTS design_memory (
    id          TEXT PRIMARY KEY,
    created_at  TEXT,
    topic       TEXT,
    style       TEXT,
    layouts_used TEXT,          -- JSON ["hero","split","card"]
    image_sources TEXT,         -- JSON {"inat": 6, "pexels": 3, "fallback": 1}
    hook_pattern TEXT,          -- "numero + dolor" | "pregunta" | "dato impactante"
    published_at TEXT,
    platform    TEXT,
    -- métricas (se rellenan después de 7 días)
    saves       INTEGER,
    reach       INTEGER,
    profile_visits INTEGER,
    saves_rate  REAL,           -- saves / reach
    perf_score  REAL            -- calculado: saves_rate * 0.6 + profile_visits_rate * 0.4
);
```

Cuando se genera un nuevo set, Gemini recibe los 5 diseños con mayor `perf_score` como contexto:

```
"Los siguientes sets tuvieron mejor rendimiento en esta cuenta:
- topic: cactus de navidad, layout: split+hero, hook: 'Lo que nadie te dice', saves_rate: 0.12
- topic: echeveria variedad, layout: hero+quote, hook: '5 tipos que...', saves_rate: 0.09
Genera contenido siguiendo patrones similares."
```

---

## Video (1080x1920)

- Cada slide: 3.5s display + efecto Ken Burns (zoom 100%→108%, dirección alterna por slide)
- Slides 1080x1350 se escalan a 1080x1920 con barras top/bottom blurred (mismo fondo, no negro)
- Cross-fade 0.4s entre slides
- Total: ~38s para 10 slides
- Sin audio (silencioso para publicación con trending sound en la app)

---

## API

```
POST /api/slides
Body: { topic, style, series_part? }
Response: { slug, images[], video_url, hashtags, hook_variants, design_id }

GET  /api/slides
Response: [{ slug, topic, style, created_at, image_count }]

GET  /api/slides/{slug}
Response: metadata completo + URLs

POST /api/slides/{slug}/publish
Body: { platform }
Response: { url }  (usa publisher.py existente)
```

---

## Archivos nuevos

| Archivo | Responsabilidad |
|---------|-----------------|
| `src/services/slides_content.py` | Gemini genera schema de 10 slides |
| `src/services/slides_imager.py` | iNaturalist + Pexels + Gemini Vision picker |
| `src/services/slides_composer.py` | Pillow: 4 layouts x 4 estilos |
| `src/services/slides_video.py` | ffmpeg Ken Burns + crossfade |
| `src/services/slides_generator.py` | Orquestador, escribe output/ y design_memory |

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `api_server.py` | 3 endpoints nuevos `/api/slides` |
| `src/services/job_store.py` | tabla `design_memory` |
| `web/app/page.tsx` | sección "Slides" nueva |
| `web/lib/api.ts` | métodos `createSlides`, `listSlides`, `getSlides` |
| `requirements-prod.txt` | sin cambios (Pillow ya está) |

## Variables de entorno nuevas

| Variable | Fuente | Requerida |
|----------|--------|-----------|
| `PEXELS_API_KEY` | pexels.com/api (gratis) | Sí |

iNaturalist no requiere key.

---

## Criterios de completitud

- `POST /api/slides` genera 10 PNG + 1 MP4 en `output/slides/{slug}/`
- Slides de especie específica usan foto de iNaturalist de esa especie
- Slides lifestyle usan Pexels con query contextual
- Gemini Vision descarta fotos de mala calidad automáticamente
- Los 4 layouts se usan según densidad de texto del slide
- `design_memory` registra cada set generado
- UI muestra carrusel navegable + video + hashtags copiables
