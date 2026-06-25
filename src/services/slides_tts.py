"""
Text-to-Speech narration for slide videos using gTTS (Google Translate TTS).
No API key required. Generates one MP3 per slide then concatenates to match
the video timeline.

Each slide budget:
  - SLIDE_DURATION seconds of speech (trimmed/padded with silence)
  - FADE_DURATION seconds of silence at the end (transition gap)
"""
import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

SLIDE_DURATION = 4.5   # must match slides_video.SLIDE_DURATION
FADE_DURATION  = 0.4   # must match slides_video.FADE_DURATION
LANG           = "es"  # narration language


def _slide_script(slide: dict) -> str:
    """Build narration text — headline + body up to ~11 words total (~4.5s at 2.5w/s)."""
    headline = slide.get("headline", "").strip()
    body     = slide.get("body", "").strip()
    if not body:
        return f"{headline}."
    # Fit headline + body in ~11 words; take first sentence of body
    first_sentence = body.split(".")[0].split("\n")[0].strip()
    combined = f"{headline}. {first_sentence}."
    words = combined.split()
    if len(words) <= 14:
        return combined
    # Truncate body to keep total under 14 words
    body_words = first_sentence.split()
    headline_words = len(headline.split())
    allowed_body = max(2, 14 - headline_words - 1)
    short_body = " ".join(body_words[:allowed_body])
    return f"{headline}. {short_body}."


def generate_narration(slides: list[dict], output_path: Path) -> Path | None:
    """
    Generate one MP3 audio file with timed narration for all slides.
    Returns output_path on success, None if gTTS is not installed.
    """
    try:
        from gtts import gTTS
    except ImportError:
        log.warning("gTTS no instalado — narración omitida (pip install gtts)")
        return None

    total_dur = len(slides) * (SLIDE_DURATION + FADE_DURATION)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        segment_files: list[Path] = []

        for slide in sorted(slides, key=lambda s: s.get("index", 0)):
            idx   = slide.get("index", 0)
            text  = _slide_script(slide)
            raw   = tmp_path / f"raw_{idx:02d}.mp3"
            padded = tmp_path / f"seg_{idx:02d}.mp3"

            # Generate TTS
            try:
                gTTS(text=text, lang=LANG).save(str(raw))
            except Exception as e:
                log.warning(f"  TTS slide {idx} falló: {e}")
                # Write silence for this slide
                _silence_mp3(padded, SLIDE_DURATION + FADE_DURATION)
                segment_files.append(padded)
                continue

            # Trim or pad to exactly SLIDE_DURATION + FADE_DURATION seconds
            target = SLIDE_DURATION + FADE_DURATION
            _trim_pad(raw, padded, target)
            segment_files.append(padded)

        if not segment_files:
            return None

        # Concatenate all segments
        concat_list = tmp_path / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{f}'" for f in segment_files),
            encoding="utf-8",
        )
        result = subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:a", "libmp3lame", "-q:a", "4",
            str(output_path),
        ], capture_output=True, text=True)

        if result.returncode != 0:
            log.error(f"Concat TTS falló: {result.stderr[-400:]}")
            return None

    log.info(f"Narración generada: {output_path.name} ({total_dur:.1f}s)")
    return output_path


def _trim_pad(src: Path, dst: Path, target_sec: float) -> None:
    """Trim audio to target_sec, then pad with silence if shorter."""
    # First trim
    trimmed = src.with_name(src.stem + "_trim.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-t", str(target_sec),
        "-c:a", "libmp3lame", "-q:a", "4",
        str(trimmed),
    ], capture_output=True)

    # Then pad if needed
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(trimmed),
        "-af", f"apad=pad_dur={target_sec}",
        "-t", str(target_sec),
        "-c:a", "libmp3lame", "-q:a", "4",
        str(dst),
    ], capture_output=True)


def _silence_mp3(dst: Path, duration: float) -> None:
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=22050:cl=mono",
        "-t", str(duration),
        "-c:a", "libmp3lame", "-q:a", "4",
        str(dst),
    ], capture_output=True)
