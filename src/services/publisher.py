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

def publish_tiktok(
    clip_path: Path, title: str, tags: list[str],
    topic: str = "", style: str = "botanico",
) -> PublisherResult:
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
        from src.services.music_selector import suggest_audio_queries, select_sound_tiktok

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context()
            raw = json.loads(cookies_path.read_text(encoding="utf-8"))
            # unwrap double array (EditThisCookie fork export format)
            if isinstance(raw, list) and raw and isinstance(raw[0], list):
                raw = raw[0]
            ctx.add_cookies(raw)
            page = ctx.new_page()

            page.goto("https://www.tiktok.com/upload")
            page.wait_for_selector("input[type='file']", timeout=15000)
            page.set_input_files("input[type='file']", str(clip_path))
            page.wait_for_selector(".caption-input", timeout=30000)

            # ── AI trending music selection ──────────────────────────────
            effective_topic = topic or title
            queries = suggest_audio_queries(effective_topic, style, platform="tiktok")
            selected = select_sound_tiktok(page, queries)
            if selected:
                log.info(f"TikTok: música trending seleccionada → '{selected}'")
            else:
                log.info("TikTok: publicando sin música (selector no disponible)")
            # ────────────────────────────────────────────────────────────

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


# ─── Instagram Reels (Playwright — con selección de música trending) ─────────

def publish_instagram_playwright(
    clip_path: Path, caption: str, topic: str = "", style: str = "botanico"
) -> PublisherResult:
    """
    Publish a Reel via Playwright web automation.
    Attempts to select trending audio matching topic+style before publishing.
    Falls back gracefully to publishing without music if the UI changes.
    """
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        return PublisherResult(
            "instagram", False,
            error="INSTAGRAM_USERNAME y INSTAGRAM_PASSWORD no configurados en .env"
        )

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return PublisherResult("instagram", False, error="playwright no instalado")

    try:
        from src.services.music_selector import suggest_audio_queries, select_sound_instagram

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            page = ctx.new_page()

            # Login
            page.goto("https://www.instagram.com/accounts/login/")
            page.wait_for_selector("input[name='username']", timeout=15000)
            page.fill("input[name='username']", INSTAGRAM_USERNAME)
            page.fill("input[name='password']", INSTAGRAM_PASSWORD)
            page.click("button[type='submit']")
            page.wait_for_url("**/instagram.com/**", timeout=20000)
            time.sleep(2)

            # Dismiss "Save info" / "Turn on notifications" dialogs
            for label in ["Not Now", "Ahora no", "Not now"]:
                btn = page.query_selector(f"button:has-text('{label}')")
                if btn:
                    btn.click()
                    time.sleep(0.8)

            # Open Create post
            create_btn = page.query_selector(
                "svg[aria-label='New post'], "
                "a[href='/create/style/'], "
                "div[role='button']:has-text('Create')"
            )
            if not create_btn:
                # Fallback: click the + icon in nav
                page.click("svg[aria-label*='reate'], a[href*='/create']")
            else:
                create_btn.click()
            time.sleep(1.5)

            # Select file
            file_input = page.query_selector("input[type='file']")
            if file_input:
                file_input.set_input_files(str(clip_path))
            else:
                return PublisherResult("instagram", False, error="file input not found in create UI")

            time.sleep(2)

            # Switch to Reel format if needed
            reel_btn = page.query_selector("button:has-text('Reel'), div:has-text('Reels')")
            if reel_btn:
                reel_btn.click()
                time.sleep(1)

            # Advance through editing steps (Next → Next → Caption)
            for _ in range(3):
                next_btn = page.query_selector("button:has-text('Next'), button:has-text('Siguiente')")
                if next_btn:
                    next_btn.click()
                    time.sleep(1.5)

            # ── AI trending music selection ──────────────────────────────
            queries = suggest_audio_queries(topic or caption[:40], style, platform="instagram")
            selected = select_sound_instagram(page, queries)
            if selected:
                log.info(f"Instagram: música trending seleccionada → '{selected}'")
            else:
                log.info("Instagram: publicando sin música adicional")
            # ────────────────────────────────────────────────────────────

            # Fill caption
            caption_box = page.query_selector(
                "div[aria-label*='caption'], div[aria-label*='Caption'], "
                "div[contenteditable='true']"
            )
            if caption_box:
                caption_box.click()
                caption_box.type(caption[:2200], delay=20)
                time.sleep(0.5)

            # Share
            share_btn = page.query_selector(
                "button:has-text('Share'), button:has-text('Compartir')"
            )
            if not share_btn:
                return PublisherResult("instagram", False, error="Share button not found")
            share_btn.click()
            time.sleep(5)
            browser.close()

        log.info("Instagram Reel (Playwright): publicado")
        return PublisherResult(
            "instagram", True,
            url=f"https://www.instagram.com/{INSTAGRAM_USERNAME}/reels/"
        )

    except Exception as e:
        log.error(f"Instagram Playwright error: {type(e).__name__}")
        safe = str(e).replace(INSTAGRAM_USERNAME or "", "***").replace(INSTAGRAM_PASSWORD or "", "***")
        return PublisherResult("instagram", False, error=safe)


# ─── Instagram Reels (instagrapi fallback — sin selección de música) ──────────

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
        log.error(f"Instagram error: {type(e).__name__}")
        # Sanitize: instagrapi may embed credentials in exception messages
        safe_msg = str(e).replace(INSTAGRAM_USERNAME, "***").replace(INSTAGRAM_PASSWORD, "***")
        return PublisherResult("instagram", False, error=safe_msg)


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
    topic: str = "",
    style: str = "botanico",
) -> list[PublisherResult]:
    """
    Publish to one or more platforms.
    topic + style are used by the AI music selector to choose trending audio.
    When provided, Instagram uses Playwright (with music); otherwise instagrapi.
    """
    effective_topic = topic or segment.get("topic", "")
    effective_style = style or segment.get("style", "botanico")

    title = segment.get("title", clip_path.stem)
    hook  = segment.get("hook", title)
    tags  = [t.strip("#") for t in hook.split() if t.startswith("#")]

    results = []
    for platform in platforms:
        if platform == "tiktok":
            results.append(publish_tiktok(clip_path, title, tags, effective_topic, effective_style))
        elif platform == "instagram":
            # Use Playwright (+ music) when topic is known; fallback to instagrapi
            if effective_topic:
                results.append(
                    publish_instagram_playwright(clip_path, hook, effective_topic, effective_style)
                )
            else:
                results.append(publish_instagram(clip_path, hook))
        elif platform == "youtube":
            results.append(publish_youtube(clip_path, title, hook, tags))
        else:
            log.warning(f"Plataforma desconocida: {platform}")

    return results
