import json
from src.utils.config import (
    ANTHROPIC_API_KEY, OPENROUTER_API_KEY, GOOGLE_API_KEY, GEMINI_MODEL,
    MAX_CLIPS, CLIP_MAX_SECONDS, TMP_DIR,
)
from src.utils.logger import get_logger

log = get_logger(__name__)

_PROMPT = """Analiza esta transcripción de video y devuelve los {max_clips} momentos con mayor potencial viral para redes sociales cortas (TikTok, Reels, Shorts).

Título del video: {title}

Transcripción (formato: [start_seg - end_seg] texto):
{transcript_text}

Responde SOLO con un array JSON válido, sin markdown ni explicaciones:
[
  {{
    "start": <segundos float>,
    "end": <segundos float>,
    "title": "<título corto del clip>",
    "hook": "<caption gancho para redes sociales, máx 150 chars>",
    "score": <entero 0-100 que representa el potencial viral>,
    "virality_reason": "<una frase corta explicando por qué este momento es viral>",
    "platforms": ["tiktok", "instagram", "youtube"]
  }}
]

Reglas:
- Cada clip debe durar entre 15 y {max_seconds} segundos
- Prioriza momentos con revelaciones, humor, consejos accionables o emociones fuertes
- El hook debe incluir emojis relevantes y llamada a la acción
- score 90-100: momento excepcional (revelación, emoción intensa, twist)
- score 70-89: muy buen momento (consejo accionable, humor claro, opinión fuerte)
- score 50-69: momento sólido (interesante pero predecible)
- Ordena el array de mayor a menor score"""


def _build_transcript_text(segments: list[dict]) -> str:
    return "\n".join(
        f"[{s['start']:.1f}s - {s['end']:.1f}s] {s['text']}"
        for s in segments
    )


def _call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=GOOGLE_API_KEY)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text


def _call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _call_openrouter(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
    resp = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048,
    )
    return resp.choices[0].message.content


def _pick_provider() -> str:
    if GOOGLE_API_KEY:
        return "gemini"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OPENROUTER_API_KEY:
        return "openrouter"
    raise RuntimeError(
        "No hay API key configurada. Agrega GOOGLE_API_KEY en .env\n"
        "Obtén una gratis en: https://aistudio.google.com"
    )


def analyze(transcript: list[dict], video_title: str = "") -> list[dict]:
    if not transcript:
        raise ValueError("Transcripción vacía")

    import hashlib
    transcript_hash = hashlib.md5(
        (video_title + "".join(s["text"] for s in transcript[:10])).encode()
    ).hexdigest()[:12]
    cache_key = transcript_hash
    cache_path = TMP_DIR / f"analysis_{cache_key}.json"
    if cache_path.exists():
        log.info(f"Análisis en cache: {cache_path.name}")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    provider = _pick_provider()
    transcript_text = _build_transcript_text(transcript)
    prompt = _PROMPT.format(
        max_clips=MAX_CLIPS,
        title=video_title,
        transcript_text=transcript_text,
        max_seconds=CLIP_MAX_SECONDS,
    )

    log.info(f"Analizando con {provider} ({GEMINI_MODEL if provider == 'gemini' else ''}) — {len(transcript)} segmentos...")

    if provider == "gemini":
        raw = _call_gemini(prompt)
    elif provider == "anthropic":
        raw = _call_anthropic(prompt)
    else:
        raw = _call_openrouter(prompt)

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    # Trim trailing content after the JSON array (Gemini sometimes appends text)
    bracket = raw.rfind("]")
    if bracket != -1:
        raw = raw[: bracket + 1]

    try:
        segments = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"El modelo devolvió JSON inválido: {e}\nRespuesta: {raw[:300]}")

    if not isinstance(segments, list) or not segments:
        raise RuntimeError("El modelo no devolvió ningún momento viral")

    cache_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Identificados {len(segments)} momentos virales")
    return segments
