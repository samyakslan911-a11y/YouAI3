import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

PROFILES_FILE = Path("data/profiles.json")

_PROFILE_PROMPT = """\
Eres un experto en content marketing para Instagram y TikTok.
Crea el perfil de IA especializada para generar carruseles virales en esta categoría: "{name}"

Responde SOLO con JSON válido, sin markdown, exactamente este schema:
{{
  "expert_context": "Instrucciones de sistema (200-300 palabras) que definen qué sabe esta IA, su tono, terminología del nicho, qué ángulos de contenido prioriza, qué errores evita",
  "style": "uno de: botanico|dark_jungle|terracota|aesthetic — elige el que mejor encaja visualmente",
  "content_angles": ["5 ángulos de contenido que más engagement generan en este nicho"],
  "image_keywords": ["6 keywords en inglés para buscar fotos de fondo en Pexels"]
}}"""


@dataclass
class ContentProfile:
    id: str
    name: str
    expert_context: str
    style: str
    content_angles: list[str]
    image_keywords: list[str]
    created_at: str


def load_profiles() -> list[ContentProfile]:
    if not PROFILES_FILE.exists():
        return []
    raw = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    return [ContentProfile(**p) for p in raw]


def save_profiles(profiles: list[ContentProfile]) -> None:
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILES_FILE.write_text(
        json.dumps([asdict(p) for p in profiles], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_profile(profile_id: str) -> ContentProfile | None:
    for p in load_profiles():
        if p.id == profile_id:
            return p
    return None


def delete_profile(profile_id: str) -> bool:
    profiles = load_profiles()
    filtered = [p for p in profiles if p.id != profile_id]
    if len(filtered) == len(profiles):
        return False
    save_profiles(filtered)
    return True


def generate_profile(name: str) -> ContentProfile:
    from google import genai
    from google.genai import errors as genai_errors

    api_key = os.environ["GOOGLE_API_KEY"]
    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    fallbacks = ["gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-flash-lite-latest"]
    models_to_try = [primary] + [m for m in fallbacks if m != primary]

    client = genai.Client(api_key=api_key)
    prompt = _PROFILE_PROMPT.format(name=name)

    last_err = None
    raw = None
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt)
                log.info(f"Profile generated with model: {model_name}")
                raw = response.text.strip()
                break
            except genai_errors.ServerError as e:
                last_err = e
                wait = 8 * (attempt + 1)
                log.warning(f"  {model_name} 503, retrying in {wait}s (attempt {attempt+1}/3)...")
                time.sleep(wait)
        else:
            log.warning(f"  {model_name} exhausted, trying next model...")
            continue
        break
    else:
        raise RuntimeError(f"All Gemini models failed: {last_err}")

    import re as _re
    raw = _re.sub(r'^```[a-z]*\s*', '', raw, flags=_re.MULTILINE)
    raw = _re.sub(r'```\s*$', '', raw, flags=_re.MULTILINE)
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
                raw = raw[start:i + 1]
                break

    data = json.loads(raw)

    profile = ContentProfile(
        id=str(uuid.uuid4())[:8],
        name=name,
        expert_context=data["expert_context"],
        style=data["style"],
        content_angles=data["content_angles"],
        image_keywords=data["image_keywords"],
        created_at=date.today().isoformat(),
    )

    profiles = load_profiles()
    profiles.append(profile)
    save_profiles(profiles)

    return profile
