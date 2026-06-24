"""
Persistent publication scheduler backed by SQLite.
A background thread wakes every 30s, finds due jobs, and publishes them.
"""
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.utils.logger import get_logger

log = get_logger(__name__)

_DB_PATH = Path("output/jobs.db")   # same DB as job_store
_lock = threading.Lock()
_thread: threading.Thread | None = None


# ── DB ────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_publishes (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'youtube',
                publish_at TEXT NOT NULL,           -- ISO-8601 UTC
                status TEXT NOT NULL DEFAULT 'pending',
                result_url TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.commit()


def schedule(filename: str, publish_at: datetime, platform: str = "youtube") -> dict:
    sid = str(uuid.uuid4())[:8]
    iso = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO scheduled_publishes (id, filename, platform, publish_at) VALUES (?,?,?,?)",
            (sid, filename, platform, iso),
        )
        c.commit()
    log.info(f"Publicación programada: {filename} → {iso}")
    return get(sid)


def cancel(sid: str) -> bool:
    with _lock, _conn() as c:
        rows = c.execute(
            "UPDATE scheduled_publishes SET status='cancelled' WHERE id=? AND status='pending'",
            (sid,),
        ).rowcount
        c.commit()
    return rows > 0


def get(sid: str) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM scheduled_publishes WHERE id=?", (sid,)).fetchone()
    return dict(row) if row else None


def list_all() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT * FROM scheduled_publishes ORDER BY publish_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


def _due_jobs() -> list[dict]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT * FROM scheduled_publishes WHERE status='pending' AND publish_at <= ?",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]


def _mark(sid: str, status: str, result_url: str = "", error: str = "") -> None:
    with _lock, _conn() as c:
        c.execute(
            "UPDATE scheduled_publishes SET status=?, result_url=?, error=? WHERE id=?",
            (status, result_url, error, sid),
        )
        c.commit()


# ── Background worker ─────────────────────────────────────────────────────────

def _worker() -> None:
    log.info("Scheduler iniciado")
    while True:
        try:
            for job in _due_jobs():
                _execute(job)
        except Exception as e:
            log.error(f"Scheduler error: {e}")
        time.sleep(30)


def _execute(job: dict) -> None:
    from pathlib import Path as P
    from src.utils.config import OUTPUT_DIR
    from src.services.publisher import publish_youtube

    sid = job["id"]
    clip_path = P(OUTPUT_DIR) / job["filename"]

    if not clip_path.exists():
        _mark(sid, "error", error="Archivo no encontrado")
        return

    # Load title/hook from sidecar
    title, hook = clip_path.stem, ""
    sidecar = clip_path.with_suffix(".json")
    if sidecar.exists():
        try:
            saved = json.loads(sidecar.read_text(encoding="utf-8"))
            title = saved.get("title", title)
            hook = saved.get("hook", "")
        except Exception:
            pass

    log.info(f"Publicando programado: {job['filename']} en {job['platform']}")
    _mark(sid, "running")

    if job["platform"] == "youtube":
        result = publish_youtube(clip_path, title, hook, [])
    else:
        _mark(sid, "error", error=f"Plataforma no soportada: {job['platform']}")
        return

    if result.success:
        _mark(sid, "done", result_url=result.url)
        log.info(f"Publicación programada completada: {result.url}")
    else:
        _mark(sid, "error", error=result.error)
        log.error(f"Publicación programada falló: {result.error}")


def start_background() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _thread = threading.Thread(target=_worker, daemon=True, name="scheduler")
    _thread.start()
