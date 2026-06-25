"""
AI-powered trending music selector for Instagram Reels and TikTok.

Gemini generates niche-specific audio search queries based on content topic
and visual style. Playwright then searches and selects trending audio inside
the platform's native upload UI — no external music APIs needed.
"""
import logging
import os

log = logging.getLogger(__name__)

# Mood mapping per visual style — informs the audio search
_STYLE_MOODS: dict[str, list[str]] = {
    "botanico":    ["botanical aesthetic", "plant room chill", "nature lo-fi", "calming green"],
    "dark_jungle": ["dark nature ambient", "jungle mysterious", "deep forest vibes", "moody botanical"],
    "terracota":   ["boho aesthetic", "warm earthy vibes", "mediterranean acoustic", "terracotta aesthetic"],
    "aesthetic":   ["aesthetic lo-fi", "dreamy ambient", "soft aesthetic", "purple aesthetic vibes"],
}

# Platform-specific trending keywords to boost discoverability
_PLATFORM_BOOST: dict[str, str] = {
    "tiktok":    "trending sound",
    "instagram": "viral reels audio",
}


def suggest_audio_queries(
    topic: str,
    style: str = "botanico",
    platform: str = "tiktok",
) -> list[str]:
    """
    Ask Gemini to generate 4 trending audio search queries for the niche.
    Falls back to rule-based queries if Gemini is unavailable.

    Returns list of queries, most likely viral first.
    """
    mood_hints = _STYLE_MOODS.get(style, ["nature aesthetic", "botanical chill"])
    boost = _PLATFORM_BOOST.get(platform, "trending")

    try:
        from google import genai

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        prompt = (
            f"I'm posting a {platform} Reel/video about: \"{topic}\".\n"
            f"Visual style: {style} ({', '.join(mood_hints)}).\n\n"
            f"Generate exactly 4 short audio search queries (2-4 words each) "
            f"that I should search inside {platform}'s audio library to find "
            f"currently trending background music that fits this content.\n"
            f"Focus on music that is viral in the plants/nature/botanical niche.\n"
            f"Reply with ONLY 4 lines, one query per line, no numbering, no quotes."
        )

        resp = client.models.generate_content(model=model, contents=prompt)
        raw = resp.text.strip()
        queries = [line.strip() for line in raw.splitlines() if line.strip()][:4]
        if queries:
            log.info(f"Gemini music queries ({platform}): {queries}")
            return queries

    except Exception as e:
        log.warning(f"Gemini music selector failed: {e} — using rule-based fallback")

    # Rule-based fallback: combine mood hints + platform boost
    first_word = topic.split()[0].lower() if topic.strip() else "nature"
    fallback = [f"{h} {boost}" for h in mood_hints[:3]] + [f"{first_word} aesthetic"]
    return fallback[:4]


def select_sound_tiktok(page, queries: list[str]) -> str | None:
    """
    During an active TikTok upload Playwright page, search for and select
    the most trending sound for the first query that returns results.

    Returns the query/sound name selected, or None if not found.
    Must be called AFTER the caption area is visible (video uploaded).
    """
    import time

    try:
        # TikTok "Add sound" / "Select sound" button
        sound_btn = page.query_selector(
            "[data-e2e='add-sound'], "
            "[data-e2e='select-sound'], "
            "button:has-text('Add sound'), "
            "button:has-text('Select sound')"
        )
        if not sound_btn:
            log.warning("TikTok: botón de audio no encontrado")
            return None

        sound_btn.click()
        time.sleep(1.5)

        for query in queries:
            # Find search input inside the sound modal
            search_input = page.query_selector(
                ".music-search-input input, "
                "[placeholder*='Search'], "
                "[data-e2e='search-input']"
            )
            if not search_input:
                log.warning("TikTok: campo de búsqueda de audio no encontrado")
                return None

            search_input.triple_click()
            search_input.type(query, delay=50)
            page.keyboard.press("Enter")
            time.sleep(2)

            # Try to click the first result (most trending = first item)
            first = page.query_selector(
                ".music-search-item:first-child, "
                ".sound-card:first-child, "
                "[data-e2e='music-item']:first-child, "
                ".tiktok-music-item"
            )
            if first:
                first.click()
                time.sleep(0.8)
                log.info(f"TikTok: audio seleccionado → '{query}'")
                # Confirm selection if there's a confirm button
                confirm = page.query_selector("button[data-e2e='confirm'], button:has-text('Confirm')")
                if confirm:
                    confirm.click()
                    time.sleep(0.5)
                return query

        log.warning("TikTok: ningún resultado de audio encontrado para los queries")
        return None

    except Exception as e:
        log.warning(f"TikTok music select failed (continuando sin audio): {e}")
        return None


def select_sound_instagram(page, queries: list[str]) -> str | None:
    """
    During an active Instagram Reel upload Playwright page, search for and
    select trending audio.

    Returns the query/sound name selected, or None.
    Must be called after the video is staged for upload (editing step).
    """
    import time

    try:
        # Instagram "Add audio" button (various selectors across UI versions)
        audio_btn = page.query_selector(
            "button:has-text('Add audio'), "
            "button:has-text('Agregar audio'), "
            "button[aria-label*='audio'], "
            "button[aria-label*='Audio'], "
            "div[role='button']:has-text('Audio')"
        )
        if not audio_btn:
            log.warning("Instagram: botón de audio no encontrado")
            return None

        audio_btn.click()
        time.sleep(1.5)

        for query in queries:
            search_input = page.query_selector(
                "input[placeholder*='Search'], "
                "input[placeholder*='Buscar'], "
                "input[type='text']"
            )
            if not search_input:
                log.warning("Instagram: campo de búsqueda de audio no encontrado")
                return None

            search_input.triple_click()
            search_input.type(query, delay=60)
            time.sleep(2)

            # First result = most trending/popular
            first = page.query_selector(
                "div[role='listitem']:first-child, "
                "li:first-child button, "
                "[class*='AudioItem']:first-child"
            )
            if first:
                first.click()
                time.sleep(1)
                log.info(f"Instagram: audio seleccionado → '{query}'")
                # Dismiss the audio panel if it stays open
                done_btn = page.query_selector("button:has-text('Done'), button:has-text('Listo')")
                if done_btn:
                    done_btn.click()
                    time.sleep(0.5)
                return query

        log.warning("Instagram: ningún resultado de audio encontrado")
        return None

    except Exception as e:
        log.warning(f"Instagram music select failed (continuando sin audio): {e}")
        return None
