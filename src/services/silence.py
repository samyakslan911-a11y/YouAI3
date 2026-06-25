"""
Silence removal using ffmpeg silencedetect.
Detects silent gaps > threshold and cuts them out, then concatenates the result.
Improves pacing on clips with pauses, ums, and dead air.
"""
import logging, subprocess, tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# Silence is anything below -35dB for more than 0.4 seconds
SILENCE_DB   = -35
SILENCE_DUR  = 0.4   # seconds — shorter = more aggressive cuts
PAD_START    = 0.05  # seconds to keep before speech resumes
PAD_END      = 0.12  # seconds to keep after speech ends (natural breath)


def detect_silence(video_path: Path) -> list[tuple[float, float]]:
    """Return list of (start, end) silent intervals in seconds."""
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-af", f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_DUR}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr

    silences: list[tuple[float, float]] = []
    start = None
    for line in output.splitlines():
        if "silence_start" in line:
            try:
                start = float(line.split("silence_start:")[1].split()[0])
            except (IndexError, ValueError):
                pass
        elif "silence_end" in line and start is not None:
            try:
                end = float(line.split("silence_end:")[1].split()[0])
                silences.append((start, end))
                start = None
            except (IndexError, ValueError):
                pass
    return silences


def _speech_intervals(duration: float, silences: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Invert silence intervals to get speech intervals."""
    intervals: list[tuple[float, float]] = []
    prev = 0.0
    for s_start, s_end in silences:
        seg_start = prev
        seg_end = s_start + PAD_END
        if seg_end - seg_start > 0.1:
            intervals.append((seg_start, seg_end))
        prev = max(s_end - PAD_START, prev)
    if duration - prev > 0.1:
        intervals.append((prev, duration))
    return intervals


def remove_silence(input_path: Path, output_path: Path) -> Path:
    """
    Remove silent gaps from a video clip.
    Returns output_path. Falls back to input_path if removal fails or saves < 5%.
    """
    try:
        # Get duration
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(input_path)],
            capture_output=True, text=True,
        )
        duration = float(probe.stdout.strip())

        silences = detect_silence(input_path)
        if not silences:
            log.info("No silence detected — skipping removal")
            return input_path

        intervals = _speech_intervals(duration, silences)
        if not intervals:
            log.info("No speech intervals — skipping removal")
            return input_path

        total_speech = sum(e - s for s, e in intervals)
        savings = 1 - total_speech / duration
        log.info(f"Silence removal: {len(silences)} gaps → saves {savings*100:.1f}%")

        if savings < 0.05:
            log.info("Savings < 5%, not worth cutting")
            return input_path

        # Build concat filter
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            segment_files: list[Path] = []

            for i, (seg_s, seg_e) in enumerate(intervals):
                seg_out = tmp_path / f"seg_{i:03d}.mp4"
                subprocess.run([
                    "ffmpeg", "-y",
                    "-ss", str(seg_s), "-to", str(seg_e),
                    "-i", str(input_path),
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-b:a", "192k",
                    "-avoid_negative_ts", "make_zero",
                    str(seg_out),
                ], capture_output=True, check=True)
                segment_files.append(seg_out)

            # Write concat list
            concat_list = tmp_path / "concat.txt"
            concat_list.write_text(
                "\n".join(f"file '{f}'" for f in segment_files),
                encoding="utf-8",
            )

            result = subprocess.run([
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ], capture_output=True, text=True)

            if result.returncode != 0:
                log.error(f"Concat failed: {result.stderr[-500:]}")
                return input_path

        log.info(f"Silence removed: {input_path.name} → {output_path.name} (saved {savings*100:.1f}%)")
        return output_path

    except Exception as e:
        log.warning(f"Silence removal failed ({e}), using original")
        return input_path
