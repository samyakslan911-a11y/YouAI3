"""
Assemble slide images into a 1080x1920 video with Ken Burns effect.
Each slide: 3.5s display + 0.4s crossfade. Blurred bars fill the
1080x1350 → 1080x1920 letterbox.
"""
import logging, tempfile
from pathlib import Path

from src.utils import ffmpeg as _ffmpeg_util

log = logging.getLogger(__name__)

SLIDE_W, SLIDE_H = 1080, 1350
VIDEO_W, VIDEO_H = 1080, 1920
SLIDE_DURATION  = 4.5   # seconds per slide (4.5s → 10 slides = 45s, ideal for Reels)
FADE_DURATION   = 0.4   # crossfade between slides
ZOOM_FACTOR     = 1.08  # Ken Burns end scale


def _ffmpeg(cmd: list[str]) -> None:
    _ffmpeg_util.run(cmd)


def assemble_video(image_paths: list[Path], output_path: Path, audio_path: Path | None = None) -> Path:
    """
    Build MP4 from ordered list of PNG slide images.
    Uses Ken Burns zoom per slide + crossfade transitions.
    """
    n = len(image_paths)
    if n == 0:
        raise ValueError("No images to assemble")

    # Bar height each side to fill 1920 from 1350
    bar_h = (VIDEO_H - SLIDE_H) // 2  # 285px top + bottom

    # Build filter_complex
    # Per slide: zoompan for Ken Burns + pad to 1920 with blurred bars
    inputs: list[str] = []
    for p in image_paths:
        inputs += ["-loop", "1", "-t", str(SLIDE_DURATION + FADE_DURATION), "-i", str(p)]

    filter_parts: list[str] = []
    zoom_frames = int((SLIDE_DURATION + FADE_DURATION) * 25)  # 25fps

    zoom_step = (ZOOM_FACTOR - 1.0) / zoom_frames

    for i in range(n):
        # Ken Burns: slow zoom in from center, alternate anchor corner
        zoom_expr = f"zoom='min(zoom+{zoom_step:.6f},{ZOOM_FACTOR})'"
        if i % 4 == 0:
            x_expr = "x='iw/2-(iw/zoom/2)'"
            y_expr = "y='ih/2-(ih/zoom/2)'"
        elif i % 4 == 1:
            x_expr = "x='0'"
            y_expr = "y='0'"
        elif i % 4 == 2:
            x_expr = "x='iw-(iw/zoom)'"
            y_expr = "y='0'"
        else:
            x_expr = "x='0'"
            y_expr = "y='ih-(ih/zoom)'"

        filter_parts.append(
            f"[{i}:v]zoompan={zoom_expr}:{x_expr}:{y_expr}"
            f":d={zoom_frames}:s={SLIDE_W}x{SLIDE_H}:fps=25[zoom{i}]"
        )

        # Blurred background bar: take same frame, scale to fill 1080x1920, blur
        filter_parts.append(
            f"[{i}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},"
            f"gblur=sigma=20[bg{i}]"
        )

        # Overlay slide on blurred background
        filter_parts.append(
            f"[bg{i}][zoom{i}]overlay=(W-w)/2:(H-h)/2[framed{i}]"
        )

    # Crossfade transitions between slides
    # First slide starts the chain
    if n == 1:
        filter_parts.append(f"[framed0]copy[final]")
    else:
        # xfade each pair
        offset = SLIDE_DURATION  # first transition at end of first slide
        filter_parts.append(
            f"[framed0][framed1]xfade=transition=fade:duration={FADE_DURATION}"
            f":offset={offset:.2f}[xf0]"
        )
        for i in range(2, n):
            offset += SLIDE_DURATION
            prev = f"xf{i-2}" if i > 2 else "xf0"
            filter_parts.append(
                f"[{prev}][framed{i}]xfade=transition=fade:duration={FADE_DURATION}"
                f":offset={offset:.2f}[xf{i-1}]"
            )
        last = f"xf{n-2}"
        filter_parts.append(f"[{last}]copy[final]")

    filter_complex = ";".join(filter_parts)

    if audio_path and audio_path.exists():
        # Audio is input index n (after n image inputs at 0..n-1)
        audio_inputs = ["-i", str(audio_path)]
        audio_flags  = ["-map", f"{n}:a", "-c:a", "aac", "-b:a", "128k",
                        "-af", "volume=-3dB"]
    else:
        audio_inputs = []
        audio_flags  = ["-an"]

    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + audio_inputs
        + [
            "-filter_complex", filter_complex,
            "-map", "[final]",
        ]
        + audio_flags
        + [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]
    )

    log.info(f"Ensamblando video: {n} slides → {output_path.name}"
             + (" + narración" if audio_path else ""))
    _ffmpeg(cmd)
    log.info(f"Video listo: {output_path.name} ({output_path.stat().st_size // 1024}KB)")
    return output_path
