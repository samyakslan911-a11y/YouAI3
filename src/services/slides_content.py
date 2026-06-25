import json, os, logging
from typing import Literal

log = logging.getLogger(__name__)

SlidStyle = Literal["terracota", "botanico", "aesthetic", "dark_jungle"]

_LAYOUT_RULES = """
Layout rules (apply automatically based on body length):
- body empty or ≤5 words → layout: "hero"
- body 1-2 sentences → layout: "split"
- body with bullet points (lines starting with •) → layout: "card"
- type pattern_interrupt or quote → layout: "quote"
"""

_SYSTEM = """Eres un experto en contenido viral para Instagram y YouTube Shorts
especializado en plantas de interior, cactus y suculentas.
Generas carruseles educativos que combinan valor real con alta retención.
Respondes SOLO con JSON válido, sin markdown, sin explicaciones."""

_PROMPT = """\
Genera un set de 10 slides para Instagram sobre el tema: "{topic}"
Estilo visual: {style}
{series_hint}

Sigue esta estructura probada:
- Slide 1 (hook): headline impactante ≤8 palabras + emoji. Body vacío.
- Slides 2-3 (contexto): por qué importa este tema
- Slides 4-8 (valor): UNA especie/idea por slide con datos reales
- Slide 9 (pattern_interrupt): stat o dato sorprendente con fuente
- Slide 10 (cta): call to action + "Parte N en 48h" si es serie

{layout_rules}

Para cada slide que mencione una especie de planta:
- Pon el nombre científico en "species" (ej: "Echeveria subsessilis")
- image_type: "species" → se buscará en iNaturalist
Para slides de ambiente/concepto:
- image_type: "lifestyle"
- image_query: query descriptivo en inglés para Pexels

Devuelve exactamente este JSON:
{{
  "title": "título del set completo",
  "hook_variants": ["variante A del hook", "variante B", "variante C"],
  "slides": [
    {{
      "index": 0,
      "type": "hook|context|value|pattern_interrupt|cta",
      "layout": "hero|split|card|quote",
      "headline": "texto del titular",
      "body": "texto del cuerpo (puede tener \\n para saltos)",
      "image_type": "species|lifestyle",
      "image_query": "query en inglés para Pexels si lifestyle",
      "species": "Nombre científico o null"
    }}
  ],
  "hashtags": {{
    "instagram": ["#tag1", "#tag2"],
    "tiktok": ["#tag1", "#tag2"],
    "pinterest": ["keyword1", "keyword2"]
  }}
}}
"""


def generate_content(topic: str, style: SlidStyle, series_part: int | None = None) -> dict:
    import time
    from google import genai
    from google.genai import errors as genai_errors

    api_key = os.environ["GOOGLE_API_KEY"]
    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    fallbacks = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-flash-lite-latest"]
    models_to_try = [primary] + [m for m in fallbacks if m != primary]

    client = genai.Client(api_key=api_key)

    series_hint = ""
    if series_part:
        series_hint = f"Este es la Parte {series_part} de una serie. Referencia partes anteriores y anuncia la siguiente."

    prompt = _SYSTEM + "\n\n" + _PROMPT.format(
        topic=topic,
        style=style,
        series_hint=series_hint,
        layout_rules=_LAYOUT_RULES,
    )

    log.info(f"Generando contenido para: {topic} ({style})")
    last_err = None
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                log.info(f"  modelo usado: {model_name}")
                raw = response.text.strip()
                break
            except genai_errors.ServerError as e:
                last_err = e
                wait = 8 * (attempt + 1)
                log.warning(f"  {model_name} 503, reintentando en {wait}s (intento {attempt+1}/3)...")
                time.sleep(wait)
        else:
            log.warning(f"  {model_name} agotado, probando siguiente modelo...")
            continue
        break
    else:
        raise RuntimeError(f"Todos los modelos Gemini fallaron: {last_err}")

    # Strip markdown code fences if present
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # Extract first complete JSON object (ignore trailing text)
    depth, start = 0, -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                raw = raw[start:i + 1]
                break

    data = json.loads(raw)
    _validate(data)
    log.info(f"  {len(data['slides'])} slides generados: {data['title']}")
    return data


def _validate(data: dict) -> None:
    assert "slides" in data, "Missing slides"
    assert "hashtags" in data, "Missing hashtags"
    assert len(data["slides"]) >= 8, f"Only {len(data['slides'])} slides"
    for s in data["slides"]:
        assert "headline" in s, f"Slide {s.get('index')} missing headline"
        assert "layout" in s, f"Slide {s.get('index')} missing layout"
        assert "image_type" in s, f"Slide {s.get('index')} missing image_type"
