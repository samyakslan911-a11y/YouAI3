import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from src.utils.config import TMP_DIR
from src.utils.logger import get_logger

log = get_logger(__name__)

_YT_OPTS = {
    "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "merge_output_format": "mp4",
    "quiet": True,
    "no_warnings": True,
}

_cookies_file: str | None = None

def _get_cookies_file() -> str | None:
    global _cookies_file
    if _cookies_file and Path(_cookies_file).exists():
        return _cookies_file
    cookies_content = os.getenv("YOUTUBE_COOKIES", "").strip()
    if not cookies_content:
        return None
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    tmp.write(cookies_content)
    tmp.close()
    _cookies_file = tmp.name
    return _cookies_file


def _is_url(source: str) -> bool:
    scheme = urlparse(source).scheme
    return scheme in ("http", "https")


def download(source: str) -> Path:
    if _is_url(source):
        return _download_url(source)
    return _use_local(source)


def _download_url(url: str) -> Path:
    base_opts: dict = {"quiet": True}
    cookies = _get_cookies_file()
    if cookies:
        base_opts["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(base_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    video_id = info.get("id", "video")
    out_path = TMP_DIR / f"{video_id}.mp4"

    if out_path.exists():
        log.info(f"Video en cache: {out_path}")
        return out_path

    opts = {**_YT_OPTS, "outtmpl": str(TMP_DIR / f"{video_id}.%(ext)s")}
    if cookies:
        opts["cookiefile"] = cookies
    log.info(f"Descargando: {info.get('title', url)}")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    return out_path


def _use_local(path: str) -> Path:
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")
    dst = TMP_DIR / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    log.info(f"Usando archivo local: {dst}")
    return dst
