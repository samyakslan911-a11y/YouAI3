"""
Agente de investigación botánica: Gemini + Google Search grounding.
- Prompt corto (respuesta ~300 palabras) para velocidad
- Cache SQLite de 30 días para consultas repetidas
- Nunca bloquea el pipeline si falla
"""
import hashlib
import logging
import os
import sqlite3
import time
from pathlib import Path

log = logging.getLogger(__name__)

_CACHE_DB = Path(os.getenv("OUTPUT_DIR", "output")) / "research_cache.db"

_PROMPT = """\
Eres un botánico experto. Busca en Google información verificada sobre: "{topic}"

Responde en español con SOLO estos puntos, sin secciones extra:

NOMBRE CIENTIFICO: [género especie, familia]
LUZ: [tipo exacto y horas]
RIEGO: [frecuencia exacta por estación]
TEMPERATURA: [rango min-max °C]
HUMEDAD: [% ideal]
SUELO: [composición específica]
PROBLEMAS FRECUENTES: [top 3 con causa + solución en 1 línea cada uno]
DATOS CURIOSOS: [2-3 datos sorprendentes y verificables]
VARIEDADES: [2-3 variedades populares con diferencia clave]
TOXICIDAD: [sí/no para humanos, perros, gatos]
PROPAGACION: [método principal + tasa de éxito aproximada]

Máximo 300 palabras. Solo datos concretos, sin generalidades.
"""


def _cache_key(topic: str) -> str:
    return hashlib.sha256(topic.strip().lower().encode()).hexdigest()[:16]


def _get_cache(key: str) -> str | None:
    try:
        _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(_CACHE_DB)
        con.execute(
            "CREATE TABLE IF NOT EXISTS research "
            "(key TEXT PRIMARY KEY, result TEXT, ts INTEGER)"
        )
        row = con.execute(
            "SELECT result, ts FROM research WHERE key=?", (key,)
        ).fetchone()
        con.close()
        if row:
            age_days = (time.time() - row[1]) / 86400
            if age_days < 30:
                log.info(f"[research] Cache hit (age {age_days:.1f}d)")
                return row[0]
    except Exception as e:
        log.debug(f"[research] Cache read error: {e}")
    return None


def _set_cache(key: str, result: str) -> None:
    try:
        con = sqlite3.connect(_CACHE_DB)
        con.execute(
            "INSERT OR REPLACE INTO research VALUES (?,?,?)",
            (key, result, int(time.time())),
        )
        con.commit()
        con.close()
    except Exception as e:
        log.debug(f"[research] Cache write error: {e}")


def research_topic(topic: str) -> str:
    """
    Investiga el tema con Gemini + Google Search.
    Devuelve contexto experto (~300 palabras) para pasar a generate_content().
    Nunca falla — si hay error retorna string vacío y el pipeline continúa.
    """
    key    = _cache_key(topic)
    cached = _get_cache(key)
    if cached:
        return cached

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return ""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model  = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        log.info(f"[research] Buscando: {topic}")
        t0 = time.time()

        response = client.models.generate_content(
            model=model,
            contents=_PROMPT.format(topic=topic),
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=1024,
            ),
        )

        text = (response.text or "").strip()
        log.info(f"[research] Listo en {time.time()-t0:.1f}s — {len(text)} chars")

        if text:
            _set_cache(key, text)
        return text

    except Exception as e:
        log.warning(f"[research] Error (pipeline continua sin contexto): {e!r}")
        return ""
