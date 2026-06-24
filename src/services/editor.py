import re
import subprocess
import unicodedata
from functools import lru_cache
from pathlib import Path

from src.utils.config import OUTPUT_DIR
from src.utils.logger import get_logger

log = get_logger(__name__)

TARGET_W, TARGET_H = 1080, 1920  # 9:16 vertical


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w]", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _ffmpeg(cmd: list) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        # Extract the actual error lines, skip the build config
        lines = [l for l in result.stderr.splitlines() if l and not l.startswith(" ") and "built with" not in l and "configuration" not in l and "lib" not in l]
        raise RuntimeError("\n".join(lines[-8:]))


def get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


@lru_cache(maxsize=8)
def _find_font() -> str:
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for f in candidates:
        if Path(f).exists():
            return f.replace("\\", "/").replace(":", "\\:")
    return ""


def cut_and_format(video_path: Path, start: float, end: float, output_path: Path) -> Path:
    # Blur background: original video blurred fills 9:16, foreground centered on top.
    # Eliminates black bars and crops out edge watermarks.
    vf = (
        f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},boxblur=20:3[bg];"
        f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )
    _ffmpeg([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(end - start),
        "-filter_complex", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-profile:v", "high", "-level", "4.0",
        "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output_path),
    ])
    return output_path


def add_captions(clip_path: Path, text: str, output_path: Path) -> Path:
    font_path = _find_font()

    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 > 40:
            lines.append(current.strip())
            current = word
        else:
            current += " " + word
    if current:
        lines.append(current.strip())
    lines = lines[:3]

    drawtext_filters = []
    y_pos = TARGET_H - 160
    font_opt = f"fontfile='{font_path}':" if font_path else ""
    for line in lines:
        safe = line.replace("'", "").replace(":", "").replace("\\", "")
        drawtext_filters.append(
            f"drawtext={font_opt}text='{safe}':fontsize=36:fontcolor=white"
            f":borderw=2:bordercolor=black:x=(w-text_w)/2:y={y_pos}"
        )
        y_pos += 45

    vf = ",".join(drawtext_filters) if drawtext_filters else "null"
    _ffmpeg([
        "ffmpeg", "-y", "-i", str(clip_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "copy",  # audio pass-through, no re-encode
        str(output_path),
    ])
    return output_path


def process_segment(video_path: Path, segment: dict, index: int, video_duration: float = 0.0) -> Path:
    stem = video_path.stem
    start, end = float(segment["start"]), float(segment["end"])

    if video_duration > 0:
        if start >= video_duration:
            raise ValueError(f"start={start:.1f}s fuera de la duración del video ({video_duration:.1f}s)")
        end = min(end, video_duration - 0.1)

    title_slug = _slugify(segment.get("title", f"clip_{index}"))[:30]
    base = OUTPUT_DIR / f"{stem}_{index:02d}_{title_slug}"

    vertical = base.parent / f"{base.name}_vertical.mp4"
    final = Path(f"{base}_final.mp4")

    log.info(f"Procesando clip {index+1}: {segment.get('title')} ({start:.1f}s - {end:.1f}s)")

    cut_and_format(video_path, start, end, vertical)
    add_captions(vertical, segment.get("hook", ""), final)

    vertical.unlink(missing_ok=True)

    log.info(f"Clip listo: {final.name}")
    return final
