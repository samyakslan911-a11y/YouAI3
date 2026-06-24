import json
import os
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="YouAI3 API")

# ALLOWED_ORIGINS env var lets Railway/Vercel restrict CORS without code changes.
# Falls back to * for local development.
_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (single-user, no persistence needed)
_jobs: dict[str, dict] = {}

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Models ────────────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    url: str
    dry_run: bool = False
    caption_style: str = "capcut"   # "capcut" | "subtitles" | "none"
    face_track: bool = True


class ResearchRequest(BaseModel):
    query: str
    max_results: int = 10
    min_ratio: float = 3.0
    language: str = "es"
    cc_only: bool = False


# ── Background pipeline ───────────────────────────────────────────────────────

def _run_pipeline(job_id: str, url: str, dry_run: bool, caption_style: str = "capcut", face_track: bool = True):
    from src.core.pipeline import ContentPipeline
    from src.services import editor

    job = _jobs[job_id]
    job["status"] = "running"
    job["logs"] = []

    def log(msg: str):
        job["logs"].append(msg)

    try:
        log(f"Iniciando pipeline: {url}")
        pipeline = ContentPipeline(dry_run=dry_run)

        from src.services import downloader, transcriber, analyzer
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
                # Write sidecar JSON so the gallery can show title/hook without a DB
                sidecar = clip_path.with_suffix(".json")
                sidecar.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
                clips.append(meta)
                log(f"Clip {i+1} listo: {clip_path.name}")
            except Exception as e:
                log(f"Clip {i+1} omitido: {e}")

        job["status"] = "done"
        job["clips"] = clips
        log(f"Pipeline completado: {len(clips)} clips")

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["logs"].append(f"Error: {e}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/jobs")
def create_job(req: ProcessRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"status": "queued", "logs": [], "clips": [], "error": ""}
    background_tasks.add_task(_run_pipeline, job_id, req.url, req.dry_run, req.caption_style, req.face_track)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/jobs")
def list_jobs():
    return [{"id": k, **v} for k, v in _jobs.items()]


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
            except Exception:
                pass
        clips.append(meta)
    return {"clips": clips}


@app.get("/api/clips/{filename}")
def serve_clip(filename: str):
    path = OUTPUT_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        raise HTTPException(status_code=404, detail="Clip not found")
    return FileResponse(path, media_type="video/mp4")


@app.get("/api/analytics")
def analytics(days: int = 28):
    from src.services.analytics import get_report
    try:
        return {"report": get_report(days=days)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
