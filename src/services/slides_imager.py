"""
Image acquisition for slides:
  1. iNaturalist — species-specific plant photos (free, no key)
  2. Pexels      — lifestyle/ambient photos (free, PEXELS_API_KEY required)
  3. Fallback    — solid gradient if both fail

Gemini Vision picks the best candidate from downloaded options.
"""
import io, json, logging, os, urllib.parse, urllib.request
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

INAT_BASE  = "https://api.inaturalist.org/v1"
PEXELS_BASE = "https://api.pexels.com/v1"
W, H = 1080, 1350


# ── iNaturalist ───────────────────────────────────────────────────────────────

def _inat_photos(species: str, n: int = 6) -> list[str]:
    """Return up to n photo URLs from iNaturalist for a species."""
    try:
        url = (
            f"{INAT_BASE}/observations"
            f"?taxon_name={urllib.parse.quote(species)}"
            "&photos=true&quality_grade=research"
            f"&per_page={n}&order_by=votes"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "YouAI3/1.0 (content-generator)"},
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        urls = []
        for obs in data.get("results", []):
            for photo in obs.get("photos", []):
                src = photo.get("url", "")
                # iNat thumbnail → large: replace "square" with "large"
                src = src.replace("/square.", "/large.")
                if src:
                    urls.append(src)
        log.info(f"  iNaturalist [{species}]: {len(urls)} fotos")
        return urls[:n]
    except Exception as e:
        log.warning(f"  iNaturalist error [{species}]: {e}")
        return []


# ── Pexels ────────────────────────────────────────────────────────────────────

def _pexels_photos(query: str, n: int = 6) -> list[str]:
    key = os.getenv("PEXELS_API_KEY", "").strip()
    if not key:
        return []
    url = (
        f"{PEXELS_BASE}/search"
        f"?query={urllib.parse.quote(query)}"
        f"&per_page={n}&orientation=portrait"
    )
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": key, "User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        urls = [p["src"]["portrait"] for p in data.get("photos", [])]
        log.info(f"  Pexels [{query}]: {len(urls)} fotos")
        return urls[:n]
    except Exception as e:
        log.warning(f"  Pexels error [{query}]: {e}")
        return []


# ── Download helper ───────────────────────────────────────────────────────────

def _download(url: str, dest: Path, top_bias: float = 0.25) -> bool:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        # Crop to portrait ratio centered
        iw, ih = img.size
        target_ratio = W / H
        current_ratio = iw / ih
        if current_ratio > target_ratio:
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        elif current_ratio < target_ratio:
            new_h = int(iw / target_ratio)
            # top_bias=0 → center, 0.5 → top edge; plants/nature look better top-biased
            top = int((ih - new_h) * top_bias)
            img = img.crop((0, top, iw, top + new_h))
        img = img.resize((W, H), Image.LANCZOS)
        img.save(dest, quality=92)
        return True
    except Exception as e:
        log.debug(f"  download failed {url[:60]}: {e}")
        return False


# ── Gemini Vision picker ──────────────────────────────────────────────────────

def _pick_best(candidates: list[Path], slide: dict) -> Path:
    """Ask Gemini Vision to pick the best photo for this slide."""
    if len(candidates) == 1:
        return candidates[0]

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        image_type = slide.get("image_type", "lifestyle")
        relevance_hint = (
            "Must show plants, succulents, or nature. "
            if image_type == "lifestyle"
            else "Must show the plant species clearly. "
        )
        prompt = (
            f"Slide headline: \"{slide.get('headline', '')}\"\n"
            f"Image query used: \"{slide.get('image_query', '')}\"\n\n"
            f"I have {len(candidates)} candidate background photos for an Instagram plant/nature slide. "
            f"{relevance_hint}"
            "Pick the ONE photo that best matches the slide topic AND has good composition: "
            "subject in upper 2/3, lower area clear for text overlay, natural lighting, sharp focus. "
            "Strongly prefer photos where the subject matches the headline topic specifically. "
            f"Reply with ONLY a single integer 0-{len(candidates)-1}. No explanation."
        )

        contents: list = [prompt]
        for p in candidates:
            try:
                with open(p, "rb") as f:
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
            except Exception:
                pass

        response = client.models.generate_content(
            model=model_name, contents=contents,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=16,
            ),
        )
        idx = int(response.text.strip().split()[0])
        idx = max(0, min(idx, len(candidates) - 1))
        log.info(f"  Gemini Vision picked photo {idx}/{len(candidates)-1}")
        return candidates[idx]
    except Exception as e:
        log.warning(f"  Gemini Vision fallback (error: {e}), using first photo")
        return candidates[0]


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_image(
    slide: dict,
    tmp_dir: Path,
    extra_keywords: list[str] | None = None,
) -> Path | None:
    """
    Download candidate photos for a slide and return the best one.
    extra_keywords: profile image_keywords used as fallback if primary search yields < 2 results.
    Returns None if all sources fail (caller should use gradient fallback).
    """
    import random as _random
    tmp_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []

    image_type = slide.get("image_type", "lifestyle")
    species    = slide.get("species")
    query      = slide.get("image_query", "succulent plant indoor")
    bias = 0.25 if image_type == "species" else 0.5

    # 1. iNaturalist for species slides
    if image_type == "species" and species:
        urls = _inat_photos(species, n=6)
        for i, url in enumerate(urls):
            dest = tmp_dir / f"inat_{i}.jpg"
            if _download(url, dest, top_bias=bias):
                candidates.append(dest)
            if len(candidates) >= 4:
                break

    # 2. Pexels primary query
    if len(candidates) < 3:
        pexels_query = query if image_type == "lifestyle" else f"{species or ''} {query}".strip()
        urls = _pexels_photos(pexels_query, n=6)
        for i, url in enumerate(urls):
            dest = tmp_dir / f"pexels_{i}.jpg"
            if _download(url, dest, top_bias=bias):
                candidates.append(dest)
            if len(candidates) >= 6:
                break

    # 2b. Retry with shorter query if primary was too specific and returned few results
    if len(candidates) < 2 and " " in pexels_query:
        short_q = " ".join(pexels_query.split()[:4])
        urls = _pexels_photos(short_q, n=4)
        for i, url in enumerate(urls):
            dest = tmp_dir / f"pexels_short_{i}.jpg"
            if _download(url, dest, top_bias=bias):
                candidates.append(dest)
            if len(candidates) >= 6:
                break

    # 3. Profile keyword fallback if primary search was thin
    if len(candidates) < 2 and extra_keywords:
        kw = _random.choice(extra_keywords)
        urls = _pexels_photos(kw, n=4)
        for i, url in enumerate(urls):
            dest = tmp_dir / f"pexels_kw_{i}.jpg"
            if _download(url, dest, top_bias=bias):
                candidates.append(dest)
            if len(candidates) >= 6:
                break

    if not candidates:
        log.warning(f"  No images found for slide {slide.get('index')}, using fallback")
        return None

    return _pick_best(candidates, slide)
