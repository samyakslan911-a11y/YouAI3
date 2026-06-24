import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from src.utils.config import (
    INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD,
    TIKTOK_COOKIES_FILE, YOUTUBE_CREDENTIALS,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class PublisherResult:
    platform: str
    success: bool
    url: str = ""
    error: str = ""


# ─── TikTok (Playwright browser automation) ──────────────────────────────────

def publish_tiktok(clip_path: Path, title: str, tags: list[str]) -> PublisherResult:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return PublisherResult("tiktok", False, error="playwright no instalado")

    cookies_path = Path(TIKTOK_COOKIES_FILE)
    if not cookies_path.exists():
        return PublisherResult(
            "tiktok", False,
            error=f"Archivo de cookies no encontrado: {TIKTOK_COOKIES_FILE}. "
                  "Exporta las cookies de TikTok con la extensión 'EditThisCookie' en formato JSON."
        )

    caption = f"{title} " + " ".join(f"#{t}" for t in tags[:5])

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            ctx = browser.new_context()
            ctx.add_cookies(json.loads(cookies_path.read_text()))
            page = ctx.new_page()

            page.goto("https://www.tiktok.com/upload")
            page.wait_for_selector("input[type='file']", timeout=15000)
            page.set_input_files("input[type='file']", str(clip_path))
            page.wait_for_selector(".caption-input", timeout=30000)
            page.fill(".caption-input", caption)
            page.click("button[data-e2e='post_video_button']")
            page.wait_for_url("**/upload**", timeout=60000)
            time.sleep(3)
            browser.close()

        log.info("TikTok: publicado")
        return PublisherResult("tiktok", True, url="https://www.tiktok.com")
    except Exception as e:
        log.error(f"TikTok error: {e}")
        return PublisherResult("tiktok", False, error=str(e))


# ─── Instagram Reels ─────────────────────────────────────────────────────────

def publish_instagram(clip_path: Path, caption: str) -> PublisherResult:
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        return PublisherResult(
            "instagram", False,
            error="INSTAGRAM_USERNAME y INSTAGRAM_PASSWORD no configurados en .env"
        )
    try:
        from instagrapi import Client
        cl = Client()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        media = cl.clip_upload(clip_path, caption=caption)
        url = f"https://www.instagram.com/reel/{media.code}/"
        log.info(f"Instagram Reel publicado: {url}")
        return PublisherResult("instagram", True, url=url)
    except Exception as e:
        log.error(f"Instagram error: {e}")
        return PublisherResult("instagram", False, error=str(e))


# ─── YouTube Shorts ───────────────────────────────────────────────────────────

def _load_youtube_creds():
    """
    Load OAuth2 credentials from env var JSON (Railway) or local file (dev).
    YOUTUBE_OAUTH_TOKEN_JSON env var takes precedence over file path.
    """
    import os
    import json
    import tempfile
    from google.oauth2.credentials import Credentials

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    token_json = os.getenv("YOUTUBE_OAUTH_TOKEN_JSON", "").strip()
    if token_json:
        data = json.loads(token_json)
        # google.oauth2.credentials.Credentials accepts from_authorized_user_info
        return Credentials.from_authorized_user_info(data, SCOPES)

    creds_path = Path(YOUTUBE_CREDENTIALS)
    if not creds_path.exists():
        raise FileNotFoundError(
            "Credenciales de YouTube no configuradas. "
            "Opciones:\n"
            "• Local: corre `python scripts/setup_youtube.py` y genera credentials/youtube_oauth.json\n"
            "• Railway: pega el contenido de ese JSON en la env var YOUTUBE_OAUTH_TOKEN_JSON"
        )
    return Credentials.from_authorized_user_file(str(creds_path), SCOPES)


def publish_youtube(clip_path: Path, title: str, description: str, tags: list[str]) -> PublisherResult:
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request

        creds = _load_youtube_creds()

        # Refresh token if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        yt = build("youtube", "v3", credentials=creds)
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:15],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(str(clip_path), mimetype="video/mp4", resumable=True)
        request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()
        video_id = response["id"]
        url = f"https://www.youtube.com/shorts/{video_id}"
        log.info(f"YouTube Short publicado: {url}")
        return PublisherResult("youtube", True, url=url)
    except Exception as e:
        log.error(f"YouTube error: {e}")
        return PublisherResult("youtube", False, error=str(e))


# ─── Publicar en todas las plataformas ───────────────────────────────────────

def publish_all(
    clip_path: Path,
    segment: dict,
    platforms: list[str],
) -> list[PublisherResult]:
    title = segment.get("title", clip_path.stem)
    hook = segment.get("hook", title)
    tags = [t.strip("#") for t in hook.split() if t.startswith("#")]

    results = []
    for platform in platforms:
        if platform == "tiktok":
            results.append(publish_tiktok(clip_path, title, tags))
        elif platform == "instagram":
            results.append(publish_instagram(clip_path, hook))
        elif platform == "youtube":
            results.append(publish_youtube(clip_path, title, hook, tags))
        else:
            log.warning(f"Plataforma desconocida: {platform}")

    return results
