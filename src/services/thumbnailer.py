"""
AI thumbnail generator for vertical clips.
1. Extract N frames with ffmpeg
2. Ask Gemini Vision to pick the most visually compelling frame
3. Compose 1080x1920 thumbnail: frame + gradient + title text overlay
"""
import subprocess
import tempfile
from pathlib import Path
from src.utils.config import GOOGLE_API_KEY, OUTPUT_DIR
from src.utils.logger import get_logger

log = get_logger(__name__)

THUMB_W, THUMB_H = 1080, 1920


def _extract_frames(clip_path: Path, n: int = 8) -> list[Path]:
    tmp = Path(tempfile.gettempdir()) / f"thumb_frames_{clip_path.stem}"
    tmp.mkdir(exist_ok=True)
    out_pattern = str(tmp / "frame_%02d.jpg")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(clip_path),
         "-vf", f"fps=1/1,scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=increase,crop={THUMB_W}:{THUMB_H}",
         "-frames:v", str(n), "-q:v", "3", out_pattern],
        capture_output=True,
    )
    if result.returncode != 0:
        return []
    return sorted(tmp.glob("frame_*.jpg"))


def _pick_best_frame(frames: list[Path], title: str, hook: str) -> Path:
    """Ask Gemini Vision which frame is most compelling for a YouTube thumbnail."""
    if not GOOGLE_API_KEY or len(frames) <= 1:
        return frames[len(frames) // 2] if frames else frames[0]
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GOOGLE_API_KEY)
        parts = [
            types.Part.from_text(
                f"Eres un experto en thumbnails de YouTube. "
                f"El clip se titula: \"{title}\". Hook: \"{hook}\". "
                f"De estas {len(frames)} imágenes (en orden), elige el número (1-{len(frames)}) "
                f"del frame más impactante visualmente para usar como thumbnail. "
                f"Responde SOLO con el número, sin explicación."
            )
        ]
        for f in frames:
            parts.append(types.Part.from_bytes(data=f.read_bytes(), mime_type="image/jpeg"))

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=parts,
        )
        idx = int(response.text.strip()) - 1
        idx = max(0, min(len(frames) - 1, idx))
        log.info(f"Gemini eligió frame {idx + 1}/{len(frames)}")
        return frames[idx]
    except Exception as e:
        log.warning(f"Gemini Vision falló, usando frame central: {e}")
        return frames[len(frames) // 2]


def _compose_thumbnail(
    frame_path: Path | None,
    title: str,
    score: int | None,
    output_path: Path,
) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import textwrap

    if frame_path and frame_path.exists():
        img = Image.open(frame_path).convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)
    else:
        img = Image.new("RGB", (THUMB_W, THUMB_H), (20, 20, 20))

    # Dark gradient overlay on bottom 55%
    overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    gradient_start = int(THUMB_H * 0.45)
    for y in range(gradient_start, THUMB_H):
        alpha = int(220 * (y - gradient_start) / (THUMB_H - gradient_start))
        draw_ov.line([(0, y), (THUMB_W, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Font — try Liberation Sans Bold (Railway), fallback to default
    font_candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
    ]
    title_font = None
    for fc in font_candidates:
        if Path(fc).exists():
            try:
                title_font = ImageFont.truetype(fc, size=82)
                score_font = ImageFont.truetype(fc, size=64)
                break
            except Exception:
                continue

    # Wrap title to ~18 chars per line
    lines = textwrap.wrap(title.upper(), width=18)
    text_y = int(THUMB_H * 0.6)

    for line in lines:
        kwargs = {"font": title_font} if title_font else {}
        # Shadow
        draw.text((54, text_y + 4), line, fill=(0, 0, 0, 180), **kwargs)
        draw.text((50, text_y), line, fill=(255, 255, 255), **kwargs)
        line_h = draw.textbbox((0, 0), line, **kwargs)[3] if title_font else 90
        text_y += line_h + 18

    # Score badge top-right
    if score is not None:
        badge_color = (34, 197, 94) if score >= 90 else (234, 179, 8) if score >= 70 else (113, 113, 122)
        badge_text = f"{score}"
        bx, by = THUMB_W - 180, 60
        draw.rounded_rectangle([bx, by, bx + 120, by + 90], radius=20, fill=badge_color)
        skw = {"font": score_font} if title_font else {}
        draw.text((bx + 60, by + 45), badge_text, fill=(255, 255, 255), anchor="mm", **skw)

    img.save(str(output_path), "JPEG", quality=92)


def generate_thumbnail(
    clip_path: Path,
    title: str,
    hook: str = "",
    score: int | None = None,
) -> Path:
    thumb_path = clip_path.with_name(clip_path.stem + "_thumb.jpg")
    if thumb_path.exists():
        return thumb_path
    try:
        frames = _extract_frames(clip_path, n=8)
        best = _pick_best_frame(frames, title, hook) if frames else None
        _compose_thumbnail(best, title, score, thumb_path)
        log.info(f"Thumbnail generado: {thumb_path.name}")
        return thumb_path
    except Exception as e:
        log.error(f"Error generando thumbnail: {e}")
        raise
