import re
import requests
from src.utils.config import YOUTUBE_API_KEY
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE = "https://www.googleapis.com/youtube/v3"


def _api(endpoint: str, params: dict) -> dict:
    params["key"] = YOUTUBE_API_KEY
    r = requests.get(f"{_BASE}/{endpoint}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def _parse_duration(iso: str) -> int:
    """PT1H2M3S → seconds"""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def _search_videos(query: str, count: int, language: str, cc_only: bool = False) -> list[str]:
    params = {
        "part": "id",
        "type": "video",
        "q": query,
        "maxResults": min(count, 50),
        "relevanceLanguage": language,
        "videoDuration": "medium",  # 4-20 min — good source for clips
    }
    if cc_only:
        params["videoLicense"] = "creativeCommon"
    data = _api("search", params)
    return [item["id"]["videoId"] for item in data.get("items", [])]


def _get_video_details(video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    data = _api("videos", {
        "part": "snippet,statistics,contentDetails",
        "id": ",".join(video_ids),
    })
    videos = []
    for item in data.get("items", []):
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        duration = _parse_duration(item.get("contentDetails", {}).get("duration", ""))
        views = int(stats.get("viewCount", 0))
        if views < 1000 or duration < 60:
            continue
        videos.append({
            "id": item["id"],
            "url": f"https://youtu.be/{item['id']}",
            "title": snippet.get("title", ""),
            "channel_id": snippet.get("channelId", ""),
            "channel_name": snippet.get("channelTitle", ""),
            "views": views,
            "likes": int(stats.get("likeCount", 0)),
            "duration_s": duration,
            "published": snippet.get("publishedAt", "")[:10],
        })
    return videos


def _get_channel_avg_views(channel_ids: list[str]) -> dict[str, float]:
    if not channel_ids:
        return {}
    data = _api("channels", {
        "part": "statistics",
        "id": ",".join(channel_ids),
    })
    avgs = {}
    for item in data.get("items", []):
        stats = item.get("statistics", {})
        total_views = int(stats.get("viewCount", 0))
        video_count = int(stats.get("videoCount", 1)) or 1
        avgs[item["id"]] = total_views / video_count
    return avgs


def search_outliers(
    query: str,
    max_results: int = 10,
    min_outlier_ratio: float = 3.0,
    language: str = "es",
    cc_only: bool = False,
) -> list[dict]:
    """
    Returns videos that are outliers in their channel — they got significantly
    more views than the channel's average, which signals viral-worthy content.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY no configurada en .env")

    log.info(f'Buscando outliers: "{query}" (idioma={language})')

    video_ids = _search_videos(query, max_results * 3, language, cc_only)
    if not video_ids:
        return []

    videos = _get_video_details(video_ids)
    if not videos:
        return []

    channel_ids = list({v["channel_id"] for v in videos})
    channel_avgs = _get_channel_avg_views(channel_ids)

    scored = []
    for v in videos:
        avg = channel_avgs.get(v["channel_id"], 0)
        if avg > 0:
            v["outlier_ratio"] = round(v["views"] / avg, 1)
            v["channel_avg_views"] = int(avg)
            scored.append(v)

    outliers = [v for v in scored if v["outlier_ratio"] >= min_outlier_ratio]
    result = sorted(outliers, key=lambda x: x["outlier_ratio"], reverse=True)[:max_results]

    log.info(f"Encontrados {len(result)} outliers de {len(videos)} videos analizados")
    return result
