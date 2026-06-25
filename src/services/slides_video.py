"""
Assemble slide images into a 1080x1920 video with Ken Burns effect.
Each slide: 3.5s display + 0.4s crossfade. Blurred bars fill the
1080x1350 → 1080x1920 letterbox.
"""
import logging, subprocess, tempfile
from pathlib import Path

log = logging.getLogger(__name__)

SLIDE_W, SLIDE_H = 1080, 1350
VIDEO_W, VIDEO_H = 1080, 1920
SLIDE_DURATION  = 3.5   # seconds per slide
FADE_DURATION   = 0.4   # crossfade between slides
ZOOM_FACTOR     = 1.08  # Ken Burns end scale


def _ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg error:\n{result.stderr[-2000:]}")


def assemble_video(image_paths: list[Path], output_path: Path) -> Path:
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

    for i in range(n):
        # Alternate zoom direction per slide for visual variety
        zoom_expr = f"zoom='if(lte(on,1),1,min(zoom+{(ZOOM_FACTOR-1)/zoom_frames:.6f},{ZOOM_FACTOR}))'"
        if i % 2 == 0:
            x_expr = "x='iw/2-(iw/zoom/2)'"
            y_expr = "y='ih/2-(ih/zoom/2)'"
        else:
            x_expr = "x='iw/2-(iw/zoom/2)+((iw-(iw/zoom))*on/(2*td*fps))'"
            y_expr = "y='ih/2-(ih/zoom/2)'"

        # Ken Burns zoom
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

    cmd = (
        ["ffmpeg", "-y"]
        + inputs
        + [
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            str(output_path),
        ]
    )

    log.info(f"Ensamblando video: {n} slides → {output_path.name}")
    _ffmpeg(cmd)
    log.info(f"Video listo: {output_path.name} ({output_path.stat().st_size // 1024}KB)")
    return output_path
