import json, os, logging
from typing import Literal

log = logging.getLogger(__name__)

SlidStyle = Literal["terracota", "botanico", "aesthetic", "dark_jungle"]

_LAYOUT_RULES = """
Layout rules:
- Slide 1 (hook) SIEMPRE → layout: "minimal" (solo headline, sin body)
- Slide 10 (cta) → layout: "hero" (solo headline, sin body)
- body empty o ≤5 palabras → layout: "hero" o "minimal"
- body 1-2 oraciones (max 25 palabras) → layout: "split"
- body con exactamente 3-4 bullets → layout: "card"
- type pattern_interrupt o quote → layout: "quote"
- slides de especie con datos clave → layout: "editorial" (se renderiza con número grande)
- Para más variedad, alterna: minimal→split→card→editorial→quote en slides 2-8.
"""

_SYSTEM = """Eres un experto en contenido viral para Instagram y YouTube Shorts.
Generas carruseles educativos que combinan valor real con alta retención.
Respondes SOLO con JSON válido, sin markdown, sin explicaciones."""

_QUALITY_RULES = """
REGLAS DE CALIDAD (obligatorias):
1. ORTOGRAFÍA: revisa cada palabra antes de responder. Cero errores ortográficos.
2. FRASES DIRECTAS: prohibido usar clichés como "pulgar verde", "manos en la tierra",
   "mundo verde". Usa lenguaje directo y concreto.
3. HEADLINE ≤10 palabras, sin comillas alrededor de frases comunes.
4. BODY en layout "split": máximo 2 oraciones cortas, total ≤25 palabras.
5. BODY en layout "card": exactamente 3-4 bullets. Cada bullet: "• texto ≤12 palabras".
   Sin sub-bullets, sin texto extra fuera de bullets.
6. BODY en layout "hero": vacío (string vacío "").
7. No empieces bullets con artículos (el/la/los/las). Ve directo al dato.
8. image_query en inglés: específico y visual, ej. "snake plant sansevieria pot windowsill".
"""

_STRUCTURES = {
    5:  "- Slide 1 (hook): headline impactante ≤8 palabras. Body vacío. layout: \"hero\"\n"
        "- Slides 2-3 (valor): UNA especie/idea por slide con 3-4 bullets de datos reales\n"
        "- Slide 4 (pattern_interrupt): stat sorprendente. layout: \"quote\"\n"
        "- Slide 5 (cta): call to action. layout: \"hero\"",

    7:  "- Slide 1 (hook): headline impactante ≤8 palabras. Body vacío. layout: \"hero\"\n"
        "- Slide 2 (contexto): por qué importa. layout: \"split\"\n"
        "- Slides 3-5 (valor): UNA especie/idea por slide con 3-4 bullets\n"
        "- Slide 6 (pattern_interrupt): stat sorprendente. layout: \"quote\"\n"
        "- Slide 7 (cta): call to action. layout: \"hero\"",

    10: "- Slide 1 (hook): headline impactante ≤8 palabras. Body vacío. layout: \"hero\"\n"
        "- Slides 2-3 (contexto): por qué importa. layout: \"split\" (máx 25 palabras body)\n"
        "- Slides 4-8 (valor): UNA especie/idea por slide con 3-4 bullets de datos reales\n"
        "- Slide 9 (pattern_interrupt): stat sorprendente. layout: \"quote\"\n"
        "- Slide 10 (cta): call to action. layout: \"hero\"",

    15: "- Slide 1 (hook): headline impactante ≤8 palabras. Body vacío. layout: \"hero\"\n"
        "- Slides 2-3 (contexto): por qué importa, datos de contexto. layout: \"split\"\n"
        "- Slides 4-12 (valor profundo): UNA especie/idea por slide con 3-4 bullets de datos reales\n"
        "- Slide 13 (resumen): los 3 puntos clave. layout: \"editorial\"\n"
        "- Slide 14 (pattern_interrupt): stat sorprendente. layout: \"quote\"\n"
        "- Slide 15 (cta): call to action. layout: \"hero\"",
}

_PROMPT = """\
Genera un set de {slide_count} slides para Instagram sobre el tema: "{topic}"
Estilo visual: {style}
{series_hint}

Estructura ({slide_count} slides):
{structure}

{layout_rules}

{quality_rules}

REGLAS DE IMAGE_QUERY (crítico para calidad visual):
- Escribe en inglés. Sé muy específico: planta + parte + contexto + lighting.
- INCORRECTO: "plant indoor", "succulent pot", "nature green"
- CORRECTO especie: "monstera deliciosa large leaf close-up natural light", "snake plant sansevieria narrow leaves terracotta pot", "fiddle leaf fig ficus lyrata bright room"
- CORRECTO lifestyle: "hands repotting plant soil close-up", "yellow leaf wilting close-up macro", "spider mites white webbing plant stem macro"
- Para cada slide usa una query DISTINTA, específica al contenido de ese slide.
- Evita queries genéricas. Pexels tiene millones de fotos — sé específico y encuentra la exacta.

REGLA DE image_type (crítico):
- Si el tema trata sobre una especie concreta (lithops, monstera, suculenta, etc.), los slides
  que MUESTRAN esa planta deben usar image_type: "species" y "species": nombre científico.
  Pexels NO tiene buenas fotos de especies nicho — iNaturalist sí.
- Solo usa image_type: "lifestyle" para slides que muestran acciones, suelo, manos, conceptos.
- EJEMPLO para tema "cuidado de lithops":
  INCORRECTO: image_type: "lifestyle", query: "lithops succulent close-up" → Pexels no tiene lithops
  CORRECTO:   image_type: "species", species: "Lithops", query: "lithops stones succulent top view"

Para slides de especie (image_type: "species"):
- "species": nombre científico exacto (ej. "Lithops", "Sansevieria trifasciata")
- image_query: nombre común inglés + parte visual + ambiente
Para slides de concepto (image_type: "lifestyle"):
- image_query: acción/objeto específico + contexto + detalle visual (ej. "overwatered plant drooping yellowing leaves close-up")

JSON de respuesta:
{{
  "title": "título del set completo",
  "hook_variants": ["variante A del hook", "variante B", "variante C"],
  "slides": [
    {{
      "index": 0,
      "type": "hook|context|value|pattern_interrupt|cta",
      "layout": "hero|split|card|quote|minimal|editorial",
      "headline": "texto del titular",
      "body": "texto del cuerpo",
      "image_type": "species|lifestyle",
      "image_query": "query muy específico en inglés para Pexels",
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


def generate_content(topic: str, style: SlidStyle, series_part: int | None = None, expert_context: str | None = None, slide_count: int = 10) -> dict:
    import time
    from google import genai
    from google.genai import errors as genai_errors, types

    api_key = os.environ["GOOGLE_API_KEY"]
    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    fallbacks = ["gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]
    models_to_try = [primary] + [m for m in fallbacks if m != primary]

    client = genai.Client(api_key=api_key)

    # Disable thinking — structured JSON generation doesn't need it and it
    # causes 2-5 min hangs. Only applies to 2.5-* models; ignored by others.
    _no_think = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=8192,
    )

    series_hint = ""
    if series_part:
        series_hint = f"Este es la Parte {series_part} de una serie. Referencia partes anteriores y anuncia la siguiente."

    system_base = _SYSTEM
    if expert_context:
        system_base = system_base + f"\n\nCONTEXTO EXPERTO:\n{expert_context}"

    valid_counts = (5, 7, 10, 15)
    sc = min(valid_counts, key=lambda x: abs(x - slide_count))
    structure = _STRUCTURES[sc]

    # Milokira uses Template 1 cover: hero slide needs care data in KEY:value format
    milokira_override = ""
    if style == "milokira":
        milokira_override = """
REGLA ESPECIAL PARA ESTILO MILOKIRA (cover card):
- Slide 1 (index 0): layout "hero". headline = nombre de la especie o tema (≤4 palabras).
  body OBLIGATORIO en este formato exacto (4 líneas con clave: valor):
  "LUZ: [tipo de luz]
RIEGO: [frecuencia]
HUMEDAD: [nivel]
DIFICULTAD: [nivel]"
  Si el tema no es una especie, usa las 4 claves más relevantes del tema.
  NO dejes body vacío para milokira — el cover muestra una tarjeta de datos.
"""

    prompt = system_base + "\n\n" + _PROMPT.format(
        topic=topic,
        style=style,
        series_hint=series_hint,
        layout_rules=_LAYOUT_RULES,
        quality_rules=_QUALITY_RULES + milokira_override,
        slide_count=sc,
        structure=structure,
    )

    log.info(f"Generando contenido para: {topic} ({style})")
    last_err = None
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=prompt, config=_no_think
                )
                log.info(f"  modelo usado: {model_name}")
                raw = response.text.strip()
                break
            except genai_errors.ServerError as e:
                last_err = e
                wait = 8 * (attempt + 1)
                log.warning(f"  {model_name} 503, reintentando en {wait}s (intento {attempt+1}/3)...")
                time.sleep(wait)
            except Exception as e:
                log.warning(f"  {model_name} error con thinking_config: {e!r}")
                # Model may not support thinking_config — retry without it
                try:
                    response = client.models.generate_content(model=model_name, contents=prompt)
                    log.info(f"  modelo usado (sin thinking_config): {model_name}")
                    raw = response.text.strip()
                    break
                except Exception as e2:
                    log.warning(f"  {model_name} fallback también falló: {e2!r}")
                    last_err = e2
                    break
        else:
            log.warning(f"  {model_name} agotado, probando siguiente modelo...")
            continue
        break
    else:
        raise RuntimeError(f"Todos los modelos Gemini fallaron: {last_err}")

    # Strip markdown code fences robustly
    import re as _re
    raw = _re.sub(r'^```[a-z]*\s*', '', raw, flags=_re.MULTILINE)
    raw = _re.sub(r'```\s*$', '', raw, flags=_re.MULTILINE)
    raw = raw.strip()

    # Extract first complete JSON object (brace-counting, ignores trailing text)
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

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido de Gemini: {e}\nRaw (primeros 300 chars): {raw[:300]}")

    _validate(data, min_slides=max(3, sc - 2))
    log.info(f"  {len(data['slides'])} slides generados: {data['title']}")
    return data


def _validate(data: dict, min_slides: int = 4) -> None:
    if "slides" not in data:
        raise ValueError("Missing slides")
    if "hashtags" not in data:
        raise ValueError("Missing hashtags")
    if len(data["slides"]) < min_slides:
        raise ValueError(f"Only {len(data['slides'])} slides (expected ≥{min_slides})")
    for s in data["slides"]:
        for field in ("headline", "layout", "image_type"):
            if field not in s:
                raise ValueError(f"Slide {s.get('index')} missing {field}")
