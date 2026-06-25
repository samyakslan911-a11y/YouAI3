import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.utils.config import OUTPUT_DIR

log = logging.getLogger(__name__)

DB_PATH = OUTPUT_DIR / "jobs.db"

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


def _init_table() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_profiles (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                expert_context TEXT NOT NULL,
                style         TEXT NOT NULL,
                content_angles TEXT NOT NULL,
                image_keywords TEXT NOT NULL,
                created_at    TEXT NOT NULL
            )
        """)


def _row(row: tuple) -> ContentProfile:
    return ContentProfile(
        id=row[0], name=row[1], expert_context=row[2], style=row[3],
        content_angles=json.loads(row[4]),
        image_keywords=json.loads(row[5]),
        created_at=row[6],
    )


def load_profiles() -> list[ContentProfile]:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, name, expert_context, style, content_angles, image_keywords, created_at "
            "FROM content_profiles ORDER BY created_at"
        ).fetchall()
    return [_row(r) for r in rows]


def get_profile(profile_id: str) -> ContentProfile | None:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, name, expert_context, style, content_angles, image_keywords, created_at "
            "FROM content_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
    return _row(row) if row else None


def delete_profile(profile_id: str) -> bool:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("DELETE FROM content_profiles WHERE id = ?", (profile_id,))
    return cursor.rowcount > 0


def _save(profile: ContentProfile) -> None:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO content_profiles "
            "(id, name, expert_context, style, content_angles, image_keywords, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                profile.id, profile.name, profile.expert_context, profile.style,
                json.dumps(profile.content_angles, ensure_ascii=False),
                json.dumps(profile.image_keywords, ensure_ascii=False),
                profile.created_at,
            ),
        )


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
    raw = _re.sub(r"^```[a-z]*\s*", "", raw, flags=_re.MULTILINE)
    raw = _re.sub(r"```\s*$", "", raw, flags=_re.MULTILINE)
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
                raw = raw[start : i + 1]
                break

    data = json.loads(raw)

    valid_styles = {"botanico", "dark_jungle", "terracota", "aesthetic"}
    style = data.get("style", "botanico")
    if style not in valid_styles:
        style = "botanico"

    profile = ContentProfile(
        id=str(uuid.uuid4())[:8],
        name=name,
        expert_context=data["expert_context"],
        style=style,
        content_angles=data.get("content_angles", []),
        image_keywords=data.get("image_keywords", []),
        created_at=date.today().isoformat(),
    )

    _save(profile)
    return profile
