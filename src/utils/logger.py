import logging
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent.parent / "logs" / "pipeline.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setFormatter(_fmt)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(_fmt)
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger
