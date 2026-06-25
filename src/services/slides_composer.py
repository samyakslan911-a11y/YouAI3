"""
Compose one slide PNG (1080x1350) from a background image + slide data.
Supports 4 layouts × 4 styles.
"""
import logging
import os
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

log = logging.getLogger(__name__)

W, H = 1080, 1350
CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@tucanal")

Layout = Literal["hero", "split", "card", "quote"]
Style  = Literal["terracota", "botanico", "aesthetic", "dark_jungle"]

# ── Windows font paths (Railway uses Liberation/DejaVu via fontconfig) ────────
_FONTS = {
    "bold":   ["C:/Windows/Fonts/arialbd.ttf",   "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
    "reg":    ["C:/Windows/Fonts/arial.ttf",      "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    "light":  ["C:/Windows/Fonts/segoeui.ttf",    "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf"],
    "lightb": ["C:/Windows/Fonts/segoeuib.ttf",   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}

FontKey = Literal["bold", "reg", "light", "lightb"]


def _font(key: FontKey, size: int) -> ImageFont.FreeTypeFont:
    if key not in _FONTS:
        raise ValueError(f"Unknown font key '{key}'. Valid: {list(_FONTS)}")
    for path in _FONTS[key]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ── Style definitions ─────────────────────────────────────────────────────────

STYLES: dict[str, dict] = {
    "terracota": {
        "overlay":   (75, 28, 10),
        "accent":    (215, 138, 72),
        "primary":   (255, 245, 225),
        "secondary": (220, 190, 155),
        "font_h": "bold",  "size_h": 78,
        "font_b": "reg",   "size_b": 38,
        "dots": (215, 138, 72),
        "card_bg": (50, 18, 6, 210),
    },
    "botanico": {
        "overlay":   (10, 35, 18),
        "accent":    (182, 148, 58),
        "primary":   (242, 238, 215),
        "secondary": (175, 200, 155),
        "font_h": "bold",  "size_h": 74,
        "font_b": "reg",   "size_b": 38,
        "dots": (182, 148, 58),
        "card_bg": (6, 22, 10, 210),
    },
    "aesthetic": {
        "overlay":   (65, 42, 72),
        "accent":    (215, 175, 200),
        "primary":   (252, 245, 250),
        "secondary": (190, 215, 185),
        "font_h": "lightb", "size_h": 70,
        "font_b": "light",  "size_b": 36,
        "dots": (215, 175, 200),
        "card_bg": (45, 28, 52, 210),
    },
    "dark_jungle": {
        "overlay":   (4, 18, 10),
        "accent":    (75, 200, 115),
        "primary":   (255, 255, 255),
        "secondary": (155, 220, 170),
        "font_h": "bold",  "size_h": 82,
        "font_b": "reg",   "size_b": 40,
        "dots": (75, 200, 115),
        "card_bg": (2, 10, 5, 215),
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gradient_bg(color: tuple) -> Image.Image:
    """Two-stop gradient with subtle radial vignette — looks intentional, not broken."""
    r, g, b = color
    # Darker shade at top, slightly warmer/lighter at bottom
    top    = (max(0, r - 18), max(0, g - 14), max(0, b - 10))
    bottom = (min(255, r + 30), min(255, g + 22), min(255, b + 15))

    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = (y / H) ** 0.8  # slightly ease the gradient
        row = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
        draw.line([(0, y), (W, y)], fill=row)

    # Subtle noise texture (+/-6 per channel) so it reads as editorial dark bg
    arr   = np.array(img, dtype=np.int16)
    noise = np.random.randint(-6, 7, arr.shape, dtype=np.int16)
    arr   = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img   = Image.fromarray(arr, "RGB")

    # Soft radial vignette darkening the corners
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vdraw    = ImageDraw.Draw(vignette)
    cx, cy   = W // 2, H // 2
    for ring in range(200, 0, -1):
        alpha = int(120 * ((ring / 200) ** 2))  # quadratic falloff
        vdraw.ellipse(
            [cx - ring * 4, cy - ring * 6, cx + ring * 4, cy + ring * 6],
            fill=(0, 0, 0, alpha),
        )
    img = Image.alpha_composite(img.convert("RGBA"), vignette).convert("RGB")
    return img


def _overlay_bottom(base: Image.Image, color: tuple, alpha_top: int, alpha_bot: int) -> Image.Image:
    ov = Image.new("RGBA", base.size, (0, 0, 0, 0))
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


def _draw_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
               color: tuple, max_w: int, cx: int, y: int, gap: int = 14,
               shadow: bool = True) -> int:
    text = _strip_emoji(text)
    for line in _wrap(text, font, max_w):
        if not line:
            y += gap
            continue
        bb = draw.textbbox((0, 0), line, font=font)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        x = cx - lw // 2
        if shadow:
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 80))
        draw.text((x, y), line, font=font, fill=color)
        y += lh + gap
    return y


def _accent_line(draw: ImageDraw.Draw, color: tuple, cx: int, y: int, w: int = 90) -> int:
    draw.rectangle([cx - w // 2, y + 10, cx + w // 2, y + 14], fill=color)
    return y + 30


def _progress_dots(draw: ImageDraw.Draw, style: dict, current: int, total: int = 10):
    r, sp = 5, 20
    tw = (total - 1) * sp
    sx = (W - tw) // 2
    y = 58
    for i in range(total):
        x = sx + i * sp
        if i == current:
            draw.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2],
                         fill=style["dots"])
        else:
            draw.ellipse([x - r, y - r, x + r, y + r],
                         fill=(255, 255, 255, 55))


def _handle(draw: ImageDraw.Draw, style: dict, handle: str = CHANNEL_HANDLE):
    f = _font("reg", 28)
    draw.text((W - 80, H - 50), handle, font=f,
              fill=(*style["accent"], 180), anchor="rm")


def _text_block(
    draw: ImageDraw.Draw, slide: dict, s: dict,
    cx: int, mw: int, ty: int,
    fh: ImageFont.FreeTypeFont, fb: ImageFont.FreeTypeFont,
    gap_h: int = 16, gap_b: int = 11,
) -> None:
    """Headline → accent line → optional body → handle. Shared by split/card/quote."""
    ey = _draw_text(draw, slide["headline"], fh, s["primary"], mw, cx, ty, gap=gap_h)
    ey = _accent_line(draw, s["accent"], cx, ey)
    if slide.get("body"):
        _draw_text(draw, slide["body"], fb, s["secondary"], mw, cx, ey, gap=gap_b)
    _handle(draw, s)


# ── Layout renderers ──────────────────────────────────────────────────────────

def _layout_hero(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Full-bleed photo, minimal overlay only on bottom 40%, large headline."""
    result = _overlay_bottom(img, s["overlay"], alpha_top=0, alpha_bot=185)
    draw = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    fh = _font(s["font_h"], s["size_h"] + 6)
    fs = _font("reg", 28)

    pad, cx, mw = 70, W // 2, W - 140
    # Position text in bottom 38%
    ty = int(H * 0.62)
    ey = _draw_text(draw, slide["headline"], fh, s["primary"], mw, cx, ty, gap=20)
    _accent_line(draw, s["accent"], cx, ey)
    _handle(draw, s)
    return result.convert("RGB")


def _layout_split(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Photo occupies top 55%, text area bottom 45% with heavy overlay."""
    result = _overlay_bottom(img, s["overlay"], alpha_top=30, alpha_bot=220)
    draw = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    split_y = int(H * 0.54)
    draw.rectangle([0, split_y, W, split_y + 2], fill=(*s["accent"], 120))

    fh = _font(s["font_h"], s["size_h"])
    fb = _font(s["font_b"], s["size_b"])
    _text_block(draw, slide, s, cx=W // 2, mw=W - 150, ty=split_y + 40, fh=fh, fb=fb)
    return result.convert("RGB")


def _layout_card(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Blurred full photo, floating card with headline + bullets."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=7))
    result = _overlay_bottom(blurred, s["overlay"], alpha_top=80, alpha_bot=160)
    draw = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    card_pad = 60
    card_x1, card_x2 = card_pad, W - card_pad
    card_y1, card_y2 = int(H * 0.28), int(H * 0.88)

    card_layer = Image.new("RGBA", result.size, (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_layer)
    card_draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y2],
        radius=24, fill=s["card_bg"],
    )
    result = Image.alpha_composite(result.convert("RGBA"), card_layer)
    draw = ImageDraw.Draw(result)

    fh = _font(s["font_h"], s["size_h"] - 10)
    fb = _font(s["font_b"], s["size_b"] - 2)
    _text_block(draw, slide, s, cx=W // 2, mw=card_x2 - card_x1 - 60,
                ty=card_y1 + 45, fh=fh, fb=fb, gap_h=14, gap_b=12)
    return result.convert("RGB")


def _layout_quote(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Heavy blur + overlay, oversized centered text — pattern interrupt."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=10))
    result = _overlay_bottom(blurred, s["overlay"], alpha_top=155, alpha_bot=220)
    draw = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    fh = _font(s["font_h"], s["size_h"] + 8)
    fb = _font(s["font_b"], s["size_b"])
    mw = W - 120
    lines_h = len(_wrap(slide["headline"], fh, mw)) * (s["size_h"] + 20)
    ty = (H - lines_h) // 2 - 40

    _text_block(draw, slide, s, cx=W // 2, mw=mw, ty=ty, fh=fh, fb=fb, gap_h=20, gap_b=10)
    return result.convert("RGB")


# ── Public API ────────────────────────────────────────────────────────────────

_LAYOUT_FN = {
    "hero":              _layout_hero,
    "split":             _layout_split,
    "card":              _layout_card,
    "quote":             _layout_quote,
    "pattern_interrupt": _layout_quote,  # alias
}


def compose_slide(
    slide: dict,
    bg_image: Path | None,
    style_name: Style,
    output_path: Path,
) -> Path:
    s = STYLES[style_name]
    layout = slide.get("layout", "hero")
    fn = _LAYOUT_FN.get(layout, _layout_hero)

    if bg_image and bg_image.exists():
        img = Image.open(bg_image).convert("RGB")
        if img.size != (W, H):
            img = img.resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg(s["overlay"])

    result = fn(img, slide, s)
    result.save(output_path, quality=93)
    log.info(f"  Slide {slide['index']:02d} [{layout}] → {output_path.name}")
    return output_path
