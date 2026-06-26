import io
import json
import os
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from src.services import job_store, scheduler
from src.utils.config import OUTPUT_DIR

# Dedicated executor for CPU/IO-heavy pipeline jobs — keeps uvicorn's event loop free
_pipeline_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipeline")

app = FastAPI(title="YouAI3 API")

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR.mkdir(exist_ok=True)

@app.on_event("startup")
def startup():
    job_store.init()
    scheduler.init()
    scheduler.start_background()


# ── Models ────────────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    url: str
    dry_run: bool = False
    caption_style: str = "capcut"
    face_track: bool = True


class QueueRequest(BaseModel):
    urls: List[str]
    dry_run: bool = False
    caption_style: str = "capcut"
    face_track: bool = True


# ── Background pipeline ───────────────────────────────────────────────────────

def _run_pipeline(job_id: str, url: str, dry_run: bool, caption_style: str = "capcut", face_track: bool = True):
    from src.services import downloader, transcriber, analyzer, editor

    def log(msg: str):
        job_store.append_log(job_id, msg)

    job_store.update(job_id, status="running", logs=[])

    try:
        log(f"Iniciando pipeline: {url}")

        video_path = downloader.download(url)
        log(f"Video descargado: {video_path.name}")

        duration = editor.get_video_duration(video_path)
        log(f"Duración: {duration:.1f}s")

        segments_raw = transcriber.transcribe(video_path)
        log(f"Transcripción: {len(segments_raw)} segmentos")

        video_title = video_path.stem.replace("_", " ")
        viral_segments = analyzer.analyze(segments_raw, video_title)
        log(f"Momentos virales: {len(viral_segments)}")

        clips = []
        for i, seg in enumerate(viral_segments):
            try:
                log(f"Procesando clip {i+1}/{len(viral_segments)}: {seg.get('title')}")
                clip_path = editor.process_segment(
                    video_path, seg, i, duration,
                    all_segments=segments_raw,
                    caption_style=caption_style,
                    face_track=face_track,
                )
                meta = {
                    "filename": clip_path.name,
                    "title": seg.get("title", ""),
                    "hook": seg.get("hook", ""),
                    "score": seg.get("score"),
                    "virality_reason": seg.get("virality_reason", ""),
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                }
                # Generate thumbnail
                try:
                    from src.services.thumbnailer import generate_thumbnail
                    thumb = generate_thumbnail(
                        clip_path,
                        title=meta["title"],
                        hook=meta["hook"],
                        score=meta["score"],
                    )
                    meta["thumbnail"] = thumb.name
                    log(f"Thumbnail generado: {thumb.name}")
                except Exception as te:
                    log(f"Thumbnail omitido: {te}")

                # Silence removal
                try:
                    from src.services import silence
                    silenced = clip_path.with_name(clip_path.stem + "_ns.mp4")
                    result_path = silence.remove_silence(clip_path, silenced)
                    if result_path != clip_path:
                        silenced.replace(clip_path)  # atomic replace (works on Windows too)
                        log(f"Silencio eliminado: {clip_path.name}")
                except Exception as se:
                    log(f"Silence removal omitido: {se}")

                # Upload to R2
                try:
                    from src.services import storage
                    r2_url = storage.upload_clip(clip_path)
                    if r2_url:
                        meta["r2_url"] = r2_url
                        log(f"R2 upload OK: {clip_path.name}")
                    if meta.get("thumbnail"):
                        from pathlib import Path as P
                        r2_thumb = storage.upload_thumbnail(OUTPUT_DIR / meta["thumbnail"])
                        if r2_thumb:
                            meta["r2_thumbnail"] = r2_thumb
                except Exception as re:
                    log(f"R2 upload omitido: {re}")

                sidecar = clip_path.with_suffix(".json")
                sidecar.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                job = job_store.get(job_id)
                job_store.update(job_id, clips=job["clips"] + [meta])  # clips per-job, no contention
                log(f"Clip {i+1} listo: {clip_path.name}")
            except Exception as e:
                log(f"Clip {i+1} omitido: {e}")

        job = job_store.get(job_id)
        job_store.update(job_id, status="done")
        log(f"Pipeline completado: {len(job['clips'])} clips")

    except Exception as e:
        job_store.update(job_id, status="error", error=str(e))
        job_store.append_log(job_id, f"Error: {e}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    checks: dict = {"status": "ok"}

    # DB reachable
    try:
        job_store.list_all()
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e)
        checks["status"] = "degraded"

    # Scheduler alive
    try:
        from src.services import scheduler as _sched
        alive = getattr(_sched, "_thread", None)
        checks["scheduler"] = "ok" if (alive and alive.is_alive()) else "dead"
        if checks["scheduler"] == "dead":
            checks["status"] = "degraded"
    except Exception:
        checks["scheduler"] = "unknown"

    # R2 configured (optional)
    try:
        from src.services import storage
        checks["r2"] = "configured" if storage.is_configured() else "not_configured"
    except Exception:
        checks["r2"] = "unknown"

    return checks


@app.post("/api/jobs")
def create_job(req: ProcessRequest):
    job_id = str(uuid.uuid4())[:8]
    job_store.create(job_id, req.url)
    _pipeline_executor.submit(_run_pipeline, job_id, req.url, req.dry_run, req.caption_style, req.face_track)
    return {"job_id": job_id}


@app.post("/api/queue")
def create_queue(req: QueueRequest):
    urls = [u.strip() for u in req.urls if u.strip()]
    if not urls:
        raise HTTPException(status_code=422, detail="No URLs provided")
    job_ids = []
    for url in urls:
        job_id = str(uuid.uuid4())[:8]
        job_store.create(job_id, url)
        _pipeline_executor.submit(_run_pipeline, job_id, url, req.dry_run, req.caption_style, req.face_track)
        job_ids.append(job_id)
    return {"job_ids": job_ids}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs")
def list_jobs():
    return job_store.list_all()


@app.get("/api/research")
def research(
    query: str,
    max_results: int = 10,
    min_ratio: float = 3.0,
    language: str = "es",
    cc_only: bool = False,
):
    from src.services.researcher import search_outliers
    try:
        videos = search_outliers(
            query=query,
            max_results=max_results,
            min_outlier_ratio=min_ratio,
            language=language,
            cc_only=cc_only,
        )
        return {"videos": videos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/clips")
def list_clips():
    clips = []
    for f in sorted(OUTPUT_DIR.glob("*_final.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        meta: dict = {"filename": f.name, "size_mb": round(f.stat().st_size / 1_048_576, 1)}
        sidecar = f.with_suffix(".json")
        if sidecar.exists():
            try:
                saved = json.loads(sidecar.read_text(encoding="utf-8"))
                meta["title"] = saved.get("title", "")
                meta["hook"] = saved.get("hook", "")
                meta["score"] = saved.get("score")
                meta["virality_reason"] = saved.get("virality_reason", "")
                meta["thumbnail"] = saved.get("thumbnail")
                meta["published"] = saved.get("published", {})
            except Exception:
                pass
        clips.append(meta)
    return {"clips": clips}


def _safe_path(base: Path, *parts: str) -> Path:
    """Resolve path and verify it stays within base — prevents path traversal."""
    path = (base / Path(*parts)).resolve()
    if not path.is_relative_to(base.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return path


@app.get("/api/clips/{filename}")
def serve_clip(filename: str):
    path = _safe_path(OUTPUT_DIR, filename)
    if not path.exists() or not path.name.endswith((".mp4", ".jpg")):
        raise HTTPException(status_code=404, detail="Clip not found")
    media = "video/mp4" if filename.endswith(".mp4") else "image/jpeg"
    return FileResponse(path, media_type=media)


@app.post("/api/clips/{filename}/thumbnail")
def regen_thumbnail(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")
    title, hook, score = path.stem, "", None
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        try:
            saved = json.loads(sidecar.read_text(encoding="utf-8"))
            title = saved.get("title", title)
            hook = saved.get("hook", "")
            score = saved.get("score")
        except Exception:
            pass
    try:
        from src.services.thumbnailer import generate_thumbnail
        thumb_path = path.with_name(path.stem + "_thumb.jpg")
        if thumb_path.exists():
            thumb_path.unlink()  # force regen
        thumb = generate_thumbnail(path, title=title, hook=hook, score=score)
        # update sidecar
        if sidecar.exists():
            try:
                saved = json.loads(sidecar.read_text(encoding="utf-8"))
                saved["thumbnail"] = thumb.name
                sidecar.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
        return {"thumbnail": thumb.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PublishRequest(BaseModel):
    platform: str = "youtube"
    title: str = ""
    description: str = ""
    tags: List[str] = []
    topic: str = ""   # used by AI music selector (optional, auto-read from sidecar)
    style: str = ""   # visual style (botanico, dark_jungle, etc.)


@app.get("/api/platforms")
def get_platforms():
    """Return which platforms are configured and their published clip counts."""
    import os
    from pathlib import Path as P

    yt_ok = bool(os.getenv("YOUTUBE_OAUTH_TOKEN_JSON") or P(os.getenv("YOUTUBE_CREDENTIALS", "credentials/youtube_oauth.json")).exists())
    ig_ok = bool(os.getenv("INSTAGRAM_USERNAME") and os.getenv("INSTAGRAM_PASSWORD"))
    tt_ok = P(os.getenv("TIKTOK_COOKIES_FILE", "cookies/tiktok.json")).exists()

    return {
        "youtube":   {"configured": yt_ok, "label": "YouTube Shorts",
                      "hint": "Corre scripts/setup_youtube.py o agrega YOUTUBE_OAUTH_TOKEN_JSON"},
        "tiktok":    {"configured": tt_ok, "label": "TikTok",
                      "hint": "Exporta cookies con EditThisCookie y guárdalas en cookies/tiktok.json"},
        "instagram": {"configured": ig_ok, "label": "Instagram Reels",
                      "hint": "Agrega INSTAGRAM_USERNAME e INSTAGRAM_PASSWORD en .env"},
    }


@app.post("/api/clips/{filename}/publish")
def publish_clip(filename: str, req: PublishRequest):
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")

    title, description, tags = req.title, req.description, req.tags
    sidecar = path.with_suffix(".json")
    meta: dict = {}
    if sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            if not title:
                title = meta.get("title", path.stem)
            if not description:
                description = meta.get("hook", "")
            if not tags:
                hook = meta.get("hook", "")
                tags = [w.strip("#") for w in hook.split() if w.startswith("#")]
        except Exception:
            pass

    if not title:
        title = path.stem

    # Read topic/style from sidecar metadata for AI music selection
    topic = req.topic or meta.get("topic", "")
    style = req.style or meta.get("style", "botanico")

    from src.services.publisher import (
        publish_youtube, publish_tiktok,
        publish_instagram, publish_instagram_playwright,
    )

    if req.platform == "youtube":
        result = publish_youtube(path, title, description, tags)
    elif req.platform == "tiktok":
        result = publish_tiktok(path, title, tags, topic, style)
    elif req.platform == "instagram":
        # Use Playwright (+ AI music) when topic metadata is available
        if topic:
            result = publish_instagram_playwright(path, description or title, topic, style)
        else:
            result = publish_instagram(path, description or title)
    else:
        raise HTTPException(status_code=422, detail=f"Plataforma desconocida: {req.platform}")

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    # Persist published URL in sidecar
    if sidecar.exists():
        try:
            published = meta.get("published", {})
            published[req.platform] = result.url
            meta["published"] = published
            sidecar.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    return {"platform": result.platform, "url": result.url}


class ScheduleRequest(BaseModel):
    publish_at: str        # ISO-8601 local or UTC, e.g. "2026-06-25T15:30:00"
    platform: str = "youtube"


@app.post("/api/clips/{filename}/schedule")
def schedule_clip(filename: str, req: ScheduleRequest):
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")
    try:
        # Accept both naive and aware ISO strings
        dt_str = req.publish_at.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(dt_str)
        except ValueError:
            dt = datetime.fromisoformat(req.publish_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="La fecha debe ser en el futuro")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: {e}")
    job = scheduler.schedule(filename, dt, req.platform)
    return job


@app.get("/api/schedule")
def list_schedule():
    return scheduler.list_all()


@app.delete("/api/schedule/{sid}")
def cancel_schedule(sid: str):
    if not scheduler.cancel(sid):
        raise HTTPException(status_code=404, detail="No encontrado o ya ejecutado")
    return {"cancelled": sid}


@app.get("/api/analytics")
def analytics(days: int = 28):
    from src.services.analytics import get_report
    try:
        return {"report": get_report(days=days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analytics/insights")
def analytics_insights(days: int = 28):
    from src.services.analytics import get_report, get_insights
    try:
        report = get_report(days=days)
        insights = get_insights(report)
        return {"insights": insights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Content Profiles ──────────────────────────────────────────────────────────

class ProfileCreateRequest(BaseModel):
    name: str


class BrandKitRequest(BaseModel):
    accent_hex: str | None = None
    base_hue: str | None = None     # natural | calido | frio
    darkness: str | None = None     # claro | suave | oscuro
    font: str | None = None         # editorial | moderno | elegante
    voice: str | None = None


class ProfileResponse(BaseModel):
    id: str
    name: str
    expert_context: str
    style: str
    content_angles: list
    image_keywords: list
    created_at: str
    brand_accent_hex: str | None = None
    brand_base_hue: str | None = None
    brand_darkness: str | None = None
    brand_font: str | None = None
    brand_voice: str | None = None


@app.get("/api/profiles")
def list_profiles():
    from src.services.content_profiles import load_profiles
    from dataclasses import asdict
    return [ProfileResponse(**asdict(p)) for p in load_profiles()]


@app.post("/api/profiles")
def create_profile(req: ProfileCreateRequest):
    from src.services.content_profiles import generate_profile
    from dataclasses import asdict
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    try:
        profile = generate_profile(req.name.strip())
        return ProfileResponse(**asdict(profile))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/profiles/{profile_id}")
def remove_profile(profile_id: str):
    from src.services.content_profiles import delete_profile
    return {"success": delete_profile(profile_id)}


@app.put("/api/profiles/{profile_id}/brand-kit")
def save_brand_kit(profile_id: str, req: BrandKitRequest):
    from src.services.content_profiles import update_brand_kit
    from dataclasses import asdict
    profile = update_brand_kit(
        profile_id, req.accent_hex, req.base_hue, req.darkness, req.font, req.voice
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse(**asdict(profile))


# ── Custom Styles ─────────────────────────────────────────────────────────────

class StyleCreateRequest(BaseModel):
    name: str
    accent_hex: str          # e.g. "#3a8c5f"
    base_hue: str = "natural"   # calido | frio | natural
    darkness: str = "suave"     # claro | suave | oscuro


@app.get("/api/styles")
def list_styles():
    from src.services.slides_composer import STYLES
    from src.services.custom_styles import list_custom
    defaults = [
        {"id": k, "name": k.replace("_", " ").title(), "accent_hex": "#{:02x}{:02x}{:02x}".format(*v["accent"][:3]),
         "is_custom": False, "darkness": "oscuro" if v.get("photo_tint", 0.10) >= 0.15 else "suave"}
        for k, v in STYLES.items()
    ]
    custom = [
        {"id": c.id, "name": c.name, "accent_hex": c.accent_hex,
         "base_hue": c.base_hue, "darkness": c.darkness, "is_custom": True}
        for c in list_custom()
    ]
    return {"styles": defaults + custom}


@app.post("/api/styles")
def create_style(req: StyleCreateRequest):
    from src.services.custom_styles import create_custom
    valid_hues = {"calido", "frio", "natural"}
    valid_dark = {"claro", "suave", "oscuro"}
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="name is required")
    if req.base_hue not in valid_hues:
        raise HTTPException(status_code=422, detail=f"base_hue must be one of {valid_hues}")
    if req.darkness not in valid_dark:
        raise HTTPException(status_code=422, detail=f"darkness must be one of {valid_dark}")
    try:
        cs = create_custom(req.name.strip(), req.accent_hex, req.base_hue, req.darkness)
        from dataclasses import asdict
        d = asdict(cs)
        d.pop("derived")
        return d
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/styles/{style_id}")
def delete_style(style_id: str):
    from src.services.custom_styles import delete_custom
    return {"success": delete_custom(style_id)}


# ── Slides ────────────────────────────────────────────────────────────────────

class SlidesRequest(BaseModel):
    topic: str
    style: str = "botanico"     # default style name OR custom style id
    series_part: int | None = None
    profile_id: str = ""
    slide_count: int = 10       # 5 | 7 | 10 | 15


SLIDES_OUTPUT = OUTPUT_DIR / "slides"


@app.post("/api/slides")
def create_slides(req: SlidesRequest):
    from src.services import slides_generator
    from src.services.slides_composer import STYLES
    from src.services.custom_styles import get_custom

    # Resolve style — could be default name or custom style ID
    style_override: dict | None = None
    effective_style = req.style

    custom_style = get_custom(req.style)
    if custom_style:
        style_override = custom_style.derived
        effective_style = "botanico"   # base layout fallback name
    elif req.style not in STYLES:
        effective_style = "botanico"

    if req.profile_id:
        from src.services.content_profiles import get_profile, build_brand_style
        _profile = get_profile(req.profile_id)
        if _profile:
            # Brand kit takes priority over manual style selection
            brand_override = build_brand_style(_profile)
            if brand_override:
                style_override = brand_override
                effective_style = "botanico"  # base name for fallback only
            elif req.style == "botanico" and not style_override:
                effective_style = _profile.style
    else:
        _profile = None

    job_id = str(uuid.uuid4())[:8]
    job_store.create(job_id, url=f"slides:{req.topic}")

    profile_snapshot = _profile
    style_snap = style_override

    def _run():
        job_store.update(job_id, status="running")
        try:
            meta = slides_generator.generate(
                req.topic, effective_style, req.series_part,
                profile=profile_snapshot,
                style_override=style_snap,
                on_progress=lambda msg: job_store.append_log(job_id, msg),
                slide_count=req.slide_count,
            )
            try:
                from src.services import storage
                slug = meta["slug"]
                slides_dir = SLIDES_OUTPUT / slug / "images"
                for img_name in meta.get("images", []):
                    storage.upload_slide_image(slug, img_name, slides_dir / img_name)
                if meta.get("video"):
                    storage.upload_slide_video(slug, SLIDES_OUTPUT / slug / "video.mp4")
            except Exception:
                pass  # R2 optional
            job_store.update(job_id, status="done", clips=[{
                "slug": meta["slug"],
                "title": meta["title"],
                "image_count": len(meta["images"]),
                "has_video": meta["video"] is not None,
            }])
        except Exception as e:
            job_store.update(job_id, status="error", error=str(e))

    _pipeline_executor.submit(_run)
    return {"job_id": job_id}


@app.get("/api/slides")
def list_slides():
    from src.services import slides_generator
    return {"sets": slides_generator.list_sets()}


@app.get("/api/slides/{slug}")
def get_slides(slug: str):
    from src.services import slides_generator
    meta = slides_generator.get_set(slug)
    if not meta:
        raise HTTPException(status_code=404, detail="Slide set not found")
    return meta


@app.get("/api/slides/{slug}/images/{filename}")
def serve_slide_image(slug: str, filename: str):
    from fastapi.responses import RedirectResponse
    path = _safe_path(SLIDES_OUTPUT, slug, "images", filename)
    if path.exists():
        return FileResponse(str(path), media_type="image/png")
    # File not on local disk (Railway ephemeral FS after re-deploy) — try R2
    try:
        from src.services import storage
        r2_url = storage.public_url(f"slides/{slug}/images/{filename}")
        if r2_url:
            return RedirectResponse(url=r2_url, status_code=302)
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/api/slides/{slug}/video")
def serve_slide_video(slug: str):
    from fastapi.responses import RedirectResponse
    path = _safe_path(SLIDES_OUTPUT, slug, "video.mp4")
    if path.exists():
        return FileResponse(str(path), media_type="video/mp4")
    try:
        from src.services import storage
        r2_url = storage.public_url(f"slides/{slug}/video.mp4")
        if r2_url:
            return RedirectResponse(url=r2_url, status_code=302)
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Video not found")


@app.get("/api/slides/{slug}/zip")
def download_slides_zip(slug: str):
    slide_dir = _safe_path(SLIDES_OUTPUT, slug)
    if not slide_dir.exists():
        raise HTTPException(status_code=404, detail="Slide set not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        images_dir = slide_dir / "images"
        if images_dir.exists():
            for img in sorted(images_dir.glob("*.png")):
                zf.write(img, arcname=f"images/{img.name}")
        video = slide_dir / "video.mp4"
        if video.exists():
            zf.write(video, arcname="video.mp4")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


class SlideUpdateRequest(BaseModel):
    headline: str | None = None
    body: str | None = None


@app.patch("/api/slides/{slug}/slides/{index}")
def update_slide_text(slug: str, index: int, req: SlideUpdateRequest):
    """Re-render a single slide with updated headline/body text."""
    import shutil as _shutil
    from src.services import slides_composer as _composer

    slide_dir = _safe_path(SLIDES_OUTPUT, slug)
    meta_path = slide_dir / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Slide set not found")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    slides = meta.get("slides", [])
    slide = next((s for s in slides if s.get("index") == index), None)
    if slide is None:
        raise HTTPException(status_code=404, detail=f"Slide {index} not found")

    if req.headline is not None:
        slide["headline"] = req.headline
    if req.body is not None:
        slide["body"] = req.body

    bg_path = slide_dir / "images" / f"bg_{index:02d}.jpg"
    bg = bg_path if bg_path.exists() else None

    style = meta.get("style", "botanico")
    style_override = meta.get("style_override")
    out_png = slide_dir / "images" / f"{index:02d}.png"
    total = len(slides)

    try:
        _composer.compose_slide(slide, bg, style, out_png,
                                total_slides=total,
                                style_override=style_override)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-render failed: {e}")

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"updated": True, "index": index}


class SlidesPublishRequest(BaseModel):
    platform: str


@app.post("/api/slides/{slug}/publish")
def publish_slides(slug: str, req: SlidesPublishRequest):
    slide_dir = _safe_path(SLIDES_OUTPUT, slug)
    if not slide_dir.exists():
        raise HTTPException(status_code=404, detail="Slide set not found")

    meta_path = slide_dir / "metadata.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Slide set metadata not found")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    if not meta.get("video"):
        raise HTTPException(status_code=400, detail="Este set no tiene video")

    video_path = slide_dir / meta["video"]
    topic = meta.get("topic", "")
    style = meta.get("style", "botanico")
    caption = (meta.get("title") or topic)

    import src.services.publisher as _pub
    _pub._current_topic = topic
    _pub._current_style = style

    from src.services.publisher import publish_instagram_playwright, publish_tiktok

    if req.platform == "instagram":
        result = publish_instagram_playwright(video_path, caption, topic, style)
    elif req.platform == "tiktok":
        result = publish_tiktok(video_path, topic, [])
    else:
        raise HTTPException(status_code=422, detail=f"Plataforma desconocida: {req.platform}")

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {"platform": result.platform, "url": result.url, "success": True}


@app.delete("/api/clips/{filename}")
def delete_clip(filename: str):
    """Delete a clip and its sidecar/thumbnail from local disk."""
    path = _safe_path(OUTPUT_DIR, filename)
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")
    removed = [str(path)]
    path.unlink()
    for ext in [".json", ".jpg"]:
        side = path.with_suffix(ext)
        if side.exists():
            side.unlink()
            removed.append(str(side))
    return {"deleted": removed}


@app.post("/api/cleanup")
def cleanup_old_clips(older_than_days: int = 7):
    """Delete local clips older than N days to free container disk space."""
    import time
    cutoff = time.time() - older_than_days * 86400
    deleted, freed = [], 0
    for f in OUTPUT_DIR.glob("*.mp4"):
        if f.stat().st_mtime < cutoff:
            size = f.stat().st_size
            f.unlink(missing_ok=True)
            for ext in [".json", ".jpg"]:
                f.with_suffix(ext).unlink(missing_ok=True)
            deleted.append(f.name)
            freed += size
    return {"deleted": len(deleted), "freed_mb": round(freed / 1_048_576, 1), "files": deleted}


# ── Canva Connect API — OAuth flow ────────────────────────────────────────────

@app.get("/api/canva/authorize")
def canva_authorize():
    """
    Step 1: Redirect to Canva OAuth consent screen.
    Visit this URL once in a browser to grant access.
    """
    from fastapi.responses import RedirectResponse
    from src.services.canva_service import generate_auth_url
    if not os.getenv("CANVA_CLIENT_ID"):
        raise HTTPException(502, "CANVA_CLIENT_ID not set in env")
    url = generate_auth_url()
    return RedirectResponse(url=url)


@app.get("/api/canva/callback")
def canva_callback(code: str, state: str):
    """
    Step 2: Canva redirects here after user consent.
    Shows tokens — copy CANVA_ACCESS_TOKEN, CANVA_REFRESH_TOKEN,
    CANVA_TOKEN_EXPIRES_AT to Railway env vars.
    """
    import time as _time
    from src.services.canva_service import exchange_code, canva
    tokens = exchange_code(code, state)
    canva.store_tokens(tokens)
    return {
        "status": "authorized",
        "instructions": "Add these to Railway env vars and redeploy",
        "CANVA_ACCESS_TOKEN":    tokens["access_token"],
        "CANVA_REFRESH_TOKEN":   tokens.get("refresh_token", ""),
        "CANVA_TOKEN_EXPIRES_AT": str(int(_time.time()) + tokens.get("expires_in", 3600)),
    }


@app.get("/api/canva/test")
def canva_test():
    """Verify Canva token and list recent designs (to find Brand Template IDs)."""
    try:
        from src.services.canva_service import canva, _API
        import httpx as _httpx
        # List user's designs — template IDs appear in the URL when you open a Brand Template in Canva
        r = _httpx.get(f"{_API}/designs?ownership=owned&limit=50", headers=canva._h(), timeout=15)
        r.raise_for_status()
        items = r.json().get("items", [])
        return {
            "status": "connected",
            "designs": [{"id": d["id"], "title": d.get("title", ""), "type": d.get("doc_type", "")} for d in items],
            "hint": "Para Brand Templates: abrí cada template en Canva y copiá el ID de la URL: canva.com/brand/templates/{ID}/edit",
        }
    except Exception as e:
        raise HTTPException(500, f"Canva error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
