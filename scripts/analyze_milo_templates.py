#!/usr/bin/env python3
"""
Analiza los templates Canva de @milokira con Gemini Vision.
Genera specs JSON focalizados en zonas de texto:
  - qué placeholder hay que borrar (clear_zones)
  - cómo renderizar el texto dinámico encima (text_elements)

El PNG queda como fondo — el diseño gráfico (paneles, formas, colores) se respeta.
El compositor PIL solo toca el texto.

Uso:
    python scripts/analyze_milo_templates.py           # solo los que faltan
    python scripts/analyze_milo_templates.py --force   # regenerar todos
    python scripts/analyze_milo_templates.py cover tip # solo esos keys
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TEMPLATES_DIR = ROOT / "assets" / "templates" / "milokira"
SPECS_DIR     = TEMPLATES_DIR / "specs"
SPECS_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES: dict[str, dict] = {
    "cover": {
        "file": "1.png",
        "size": (1080, 1080),
        "role": "portada con paneles de monstera laterales, titular bicolor una-palabra-por-línea, foto de planta en círculo sage",
    },
    "guide": {
        "file": "2.png",
        "size": (1080, 1080),
        "role": "guía rápida con paneles laterales, small label, headline grande, card numerada 01/02/03/04",
    },
    "species": {
        "file": "Planta del mes.png",
        "size": (1080, 1080),
        "role": "planta del mes en fondo sage, label PLANTA DEL MES, headline bicolor, card cream con tabla datos key:value",
    },
    "cta": {
        "file": "Pregunta CTA.png",
        "size": (1080, 1080),
        "role": "CTA con paneles laterales, label CUÉNTANOS, headline bicolor última-palabra-lavanda, botón pill sage",
    },
    "portada": {
        "file": "Portada.png",
        "size": (1080, 1350),
        "role": "portada v2 con paneles edge-to-edge, titular bicolor, subtítulo, botón DESLIZA",
    },
    "l1_hero": {
        "file": "L1 Hero.png",
        "size": (1080, 1350),
        "role": "hero con paneles medios, titular bicolor, círculo sage con foto de planta, subtítulo",
    },
    "l2_list": {
        "file": "L2 List.png",
        "size": (1080, 1350),
        "role": "lista badges con paneles, label, headline, items numerados con círculos",
    },
    "l3_data": {
        "file": "L3 Data.png",
        "size": (1080, 1350),
        "role": "fondo sage, paneles, titular bicolor, card cream con foto y tabla key:value",
    },
    "l4_quote": {
        "file": "L4 Quote.png",
        "size": (1080, 1350),
        "role": "quote en cream, paneles, comillas decorativas, texto de cita centrado, atribución",
    },
    "l5_split": {
        "file": "L5 Split.png",
        "size": (1080, 1350),
        "role": "mitad izquierda sage con foto, mitad derecha cream con titular bicolor y body text",
    },
    "l6_grid": {
        "file": "L6 Grid.png",
        "size": (1080, 1350),
        "role": "grid 2x2 con paneles, headline, 4 tarjetas alternando lavanda/cream",
    },
    "lista": {
        "file": "Lista.png",
        "size": (1080, 1350),
        "role": "checklist con paneles anchos, label CHECKLIST, headline, lista 01-05",
    },
    "cita": {
        "file": "Cita.png",
        "size": (1080, 1350),
        "role": "fondo sage sólido, decoración '❝❝' lavanda grande fija, texto de cita cream, atribución",
    },
    "cta_big": {
        "file": "CTA.png",
        "size": (1080, 1350),
        "role": "paneles edge-to-edge, titular bicolor, subtítulo, botón DESLIZA",
    },
    "tip": {
        "file": "Tip.png",
        "size": (1080, 1350),
        "role": "paneles anchos, sparkle, label TIP DEL DÍA, headline grande, caja lavanda con body text, atribución",
    },
}

PROMPT = """\
Eres un experto en diseño gráfico analizando un template de Instagram de @milokira (canal botánico).
Template: "{key}" — {role}
Imagen: {w}×{h} píxeles.

TAREA PRINCIPAL: identificar todo el TEXTO del template para que el compositor PIL pueda:
1. BORRAR el texto placeholder que trae el diseño de Canva
2. ESCRIBIR texto dinámico nuevo en su lugar con el mismo estilo

El diseño gráfico (paneles de hojas, fondos, formas, botones, cards) se mantiene del PNG.
Solo nos interesa el texto: dónde está, qué estilo tiene, y qué zona hay que limpiar antes de reescribir.

Responde SOLO con JSON válido, sin markdown, sin explicaciones:

{{
  "id": "{key}",
  "description": "descripción de una línea del template",
  "bg_color_rgb": [R, G, B],
  "clear_zones": [
    {{
      "label": "nombre descriptivo de qué zona se limpia",
      "x": int, "y": int, "w": int, "h": int,
      "fill_rgb": [R, G, B],
      "notes": "por qué se limpia esta zona"
    }}
  ],
  "text_elements": [
    {{
      "role": "sparkle | label | headline | subheadline | body | numbered_item | button_text | handle | quote | attribution | table_key | table_value",
      "x": int,
      "y": int,
      "w": int,
      "h": int,
      "cx": int,
      "font_size": int,
      "font_weight": "extra_bold" | "bold" | "semibold" | "regular",
      "color_rgb": [R, G, B],
      "text_align": "center" | "left" | "right",
      "uppercase": true | false,
      "style_notes": "descripción del estilo: bicolor, alternante, última palabra, etc.",
      "bicolor_colors": [[R,G,B],[R,G,B]] o null,
      "placeholder_text": "texto de ejemplo visible en la imagen"
    }}
  ]
}}

NOTAS IMPORTANTES:
- clear_zones: rectángulos que hay que pintar con fill_rgb ANTES de escribir el texto nuevo. Deben cubrir exactamente el área del placeholder pero no más (para no tapar el diseño gráfico).
- text_elements: posición y estilo del texto que PIL va a dibujar. x,y = esquina superior izquierda. cx = centro horizontal si aplica.
- Si hay sparkle (estrella de 4 puntas decorativa): incluirla en text_elements como role:"sparkle" con su posición y tamaño.
- El handle @milokira siempre está al fondo — incluirlo.
- Sé muy preciso con las coordenadas — van directo a PIL ImageDraw en una imagen {w}×{h}.
"""


def _extract_json(raw: str) -> str:
    raw = re.sub(r"^```[a-z]*\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)
    raw = raw.strip()
    depth, start = 0, -1
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                return raw[start : i + 1]
    return raw


def analyze(key: str, info: dict, client) -> dict | None:
    from google.genai import types
    import PIL.Image as PILImage

    path = TEMPLATES_DIR / info["file"]
    if not path.exists():
        print(f"  SKIP — archivo no encontrado: {path}")
        return None

    img = PILImage.open(path).convert("RGB")
    w, h = img.size

    prompt = PROMPT.format(key=key, role=info["role"], w=w, h=h)

    print(f"  Enviando a Gemini Vision ({w}×{h})...", end="", flush=True)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[img, prompt],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            max_output_tokens=8192,
        ),
    )

    raw = response.text.strip()
    json_str = _extract_json(raw)
    spec = json.loads(json_str)
    spec["source_file"] = info["file"]
    spec["source_size"] = [w, h]

    n_text  = len(spec.get("text_elements", []))
    n_clear = len(spec.get("clear_zones", []))
    print(f" OK ({n_text} zonas de texto, {n_clear} zonas a limpiar)")
    return spec


def main() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY no encontrada en el entorno")
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    force       = "--force" in sys.argv
    keys_filter = [a for a in sys.argv[1:] if not a.startswith("--")]
    targets     = {k: v for k, v in TEMPLATES.items() if not keys_filter or k in keys_filter}

    ok = skipped = errors = 0
    for key, info in targets.items():
        spec_path = SPECS_DIR / f"{key}.json"

        if spec_path.exists() and not force:
            print(f"✓ {key}: ya tiene spec (usa --force para regenerar)")
            skipped += 1
            continue

        print(f"> {key}  [{info['file']}]")
        try:
            spec = analyze(key, info, client)
            if spec is not None:
                spec_path.write_text(
                    json.dumps(spec, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"  Guardado: {spec_path.relative_to(ROOT)}")
                ok += 1
        except json.JSONDecodeError as e:
            print(f"  ERROR JSON: {e}")
            errors += 1
        except Exception as e:
            print(f"  ERROR {type(e).__name__}: {e}")
            errors += 1

    print(f"\nFin: {ok} analizados, {skipped} ya existían, {errors} errores")
    print(f"Specs en: {SPECS_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
