"""
Slides Generator orchestrator.
Coordinates content → images → composition → video → design_memory.
"""
import json, logging, os, re, shutil, sqlite3, tempfile, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import slides_content, slides_imager, slides_composer, slides_video
from src.utils.config import OUTPUT_DIR as _BASE_OUTPUT_DIR

log = logging.getLogger(__name__)

OUTPUT_DIR = _BASE_OUTPUT_DIR / "slides"
DB_PATH    = _BASE_OUTPUT_DIR / "jobs.db"


# ── design_memory table ───────────────────────────────────────────────────────

def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS design_memory (
                id              TEXT PRIMARY KEY,
                created_at      TEXT,
                topic           TEXT,
                style           TEXT,
                layouts_used    TEXT,
                image_sources   TEXT,
                hook_pattern    TEXT,
                slug            TEXT,
                published_at    TEXT,
                platform        TEXT,
                saves           INTEGER,
                reach           INTEGER,
                profile_visits  INTEGER,
                saves_rate      REAL,
                perf_score      REAL
            )
        """)


def _save_design(design_id: str, topic: str, style: str, content: dict,
                 image_sources: dict) -> None:
    layouts = list({s.get("layout", "hero") for s in content.get("slides", [])})
    hook = content["slides"][0].get("headline", "")[:60] if content.get("slides") else ""

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO design_memory
            (id, created_at, topic, style, layouts_used, image_sources, hook_pattern, slug)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            design_id,
            datetime.now(timezone.utc).isoformat(),
            topic, style,
            json.dumps(layouts),
            json.dumps(image_sources),
            hook,
            design_id,
        ))


def _top_designs(n: int = 5) -> list[dict]:
    """Return top-n performing designs for Gemini context injection."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT topic, style, layouts_used, hook_pattern, saves_rate
                FROM design_memory
                WHERE perf_score IS NOT NULL
                ORDER BY perf_score DESC
                LIMIT ?
            """, (n,)).fetchall()
        return [
            {"topic": r[0], "style": r[1], "layouts": json.loads(r[2] or "[]"),
             "hook": r[3], "saves_rate": r[4]}
            for r in rows
        ]
    except Exception:
        return []


# ── Slug helpers ──────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:40]


# ── Main generator ────────────────────────────────────────────────────────────

def generate(
    topic: str,
    style: slides_composer.Style = "botanico",
    series_part: int | None = None,
    on_progress: callable = None,
) -> dict:
    """
    Generate a full slide set for a topic.
    Returns metadata dict with slug, image paths, video path, hashtags.
    """
    _init_db()

    design_id = str(uuid.uuid4())[:8]
    slug = f"{_slugify(topic)}-{design_id}"
    out_dir = OUTPUT_DIR / slug
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    def _log(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    # ── 1. Generate content via Gemini ────────────────────────────────────────
    _log("Generando contenido con Gemini...")
    top = _top_designs()
    content = slides_content.generate_content(topic, style, series_part)
    _log(f"Contenido listo: {len(content['slides'])} slides")

    # ── 2. Fetch images in parallel, compose slides ───────────────────────────
    image_paths: list[Path] = []
    image_sources: dict = {"inat": 0, "pexels": 0, "fallback": 0}
    slides = content["slides"]

    _log("Descargando imágenes en paralelo...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        def _fetch_one(slide: dict) -> tuple[int, Path | None]:
            idx = slide.get("index", 0)
            slide_tmp = tmp_path / f"slide_{idx:02d}"
            slide_tmp.mkdir(exist_ok=True)
            return idx, slides_imager.fetch_image(slide, slide_tmp)

        bg_by_idx: dict[int, Path | None] = {}
        with ThreadPoolExecutor(max_workers=min(len(slides), 6)) as pool:
            futures = {pool.submit(_fetch_one, s): s for s in slides}
            for fut in as_completed(futures):
                idx, bg = fut.result()
                bg_by_idx[idx] = bg

        # Compose in index order (deterministic output)
        _log(f"Componiendo {len(slides)} slides...")
        for slide in sorted(slides, key=lambda s: s.get("index", 0)):
            idx = slide.get("index", len(image_paths))
            bg = bg_by_idx.get(idx)

            if bg is None:
                image_sources["fallback"] += 1
            elif "inat" in bg.name:
                image_sources["inat"] += 1
            else:
                image_sources["pexels"] += 1

            out_png = img_dir / f"{idx:02d}.png"
            slides_composer.compose_slide(slide, bg, style, out_png)
            image_paths.append(out_png)

    src_summary = f"inat={image_sources['inat']} pexels={image_sources['pexels']} fallback={image_sources['fallback']}"
    _log(f"Imágenes listas: {src_summary}")

    # ── 3. Assemble video ─────────────────────────────────────────────────────
    # ── 3. Generate TTS narration ─────────────────────────────────────────────
    audio_path: Path | None = None
    try:
        from . import slides_tts
        narration = out_dir / "narration.mp3"
        audio_path = slides_tts.generate_narration(content["slides"], narration)
        if audio_path:
            _log("Narración generada")
    except Exception as e:
        log.warning(f"TTS omitido: {e}")

    # ── 4. Assemble video ─────────────────────────────────────────────────────
    _log("Ensamblando video...")
    video_path = out_dir / "video.mp4"
    try:
        slides_video.assemble_video(image_paths, video_path, audio_path=audio_path)
        _log(f"Video listo: {video_path.name}")
    except Exception as e:
        log.error(f"Video assembly failed: {e}")
        video_path = None

    # ── 4. Write metadata ─────────────────────────────────────────────────────
    metadata = {
        "design_id":    design_id,
        "slug":         slug,
        "topic":        topic,
        "style":        style,
        "series_part":  series_part,
        "title":        content.get("title", topic),
        "hook_variants": content.get("hook_variants", []),
        "hashtags":     content.get("hashtags", {}),
        "slides":       content.get("slides", []),
        "images":       [p.name for p in image_paths],
        "video":        video_path.name if video_path else None,
        "image_sources": image_sources,
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _save_design(design_id, topic, style, content, image_sources)
    log.info(f"Slide set listo: {slug} ({len(image_paths)} imágenes)")
    return metadata


# ── List / Get helpers ────────────────────────────────────────────────────────

def list_sets() -> list[dict]:
    if not OUTPUT_DIR.exists():
        return []
    result = []
    for meta_path in sorted(OUTPUT_DIR.glob("*/metadata.json"), reverse=True):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            result.append({
                "slug":       m["slug"],
                "topic":      m["topic"],
                "style":      m["style"],
                "title":      m.get("title", m["topic"]),
                "created_at": m["created_at"],
                "image_count": len(m.get("images", [])),
                "has_video":  m.get("video") is not None,
            })
        except Exception:
            pass
    return result


def get_set(slug: str) -> dict | None:
    meta_path = OUTPUT_DIR / slug / "metadata.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))
