"""
SQLite-backed job store. Replaces the in-memory _jobs dict so jobs survive
process restarts within a deployment.
"""
import json
import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path("output/jobs.db")
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                logs TEXT NOT NULL DEFAULT '[]',
                clips TEXT NOT NULL DEFAULT '[]',
                error TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT (unixepoch('now', 'subsec'))
            )
        """)
        c.commit()


def create(job_id: str, url: str) -> dict:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO jobs (id, url) VALUES (?, ?)",
            (job_id, url),
        )
        c.commit()
    return get(job_id)


def update(job_id: str, **fields) -> None:
    allowed = {"status", "logs", "clips", "error"}
    cols = {k: v for k, v in fields.items() if k in allowed}
    if not cols:
        return
    # Serialize lists to JSON
    params = {k: json.dumps(v) if isinstance(v, list) else v for k, v in cols.items()}
    set_clause = ", ".join(f"{k} = ?" for k in params)
    with _lock, _conn() as c:
        c.execute(
            f"UPDATE jobs SET {set_clause} WHERE id = ?",
            (*params.values(), job_id),
        )
        c.commit()


def get(job_id: str) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_all() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["logs"] = json.loads(d["logs"])
    d["clips"] = json.loads(d["clips"])
    return d
