"""
Custom user-defined slide styles.
Users supply: name, accent HEX, base_hue (calido/frio/natural), darkness (claro/suave/oscuro).
We derive a full style dict compatible with slides_composer.STYLES.
"""
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.utils.config import OUTPUT_DIR

log = logging.getLogger(__name__)
DB_PATH = OUTPUT_DIR / "jobs.db"


@dataclass
class CustomStyle:
    id: str
    name: str
    accent_hex: str
    base_hue: str     # calido | frio | natural
    darkness: str     # claro | suave | oscuro
    derived: dict     # full STYLES-format dict
    created_at: str


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _scale(c: tuple, factor: float) -> tuple:
    return tuple(min(255, max(0, int(v * factor))) for v in c)


def derive_style_dict(accent_hex: str, base_hue: str, darkness: str) -> dict:
    """Generate a full slides_composer style dict from 3 simple inputs."""
    accent = _hex_to_rgb(accent_hex)
    accent2 = _scale(accent, 0.70)

    base_hues = {
        "calido":   {"overlay": (28, 16, 6),  "overlay2": (52, 28, 12)},
        "frio":     {"overlay": (6, 12, 28),  "overlay2": (12, 22, 52)},
        "natural":  {"overlay": (8, 16, 6),   "overlay2": (16, 32, 10)},
    }
    darkness_cfg = {
        "claro":  {"photo_tint": 0.05, "card_alpha": 175, "bot_alpha": 145},
        "suave":  {"photo_tint": 0.09, "card_alpha": 192, "bot_alpha": 170},
        "oscuro": {"photo_tint": 0.18, "card_alpha": 210, "bot_alpha": 200},
    }

    hue = base_hues.get(base_hue, base_hues["natural"])
    dark = darkness_cfg.get(darkness, darkness_cfg["suave"])

    # Secondary color: lighter/desaturated version of accent
    secondary = tuple(min(255, max(0, int(v * 0.55 + 165 * 0.45))) for v in accent)
    bloom = _scale(accent, 0.42)
    card_bg = (*hue["overlay"], dark["card_alpha"])

    return {
        "overlay":    hue["overlay"],
        "overlay2":   hue["overlay2"],
        "accent":     accent,
        "accent2":    accent2,
        "primary":    (252, 250, 240),
        "secondary":  secondary,
        "bloom_color": bloom,
        "font_h": "bold",  "size_h": 84,
        "font_b": "light", "size_b": 42,
        "dots":    accent,
        "card_bg": card_bg,
        "photo_tint": dark["photo_tint"],
        "_custom_bot_alpha": dark["bot_alpha"],
    }


def _init_table() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_styles (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                accent_hex  TEXT NOT NULL,
                base_hue    TEXT NOT NULL,
                darkness    TEXT NOT NULL,
                derived     TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)


def _row(row: tuple) -> CustomStyle:
    return CustomStyle(
        id=row[0], name=row[1], accent_hex=row[2],
        base_hue=row[3], darkness=row[4],
        derived=json.loads(row[5]), created_at=row[6],
    )


def list_custom() -> list[CustomStyle]:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id,name,accent_hex,base_hue,darkness,derived,created_at "
            "FROM custom_styles ORDER BY created_at"
        ).fetchall()
    return [_row(r) for r in rows]


def get_custom(style_id: str) -> CustomStyle | None:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id,name,accent_hex,base_hue,darkness,derived,created_at "
            "FROM custom_styles WHERE id=?", (style_id,)
        ).fetchone()
    return _row(row) if row else None


def create_custom(name: str, accent_hex: str, base_hue: str, darkness: str) -> CustomStyle:
    _init_table()
    derived = derive_style_dict(accent_hex, base_hue, darkness)
    cs = CustomStyle(
        id=str(uuid.uuid4())[:8],
        name=name,
        accent_hex=accent_hex,
        base_hue=base_hue,
        darkness=darkness,
        derived=derived,
        created_at=date.today().isoformat(),
    )
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO custom_styles (id,name,accent_hex,base_hue,darkness,derived,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (cs.id, cs.name, cs.accent_hex, cs.base_hue, cs.darkness,
             json.dumps(cs.derived, ensure_ascii=False), cs.created_at),
        )
    log.info(f"Custom style created: {cs.name} ({cs.id})")
    return cs


def delete_custom(style_id: str) -> bool:
    _init_table()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM custom_styles WHERE id=?", (style_id,))
    return cur.rowcount > 0
