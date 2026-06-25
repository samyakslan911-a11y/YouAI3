#!/usr/bin/env python3
"""Download open-source premium fonts for YouAI3 slide generation.

Playfair Display (SIL OFL) — elegant editorial serif for headlines.
Montserrat (SIL OFL) — clean geometric sans-serif for body text.
"""
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

_BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# Variable fonts — brackets must be URL-encoded
FONTS = {
    "PlayfairDisplay.ttf": f"{_BASE}/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    "Montserrat.ttf":      f"{_BASE}/montserrat/Montserrat%5Bwght%5D.ttf",
}


def download_fonts(force: bool = False) -> None:
    ok = skipped = failed = 0
    for name, url in FONTS.items():
        dest = FONTS_DIR / name
        if dest.exists() and not force:
            print(f"  ok {name} (cached)")
            skipped += 1
            continue
        print(f"  -> {name}...", end=" ", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
                f.write(r.read())
            print("done")
            ok += 1
        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1
    print(f"\nFonts: {ok} downloaded, {skipped} cached, {failed} failed")
    if failed:
        print("  Falling back to system fonts — slides will still generate.")


if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    download_fonts(force=force)
