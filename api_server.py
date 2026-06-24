import json
import os
import uuid
from pathlib import Path
from typing import List

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.services import job_store, scheduler

app = FastAPI(title="YouAI3 API")

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = Path("output")
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
        job = job_store.get(job_id)
        logs = job["logs"] + [msg]
        job_store.update(job_id, logs=logs)

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

                sidecar = clip_path.with_suffix(".json")
                sidecar.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                job = job_store.get(job_id)
                job_store.update(job_id, clips=job["clips"] + [meta])
                log(f"Clip {i+1} listo: {clip_path.name}")
            except Exception as e:
                log(f"Clip {i+1} omitido: {e}")

        job = job_store.get(job_id)
        job_store.update(job_id, status="done")
        log(f"Pipeline completado: {len(job['clips'])} clips")

    except Exception as e:
        job_store.update(job_id, status="error", error=str(e))
        job = job_store.get(job_id)
        job_store.update(job_id, logs=job["logs"] + [f"Error: {e}"])


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/jobs")
def create_job(req: ProcessRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    job_store.create(job_id, req.url)
    background_tasks.add_task(_run_pipeline, job_id, req.url, req.dry_run, req.caption_style, req.face_track)
    return {"job_id": job_id}


@app.post("/api/queue")
def create_queue(req: QueueRequest, background_tasks: BackgroundTasks):
    urls = [u.strip() for u in req.urls if u.strip()]
    if not urls:
        raise HTTPException(status_code=422, detail="No URLs provided")
    job_ids = []
    for url in urls:
        job_id = str(uuid.uuid4())[:8]
        job_store.create(job_id, url)
        background_tasks.add_task(_run_pipeline, job_id, url, req.dry_run, req.caption_style, req.face_track)
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
            except Exception:
                pass
        clips.append(meta)
    return {"clips": clips}


@app.get("/api/clips/{filename}")
def serve_clip(filename: str):
    path = OUTPUT_DIR / filename
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


@app.post("/api/clips/{filename}/publish")
def publish_clip(filename: str, req: PublishRequest):
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")

    title, description, tags = req.title, req.description, req.tags
    sidecar = path.with_suffix(".json")
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

    from src.services.publisher import publish_youtube, publish_tiktok, publish_instagram

    if req.platform == "youtube":
        result = publish_youtube(path, title, description, tags)
    elif req.platform == "tiktok":
        result = publish_tiktok(path, title, tags)
    elif req.platform == "instagram":
        result = publish_instagram(path, description or title)
    else:
        raise HTTPException(status_code=422, detail=f"Plataforma desconocida: {req.platform}")

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {"platform": result.platform, "url": result.url}


class ScheduleRequest(BaseModel):
    publish_at: str        # ISO-8601 local or UTC, e.g. "2026-06-25T15:30:00"
    platform: str = "youtube"


@app.post("/api/clips/{filename}/schedule")
def schedule_clip(filename: str, req: ScheduleRequest):
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")
    from datetime import datetime, timezone
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
