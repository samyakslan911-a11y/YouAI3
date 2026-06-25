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
    import urllib.parse
    url = (
        f"{PEXELS_BASE}/search"
        f"?query={urllib.parse.quote(query)}"
        f"&per_page={n}&orientation=portrait"
    )
    try:
        req = urllib.request.Request(url, headers={"Authorization": key})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read())
        urls = [p["src"]["portrait"] for p in data.get("photos", [])]
        log.info(f"  Pexels [{query}]: {len(urls)} fotos")
        return urls[:n]
    except Exception as e:
        log.warning(f"  Pexels error [{query}]: {e}")
        return []


# ── Download helper ───────────────────────────────────────────────────────────

def _download(url: str, dest: Path) -> bool:
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
            top = (ih - new_h) // 4  # bias toward top-center for plants
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

        prompt = (
            f"Slide headline: \"{slide.get('headline', '')}\"\n"
            f"Slide body: \"{slide.get('body', '')}\"\n\n"
            f"I have {len(candidates)} candidate background photos for this slide. "
            "Pick the ONE with best: composition (space for text at bottom), "
            "natural lighting, subject clarity, and relevance to the headline. "
            f"Reply with ONLY a single integer 0-{len(candidates)-1}."
        )

        contents: list = [prompt]
        for p in candidates:
            try:
                with open(p, "rb") as f:
                    contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))
            except Exception:
                pass

        response = client.models.generate_content(model=model_name, contents=contents)
        idx = int(response.text.strip().split()[0])
        idx = max(0, min(idx, len(candidates) - 1))
        log.info(f"  Gemini Vision picked photo {idx}/{len(candidates)-1}")
        return candidates[idx]
    except Exception as e:
        log.warning(f"  Gemini Vision fallback (error: {e}), using first photo")
        return candidates[0]


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_image(slide: dict, tmp_dir: Path) -> Path | None:
    """
    Download candidate photos for a slide and return the best one.
    Returns None if all sources fail (caller should use gradient fallback).
    """
    tmp_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []

    image_type = slide.get("image_type", "lifestyle")
    species    = slide.get("species")
    query      = slide.get("image_query", "succulent plant indoor")

    # 1. iNaturalist for species slides
    if image_type == "species" and species:
        urls = _inat_photos(species, n=6)
        for i, url in enumerate(urls):
            dest = tmp_dir / f"inat_{i}.jpg"
            if _download(url, dest):
                candidates.append(dest)
            if len(candidates) >= 4:
                break

    # 2. Pexels for lifestyle or as supplement
    if len(candidates) < 3:
        pexels_query = query if image_type == "lifestyle" else f"{species or ''} {query}".strip()
        urls = _pexels_photos(pexels_query, n=6)
        for i, url in enumerate(urls):
            dest = tmp_dir / f"pexels_{i}.jpg"
            if _download(url, dest):
                candidates.append(dest)
            if len(candidates) >= 6:
                break

    if not candidates:
        log.warning(f"  No images found for slide {slide.get('index')}, using fallback")
        return None

    return _pick_best(candidates, slide)
