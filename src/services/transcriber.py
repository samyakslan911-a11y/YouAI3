import json
import re
import subprocess
from pathlib import Path

from src.utils.config import TMP_DIR, GOOGLE_API_KEY, GEMINI_MODEL, WHISPER_MODEL
from src.utils.logger import get_logger

log = get_logger(__name__)


def _extract_audio(video_path: Path) -> Path:
    audio_path = TMP_DIR / f"{video_path.stem}.mp3"
    if audio_path.exists():
        return audio_path
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extract error: {result.stderr}")
    return audio_path


def _transcribe_gemini(video_path: Path) -> list[dict]:
    import base64
    from google import genai

    audio_path = _extract_audio(video_path)
    client = genai.Client(api_key=GOOGLE_API_KEY)

    log.info("Enviando audio a Gemini (inline)...")
    audio_b64 = base64.b64encode(audio_path.read_bytes()).decode()

    prompt = (
        "Transcribe este audio completamente. "
        "Devuelve SOLO un array JSON válido sin markdown:\n"
        '[{"text": "...", "start": 0.0, "end": 5.2}, ...]'
        "\nCada segmento debe tener texto, start y end en segundos."
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            {"inline_data": {"mime_type": "audio/mpeg", "data": audio_b64}},
            prompt,
        ],
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    return json.loads(raw.strip())


def _transcribe_whisper(video_path: Path) -> list[dict]:
    import whisper

    _model_cache = {}

    def _load(name: str):
        if name not in _model_cache:
            log.info(f"Cargando modelo Whisper '{name}'...")
            _model_cache[name] = whisper.load_model(name)
        return _model_cache[name]

    model = _load(WHISPER_MODEL)
    result = model.transcribe(str(video_path), verbose=False)
    return [
        {"text": s["text"].strip(), "start": s["start"], "end": s["end"]}
        for s in result["segments"]
    ]


def transcribe(video_path: Path) -> list[dict]:
    cache_path = TMP_DIR / f"{video_path.stem}_transcript.json"

    if cache_path.exists():
        log.info(f"Transcripción en cache: {cache_path}")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    log.info(f"Transcribiendo: {video_path.name}")

    if GOOGLE_API_KEY:
        segments = _transcribe_gemini(video_path)
        log.info("Transcripción con Gemini")
    else:
        segments = _transcribe_whisper(video_path)
        log.info("Transcripción con Whisper")

    cache_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(f"Transcripción guardada: {len(segments)} segmentos")
    return segments
