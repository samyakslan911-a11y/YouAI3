"""
Compose one slide PNG (1080x1350) from a background image + slide data.
Supports 4 layouts × 4 styles.
Premium variable fonts: Playfair Display (headlines) + Montserrat (body).
"""
import logging
import os
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

log = logging.getLogger(__name__)

W, H = 1080, 1350
CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@tucanal")

_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

Layout = Literal["hero", "split", "card", "quote"]
Style  = Literal["terracota", "botanico", "aesthetic", "dark_jungle"]

# Variable font files (Playfair Display + Montserrat, both OFL licensed)
_FONT_FILES = {
    "playfair":   _ASSETS / "PlayfairDisplay.ttf",
    "montserrat": _ASSETS / "Montserrat.ttf",
}

# (font_file_key, variable_weight_axis) per role
_FONT_ROLES: dict[str, tuple[str, int]] = {
    "bold":   ("playfair",   700),   # editorial serif headlines
    "reg":    ("montserrat", 400),   # clean body text
    "light":  ("montserrat", 300),   # detail / handle text
    "lightb": ("montserrat", 600),   # semi-bold accents
}

# System font fallbacks (Railway uses DejaVu/Liberation via fontconfig)
_FALLBACKS: dict[str, list[str]] = {
    "bold":   ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"],
    "reg":    ["C:/Windows/Fonts/arial.ttf",
               "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "light":  ["C:/Windows/Fonts/segoeui.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf"],
    "lightb": ["C:/Windows/Fonts/segoeuib.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}

FontKey = Literal["bold", "reg", "light", "lightb"]


def _font(key: FontKey, size: int) -> ImageFont.FreeTypeFont:
    if key not in _FONT_ROLES:
        raise ValueError(f"Unknown font key '{key}'. Valid: {list(_FONT_ROLES)}")
    file_key, weight = _FONT_ROLES[key]
    asset_path = _FONT_FILES[file_key]
    paths = [str(asset_path)] + _FALLBACKS[key]
    for path in paths:
        try:
            f = ImageFont.truetype(path, size)
            try:
                f.set_variation_by_axes([weight])
            except (AttributeError, OSError):
                pass  # static fallback font — use as-is
            return f
        except OSError:
            continue
    return ImageFont.load_default()


# ── Vibrant style definitions (moodboard aesthetic) ───────────────────────────

STYLES: dict[str, dict] = {
    "terracota": {
        "overlay":   (68, 20, 6),
        "accent":    (228, 140, 65),
        "primary":   (255, 248, 228),
        "secondary": (220, 185, 148),
        "font_h": "bold",  "size_h": 84,
        "font_b": "reg",   "size_b": 40,
        "dots":    (228, 140, 65),
        "card_bg": (45, 12, 3, 218),
    },
    "botanico": {
        "overlay":   (6, 26, 12),
        "accent":    (205, 170, 55),
        "primary":   (250, 245, 220),
        "secondary": (148, 215, 138),
        "font_h": "bold",  "size_h": 82,
        "font_b": "reg",   "size_b": 40,
        "dots":    (205, 170, 55),
        "card_bg": (3, 16, 7, 218),
    },
    "aesthetic": {
        "overlay":   (52, 28, 62),
        "accent":    (232, 172, 212),
        "primary":   (255, 248, 253),
        "secondary": (192, 218, 190),
        "font_h": "lightb", "size_h": 78,
        "font_b": "light",  "size_b": 38,
        "dots":    (232, 172, 212),
        "card_bg": (38, 18, 48, 218),
    },
    "dark_jungle": {
        "overlay":   (2, 10, 5),
        "accent":    (78, 225, 118),
        "primary":   (255, 255, 255),
        "secondary": (148, 232, 170),
        "font_h": "bold",  "size_h": 86,
        "font_b": "reg",   "size_b": 40,
        "dots":    (78, 225, 118),
        "card_bg": (1, 6, 2, 222),
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gradient_bg(color: tuple) -> Image.Image:
    """Gradient with noise texture for fallback when no photo is available."""
    r, g, b = color
    top    = (max(0, r - 20), max(0, g - 16), max(0, b - 12))
    bottom = (min(255, r + 35), min(255, g + 26), min(255, b + 18))
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = (y / H) ** 0.8
        row = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        draw.line([(0, y), (W, y)], fill=row)
    arr   = np.array(img, dtype=np.int16)
    noise = np.random.randint(-8, 9, arr.shape, dtype=np.int16)
    arr   = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img   = Image.fromarray(arr, "RGB")
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vdraw    = ImageDraw.Draw(vignette)
    cx, cy   = W // 2, H // 2
    for ring in range(200, 0, -1):
        alpha = int(130 * ((ring / 200) ** 2))
        vdraw.ellipse(
            [cx - ring * 4, cy - ring * 6, cx + ring * 4, cy + ring * 6],
            fill=(0, 0, 0, alpha),
        )
    return Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")


def _grain_overlay(img: Image.Image, intensity: int = 13) -> Image.Image:
    """Film grain — editorial texture that makes slides look shot on analog camera."""
    arr   = np.array(img.convert("RGB"), dtype=np.int16)
    grain = np.random.normal(0, intensity, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + grain, 0, 255).astype(np.uint8), "RGB")


def _overlay_bottom(base: Image.Image, color: tuple, alpha_top: int, alpha_bot: int) -> Image.Image:
    ov   = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    r, g, b = color
    for y in range(H):
        t = y / H
        a = int(alpha_top + (alpha_bot - alpha_top) * (t ** 0.5))
        draw.line([(0, y), (W, y)], fill=(r, g, b, a))
    return Image.alpha_composite(base.convert("RGBA"), ov)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        words = raw.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            if font.getlength(test) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines


def _strip_emoji(text: str) -> str:
    import re
    return re.sub(
        r"[\U00010000-\U0010ffff"
        r"\U0001F300-\U0001F9FF"
        r"☀-➿"
        r"︀-️"
        r"‍]+",
        "",
        text,
    ).strip()


def _draw_text(
    draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
    color: tuple, max_w: int, cx: int, y: int, gap: int = 14,
    shadow: bool = True,
) -> int:
    text = _strip_emoji(text)
    for line in _wrap(text, font, max_w):
        if not line:
            y += gap
            continue
        bb = draw.textbbox((0, 0), line, font=font)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        x = cx - lw // 2
        if shadow:
            draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 90))
        draw.text((x, y), line, font=font, fill=color)
        y += lh + gap
    return y


def _accent_line(draw: ImageDraw.Draw, color: tuple, cx: int, y: int, w: int = 80) -> int:
    """Thin editorial accent line below headline."""
    draw.rectangle([cx - w // 2, y + 12, cx + w // 2, y + 14], fill=color)
    return y + 32


def _progress_dots(draw: ImageDraw.Draw, style: dict, current: int, total: int = 10):
    r, sp = 4, 18
    tw = (total - 1) * sp
    sx = (W - tw) // 2
    y  = 55
    for i in range(total):
        x = sx + i * sp
        if i == current:
            draw.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=style["dots"])
        else:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 45))


def _handle(draw: ImageDraw.Draw, style: dict, handle: str = CHANNEL_HANDLE):
    f = _font("light", 26)
    draw.text((W - 72, H - 46), handle, font=f, fill=(*style["accent"], 170), anchor="rm")


def _page_number(draw: ImageDraw.Draw, current: int, total: int, s: dict) -> None:
    """Editorial page counter — bottom left, light font."""
    f = _font("light", 24)
    draw.text((64, H - 46), f"{current + 1:02d} / {total:02d}", font=f,
              fill=(*s["accent"], 150))


def _text_block(
    draw: ImageDraw.Draw, slide: dict, s: dict,
    cx: int, mw: int, ty: int,
    fh: ImageFont.FreeTypeFont, fb: ImageFont.FreeTypeFont,
    gap_h: int = 18, gap_b: int = 12,
) -> None:
    ey = _draw_text(draw, slide["headline"], fh, s["primary"], mw, cx, ty, gap=gap_h)
    ey = _accent_line(draw, s["accent"], cx, ey)
    if slide.get("body"):
        _draw_text(draw, slide["body"], fb, s["secondary"], mw, cx, ey, gap=gap_b)
    _handle(draw, s)


# ── Layout renderers ──────────────────────────────────────────────────────────

def _layout_hero(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Full-bleed photo, strong gradient only on bottom 45%, large editorial headline."""
    result = _overlay_bottom(img, s["overlay"], alpha_top=0, alpha_bot=200)
    draw   = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    fh = _font(s["font_h"], s["size_h"] + 8)
    pad, cx, mw = 72, W // 2, W - 144
    ty = int(H * 0.60)
    ey = _draw_text(draw, slide["headline"], fh, s["primary"], mw, cx, ty, gap=22)
    _accent_line(draw, s["accent"], cx, ey)
    _handle(draw, s)
    return result.convert("RGB")


def _layout_split(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Photo top 52%, text area bottom 48% with clean separator."""
    result = _overlay_bottom(img, s["overlay"], alpha_top=25, alpha_bot=230)
    draw   = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    split_y = int(H * 0.52)
    draw.rectangle([0, split_y, W, split_y + 2], fill=(*s["accent"], 140))

    fh = _font(s["font_h"], s["size_h"])
    fb = _font(s["font_b"], s["size_b"])
    _text_block(draw, slide, s, cx=W // 2, mw=W - 160, ty=split_y + 44, fh=fh, fb=fb)
    return result.convert("RGB")


def _layout_card(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Blurred full photo + floating frosted card with headline + body."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=8))
    result  = _overlay_bottom(blurred, s["overlay"], alpha_top=90, alpha_bot=170)
    draw    = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    card_pad = 56
    card_x1, card_x2 = card_pad, W - card_pad
    card_y1, card_y2 = int(H * 0.27), int(H * 0.87)

    card_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    card_draw  = ImageDraw.Draw(card_layer)
    card_draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y2],
        radius=28, fill=s["card_bg"],
    )
    # Subtle card border for editorial depth
    card_draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y2],
        radius=28, outline=(*s["accent"][:3], 50), width=1,
    )
    result = Image.alpha_composite(result.convert("RGBA"), card_layer)
    draw   = ImageDraw.Draw(result)

    fh = _font(s["font_h"], s["size_h"] - 8)
    fb = _font(s["font_b"], s["size_b"] - 2)
    _text_block(draw, slide, s, cx=W // 2, mw=card_x2 - card_x1 - 64,
                ty=card_y1 + 50, fh=fh, fb=fb, gap_h=16, gap_b=12)
    return result.convert("RGB")


def _layout_quote(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Heavy blur + overlay, oversized centered text — pattern interrupt slide."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=12))
    result  = _overlay_bottom(blurred, s["overlay"], alpha_top=165, alpha_bot=230)
    draw    = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    fh  = _font(s["font_h"], s["size_h"] + 10)
    fb  = _font(s["font_b"], s["size_b"])
    mw  = W - 120
    # Large decorative quote mark
    fq  = _font("bold", 180)
    bb  = draw.textbbox((0, 0), "“", font=fq)
    draw.text((W // 2 - (bb[2] - bb[0]) // 2, int(H * 0.08)),
              "“", font=fq, fill=(*s["accent"][:3], 40))

    lines_h = len(_wrap(slide["headline"], fh, mw)) * (s["size_h"] + 24)
    ty = max(int(H * 0.30), (H - lines_h) // 2 - 60)
    _text_block(draw, slide, s, cx=W // 2, mw=mw, ty=ty, fh=fh, fb=fb, gap_h=22, gap_b=12)
    return result.convert("RGB")


# ── Public API ────────────────────────────────────────────────────────────────

_LAYOUT_FN = {
    "hero":              _layout_hero,
    "split":             _layout_split,
    "card":              _layout_card,
    "quote":             _layout_quote,
    "pattern_interrupt": _layout_quote,
}


def compose_slide(
    slide: dict,
    bg_image: Path | None,
    style_name: Style,
    output_path: Path,
    total_slides: int = 10,
) -> Path:
    s      = STYLES[style_name]
    layout = slide.get("layout", "hero")
    fn     = _LAYOUT_FN.get(layout, _layout_hero)

    if bg_image and bg_image.exists():
        img = Image.open(bg_image).convert("RGB")
        if img.size != (W, H):
            # Smart crop: keep subject in upper-center (plants/nature subjects tend to be there)
            img = ImageOps.fit(img, (W, H), Image.LANCZOS, centering=(0.5, 0.3))
        # Subtle sharpening for print-quality crispness
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=65, threshold=3))
    else:
        img = _gradient_bg(s["overlay"])

    result = fn(img, slide, s)

    # Editorial page counter (drawn after layout so it sits on top)
    page_draw = ImageDraw.Draw(result)
    _page_number(page_draw, slide.get("index", 0), total_slides, s)

    # Film grain overlay — gives editorial analog texture to every slide
    result = _grain_overlay(result.convert("RGB"), intensity=13)

    result.save(output_path, quality=95)
    log.info(f"  Slide {slide['index']:02d} [{layout}] -> {output_path.name}")
    return output_path
