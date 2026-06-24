from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def _dir(name: str, default: str) -> Path:
    p = Path(os.getenv(name, BASE_DIR / default))
    p.mkdir(parents=True, exist_ok=True)
    return p

TMP_DIR    = _dir("TMP_DIR", "tmp")
OUTPUT_DIR = _dir("OUTPUT_DIR", "output")

ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY     = os.getenv("OPENROUTER_API_KEY", "")
GOOGLE_API_KEY         = os.getenv("GOOGLE_API_KEY", "")
YOUTUBE_API_KEY        = os.getenv("YOUTUBE_API_KEY", "") or GOOGLE_API_KEY
GEMINI_MODEL           = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
WHISPER_MODEL          = os.getenv("WHISPER_MODEL", "base")

INSTAGRAM_USERNAME     = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD     = os.getenv("INSTAGRAM_PASSWORD", "")
TIKTOK_COOKIES_FILE    = os.getenv("TIKTOK_COOKIES_FILE", str(BASE_DIR / "cookies" / "tiktok.json"))
YOUTUBE_CREDENTIALS    = os.getenv("YOUTUBE_CREDENTIALS_FILE", str(BASE_DIR / "credentials" / "youtube_oauth.json"))

MAX_CLIPS              = int(os.getenv("MAX_CLIPS", "5"))
CLIP_MAX_SECONDS       = int(os.getenv("CLIP_MAX_SECONDS", "60"))
