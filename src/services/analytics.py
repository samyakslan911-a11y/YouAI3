import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests

from src.utils.config import YOUTUBE_CREDENTIALS
from src.utils.logger import get_logger

log = get_logger(__name__)

_ANALYTICS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"
_DATA_URL = "https://www.googleapis.com/youtube/v3/videos"


def _load_creds() -> dict:
    """Load OAuth credentials from env var (Railway) or file (local)."""
    # YOUTUBE_OAUTH_TOKEN_JSON is the canonical var (same as publisher.py)
    token_json = os.getenv("YOUTUBE_OAUTH_TOKEN_JSON", "") or os.getenv("YOUTUBE_TOKEN_JSON", "")
    if token_json:
        return json.loads(token_json)
    creds_path = Path(YOUTUBE_CREDENTIALS)
    if not creds_path.exists():
        raise RuntimeError(
            "No hay credenciales OAuth.\n"
            "Local: corre scripts/setup_youtube.py\n"
            "Railway: pega credentials/youtube_oauth.json en la variable YOUTUBE_OAUTH_TOKEN_JSON"
        )
    return json.loads(creds_path.read_text())


def _get_access_token() -> str:
    creds = _load_creds()
    token = creds.get("token")
    if not token:
        raise RuntimeError("Token vacío — vuelve a correr scripts/setup_youtube.py")

    if creds.get("refresh_token"):
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        }, timeout=10)
        if r.ok:
            new_token = r.json().get("access_token", token)
            # Persist refresh locally if file exists
            creds_path = Path(YOUTUBE_CREDENTIALS)
            if creds_path.exists():
                creds["token"] = new_token
                creds_path.write_text(json.dumps(creds))
            return new_token

    return token


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {_get_access_token()}"}


def get_channel_videos(max_results: int = 50) -> list[dict]:
    """Returns the most recent videos on the authenticated channel."""
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        headers=_auth_header(),
        params={
            "part": "id,snippet",
            "forMine": "true",
            "type": "video",
            "maxResults": max_results,
            "order": "date",
        },
        timeout=15,
    )
    r.raise_for_status()
    return [
        {
            "id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "published": item["snippet"]["publishedAt"][:10],
        }
        for item in r.json().get("items", [])
    ]


def get_video_metrics(video_ids: list[str], days: int = 28) -> list[dict]:
    """
    Fetches retention, CTR, and engagement metrics for a list of video IDs.
    Returns results sorted by average view percentage (retention) descending.
    """
    if not video_ids:
        return []

    end = date.today()
    start = end - timedelta(days=days)

    r = requests.get(
        _ANALYTICS_URL,
        headers=_auth_header(),
        params={
            "ids": "channel==MINE",
            "dimensions": "video",
            "filters": f"video=={','.join(video_ids)}",
            "metrics": ",".join([
                "views",
                "estimatedMinutesWatched",
                "averageViewDuration",
                "averageViewPercentage",
                "likes",
                "comments",
                "shares",
                "subscribersGained",
                "cardClickRate",
                "annotationClickThroughRate",
            ]),
            "startDate": str(start),
            "endDate": str(end),
            "sort": "-averageViewPercentage",
        },
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()

    headers = [h["name"] for h in data.get("columnHeaders", [])]
    results = []
    for row in data.get("rows", []):
        entry = dict(zip(headers, row))
        results.append({
            "id": entry.get("video"),
            "views": int(entry.get("views", 0)),
            "watch_minutes": round(float(entry.get("estimatedMinutesWatched", 0)), 1),
            "avg_view_duration_s": int(entry.get("averageViewDuration", 0)),
            "retention_pct": round(float(entry.get("averageViewPercentage", 0)), 1),
            "likes": int(entry.get("likes", 0)),
            "comments": int(entry.get("comments", 0)),
            "shares": int(entry.get("shares", 0)),
            "subs_gained": int(entry.get("subscribersGained", 0)),
            "card_ctr": round(float(entry.get("cardClickRate", 0)) * 100, 2),
        })
    return results


def get_report(days: int = 28) -> list[dict]:
    """
    Full report: fetches channel videos + their analytics and merges them.
    Returns sorted by retention descending.
    """
    log.info("Obteniendo videos del canal...")
    videos = get_channel_videos()
    if not videos:
        log.info("No hay videos en el canal aún.")
        return []

    video_ids = [v["id"] for v in videos]
    log.info(f"Obteniendo métricas de {len(video_ids)} videos (últimos {days} días)...")
    metrics = get_video_metrics(video_ids, days)

    # Merge title/published into metrics
    meta = {v["id"]: v for v in videos}
    for m in metrics:
        m.update({
            "title": meta.get(m["id"], {}).get("title", ""),
            "published": meta.get(m["id"], {}).get("published", ""),
            "url": f"https://youtu.be/{m['id']}",
        })

    return sorted(metrics, key=lambda x: x["retention_pct"], reverse=True)


def get_insights(report: list[dict]) -> list[str]:
    """
    Use Gemini to generate 4-6 actionable insights from the analytics report.
    Returns a list of insight strings.
    """
    if not report:
        return ["Aún no hay datos suficientes. Publica algunos clips y espera 24-48h."]

    from src.utils.config import GOOGLE_API_KEY
    if not GOOGLE_API_KEY:
        return ["Configura GOOGLE_API_KEY para obtener insights con IA."]

    from google import genai

    summary = "\n".join(
        f"- \"{r['title'][:60]}\" | {r['views']} vistas | {r['retention_pct']}% retención | {r['avg_view_duration_s']}s dur. avg | {r['likes']} likes | +{r['subs_gained']} subs"
        for r in report[:20]
    )

    prompt = f"""Eres un estratega de YouTube Shorts. Analiza estos datos de rendimiento y dame exactamente 5 insights accionables en español, cada uno en una línea que empiece con un emoji relevante. Sé específico con los datos, no genérico.

Datos (últimos 28 días):
{summary}

Responde SOLO con las 5 líneas de insights, sin numeración, sin encabezados."""

    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        lines = [l.strip() for l in response.text.strip().splitlines() if l.strip()]
        return lines[:6]
    except Exception as e:
        log.error(f"Insights error: {e}")
        return [f"Error generando insights: {e}"]
