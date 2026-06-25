import re
import subprocess
import tempfile
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from src.utils import ffmpeg as _ffmpeg_util
from src.utils.config import OUTPUT_DIR
from src.utils.logger import get_logger

log = get_logger(__name__)

TARGET_W, TARGET_H = 1080, 1920  # 9:16 vertical
CaptionStyle = Literal["capcut", "karaoke", "subtitles", "none"]


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w]", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _ffmpeg(cmd: list) -> None:
    _ffmpeg_util.run(cmd)


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


@lru_cache(maxsize=1)
def _find_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",  # Railway (fonts-liberation)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for f in candidates:
        if Path(f).exists():
            return f
    return ""


# ── Face tracking ─────────────────────────────────────────────────────────────

def _detect_face_track(video_path: Path, start: float, end: float) -> tuple[int, int, int, int] | None:
    """
    Sample frames from [start, end], detect faces with OpenCV DNN.
    Returns (crop_w, crop_h, crop_x, crop_y) for ffmpeg crop filter — a 9:16
    strip centered on the smoothed face position in the original video.
    Returns None when face detection fails or is insufficient (use center crop).
    """
    try:
        import cv2
        import urllib.request
    except ImportError:
        log.warning("opencv no disponible, usando crop centrado")
        return None

    model_dir = Path(tempfile.gettempdir()) / "cv_face"
    model_dir.mkdir(exist_ok=True)
    proto = model_dir / "deploy.prototxt"
    caffemodel = model_dir / "res10_300x300_ssd_iter_140000.caffemodel"

    # Pinned to specific commits — "master" refs can break if files move
    proto_url = "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/dnn/face_detector/deploy.prototxt"
    model_url = "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"

    try:
        if not proto.exists():
            urllib.request.urlretrieve(proto_url, proto)
        if not caffemodel.exists():
            urllib.request.urlretrieve(model_url, caffemodel)
        net = cv2.dnn.readNetFromCaffe(str(proto), str(caffemodel))
    except Exception as e:
        log.warning(f"No se pudo cargar modelo de face detection: {e}")
        return None

    cap = cv2.VideoCapture(str(video_path))
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    duration = end - start
    n_samples = min(20, max(5, int(duration * 2)))
    sample_times = [start + duration * i / (n_samples - 1) for i in range(n_samples)]

    face_centers_x: list[float] = []
    for t in sample_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret:
            continue
        fh, fw = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0,
                                     (300, 300), (104.0, 177.0, 123.0))
        net.setInput(blob)
        detections = net.forward()
        best_conf, best_cx = 0.0, None
        for i in range(detections.shape[2]):
            conf = float(detections[0, 0, i, 2])
            if conf > 0.5 and conf > best_conf:
                x1 = int(detections[0, 0, i, 3] * fw)
                x2 = int(detections[0, 0, i, 5] * fw)
                best_cx = (x1 + x2) / 2.0
                best_conf = conf
        if best_cx is not None:
            face_centers_x.append(best_cx)

    cap.release()

    if len(face_centers_x) < n_samples * 0.3:
        return None  # not enough faces — caller uses center crop

    # EMA smooth (α=0.15) — reduces jitter
    alpha = 0.15
    smoothed_cx = face_centers_x[0]
    for cx in face_centers_x[1:]:
        smoothed_cx = alpha * cx + (1 - alpha) * smoothed_cx

    # Compute 9:16 crop geometry in Python to avoid comma issues in ffmpeg expressions
    crop_w = int(orig_h * 9 / 16)
    crop_h = orig_h
    crop_x = int(smoothed_cx - crop_w / 2)
    crop_x = max(0, min(orig_w - crop_w, crop_x))  # clamp within frame
    return (crop_w, crop_h, crop_x, 0)


# ── Captions ──────────────────────────────────────────────────────────────────

def _interpolate_word_timing(
    segments: list[dict], clip_start: float, clip_end: float
) -> list[dict]:
    """
    Distribute words proportionally within each segment's time range,
    normalized to clip-relative time (clip_start → 0).
    Returns list of {word, start, end} in seconds relative to clip start.
    """
    events: list[dict] = []
    for seg in segments:
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", 0))
        if seg_end <= clip_start or seg_start >= clip_end:
            continue
        effective_start = max(seg_start, clip_start)
        effective_end = min(seg_end, clip_end)
        dur = effective_end - effective_start
        if dur <= 0:
            continue
        words = [w for w in seg.get("text", "").strip().split() if w]
        if not words:
            continue
        word_dur = dur / len(words)
        for i, word in enumerate(words):
            ws = effective_start + i * word_dur - clip_start
            events.append({"word": word, "start": max(0.0, ws), "end": ws + word_dur})
    return events


def _chunk_words(events: list[dict], n: int = 4) -> list[list[dict]]:
    return [events[i:i + n] for i in range(0, len(events), n)]


def _seconds_to_srt_ts(s: float) -> str:
    s = max(0.0, s)
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def _build_srt(word_events: list[dict], style: CaptionStyle) -> Path | None:
    if style == "none" or not word_events:
        return None

    srt_file = Path(tempfile.gettempdir()) / f"captions_{id(word_events)}.srt"
    entries: list[str] = []

    if style == "capcut":
        for i, ev in enumerate(word_events, 1):
            entries.append(
                f"{i}\n"
                f"{_seconds_to_srt_ts(ev['start'])} --> {_seconds_to_srt_ts(ev['end'])}\n"
                f"{ev['word'].upper()}\n"
            )
    else:  # subtitles: chunks of 4 words
        chunks = _chunk_words(word_events)
        for i, chunk in enumerate(chunks, 1):
            text = " ".join(ev["word"] for ev in chunk)
            entries.append(
                f"{i}\n"
                f"{_seconds_to_srt_ts(chunk[0]['start'])} --> {_seconds_to_srt_ts(chunk[-1]['end'])}\n"
                f"{text}\n"
            )

    srt_file.write_text("\n".join(entries), encoding="utf-8")
    return srt_file


def _ass_header(style: CaptionStyle) -> str:
    if style == "capcut":
        return (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            f"PlayResX: {TARGET_W}\n"
            f"PlayResY: {TARGET_H}\n"
            "WrapStyle: 0\n\n"
            "[V4+ Styles]\n"
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
            "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
            "Alignment,MarginL,MarginR,MarginV,Encoding\n"
            "Style: Default,Liberation Sans,88,"
            "&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,"
            "-1,0,0,0,100,100,0,0,1,4,1,5,60,60,200,1\n\n"
            "[Events]\n"
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        )
    # karaoke
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {TARGET_W}\n"
        f"PlayResY: {TARGET_H}\n"
        "WrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
        "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Default,Liberation Sans,72,"
        "&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,"
        "-1,0,0,0,100,100,0,0,1,3,0,2,60,60,80,1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )


def _ts_ass(s: float) -> str:
    s = max(0.0, s)
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    cs = int((s - int(s)) * 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def _build_ass(word_events: list[dict], style: CaptionStyle) -> Path:
    ass_file = Path(tempfile.gettempdir()) / f"captions_{id(word_events)}.ass"
    lines = [_ass_header(style)]

    if style == "capcut":
        for ev in word_events:
            tag = r"{\an5\fscx118\fscy118\fad(80,60)}"
            text = tag + ev["word"].upper()
            lines.append(
                f"Dialogue: 0,{_ts_ass(ev['start'])},{_ts_ass(ev['end'])},"
                f"Default,,0,0,0,,{text}"
            )
    else:  # karaoke — groups of 4
        chunks = _chunk_words(word_events)
        for chunk in chunks:
            start = chunk[0]["start"]
            end = chunk[-1]["end"]
            text = "".join(
                "{\\kf%d}%s " % (max(1, round((ev["end"] - ev["start"]) * 100)), ev["word"].upper())
                for ev in chunk
            ).rstrip()
            lines.append(
                f"Dialogue: 0,{_ts_ass(start)},{_ts_ass(end)},"
                f"Default,,0,0,0,,{text}"
            )

    ass_file.write_text("\n".join(lines), encoding="utf-8")
    return ass_file


def _caption_force_style(style: CaptionStyle, font_path: str) -> str:
    # Use friendly font name for libass; fallback to Arial
    font_map = {
        "LiberationSans-Bold": "Liberation Sans",
        "DejaVuSans-Bold": "DejaVu Sans",
        "arialbd": "Arial",
        "arial": "Arial",
    }
    stem = Path(font_path).stem if font_path else ""
    font_name = font_map.get(stem, "Arial")
    if style == "capcut":
        return (
            f"FontName={font_name},FontSize=22,Bold=1,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "Outline=4,Shadow=1,MarginV=200,Alignment=2"
        )
    return (
        f"FontName={font_name},FontSize=14,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "Outline=3,Shadow=0,MarginV=80,Alignment=2"
    )


# ── Main functions ────────────────────────────────────────────────────────────

def cut_and_format(
    video_path: Path,
    start: float,
    end: float,
    output_path: Path,
    face_crop: tuple[int, int, int, int] | None = None,
    srt_path: Path | None = None,
    caption_style: CaptionStyle = "none",
) -> Path:
    # fg filter: face-tracked crop + scale if face detected, else letterbox scale
    if face_crop is not None:
        cw, ch, cx, cy = face_crop
        fg_filter = f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale={TARGET_W}:{TARGET_H}[fg]"
    else:
        fg_filter = f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease[fg]"

    filter_complex = (
        f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
        f"crop={TARGET_W}:{TARGET_H},boxblur=20:3[bg];"
        f"{fg_filter};"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
    )

    map_arg = "[out]"

    if srt_path and srt_path.exists():
        srt_str = str(srt_path).replace("\\", "/")
        if srt_path.suffix == ".ass":
            filter_complex += f";[out]ass={srt_str}[final]"
        else:
            font_path = _find_font()
            force_style = _caption_force_style(caption_style, font_path)
            filter_complex += f";[out]subtitles={srt_str}:force_style='{force_style}'[final]"
        map_arg = "[final]"

    _ffmpeg([
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(video_path),
        "-t", str(end - start),
        "-filter_complex", filter_complex,
        "-map", map_arg,
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "fast",
        "-profile:v", "high", "-level", "4.0",
        "-b:v", "8M", "-maxrate", "10M", "-bufsize", "16M",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(output_path),
    ])
    return output_path


def process_segment(
    video_path: Path,
    segment: dict,
    index: int,
    video_duration: float = 0.0,
    all_segments: list[dict] | None = None,
    caption_style: CaptionStyle = "capcut",
    face_track: bool = True,
) -> Path:
    stem = video_path.stem
    start, end = float(segment["start"]), float(segment["end"])

    if video_duration > 0:
        if start >= video_duration:
            raise ValueError(f"start={start:.1f}s fuera de la duración del video ({video_duration:.1f}s)")
        end = min(end, video_duration - 0.1)

    title_slug = _slugify(segment.get("title", f"clip_{index}"))[:30]
    final = OUTPUT_DIR / f"{stem}_{index:02d}_{title_slug}_final.mp4"

    log.info(f"Procesando clip {index+1}: {segment.get('title')} ({start:.1f}s - {end:.1f}s)")

    face_crop = None
    if face_track:
        log.info(f"  Detectando cara en clip {index+1}...")
        face_crop = _detect_face_track(video_path, start, end)
        log.info(f"  Face crop: {face_crop}" if face_crop else "  Sin cara — crop centrado")

    srt_path: Path | None = None
    if caption_style != "none" and all_segments:
        word_events = _interpolate_word_timing(all_segments, start, end)
        if caption_style in ("capcut", "karaoke"):
            srt_path = _build_ass(word_events, caption_style)
        else:
            srt_path = _build_srt(word_events, caption_style)
        if srt_path:
            log.info(f"  Captions ({caption_style}): {len(word_events)} palabras")

    try:
        cut_and_format(
            video_path, start, end, final,
            face_crop=face_crop,
            srt_path=srt_path,
            caption_style=caption_style,
        )
    finally:
        if srt_path and srt_path.exists():
            srt_path.unlink(missing_ok=True)

    log.info(f"Clip listo: {final.name}")
    return final
