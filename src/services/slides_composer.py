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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

log = logging.getLogger(__name__)

W, H = 1080, 1350
CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@tucanal")

_ASSETS = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

Layout = Literal["hero", "split", "card", "quote"]
Style  = Literal["terracota", "botanico", "aesthetic", "dark_jungle"]

_FONT_FILES = {
    "playfair":   _ASSETS / "PlayfairDisplay.ttf",
    "montserrat": _ASSETS / "Montserrat.ttf",
}

_FONT_ROLES: dict[str, tuple[str, int]] = {
    "bold":   ("playfair",   700),
    "reg":    ("montserrat", 400),
    "light":  ("montserrat", 300),
    "lightb": ("montserrat", 600),
}

_FALLBACKS: dict[str, list[str]] = {
    "bold":   ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/georgia.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
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
        raise ValueError(f"Unknown font key '{key}'")
    file_key, weight = _FONT_ROLES[key]
    paths = [str(_FONT_FILES[file_key])] + _FALLBACKS[key]
    for path in paths:
        try:
            f = ImageFont.truetype(path, size)
            try:
                f.set_variation_by_axes([weight])
            except (AttributeError, OSError):
                pass
            return f
        except OSError:
            continue
    return ImageFont.load_default()


# ── Style definitions ─────────────────────────────────────────────────────────

STYLES: dict[str, dict] = {
    "terracota": {
        "overlay":    (62, 18, 5),
        "overlay2":   (110, 40, 12),      # second gradient stop — warm burnt sienna
        "accent":     (235, 148, 62),
        "accent2":    (200, 90, 35),      # deeper terracotta for shadows
        "primary":    (255, 250, 232),
        "secondary":  (225, 192, 152),
        "bloom_color":(180, 80, 30),      # radial bloom tint
        "font_h": "bold",   "size_h": 86,
        "font_b": "reg",    "size_b": 40,
        "dots":    (235, 148, 62),
        "card_bg": (42, 10, 2, 220),
        "photo_tint": 0.22,
    },
    "botanico": {
        "overlay":    (5, 24, 10),
        "overlay2":   (12, 48, 22),       # richer forest mid-tone
        "accent":     (210, 178, 52),
        "accent2":    (150, 115, 28),
        "primary":    (252, 248, 224),
        "secondary":  (152, 220, 142),
        "bloom_color":(30, 80, 40),
        "font_h": "bold",   "size_h": 84,
        "font_b": "reg",    "size_b": 40,
        "dots":    (210, 178, 52),
        "card_bg": (3, 15, 6, 220),
        "photo_tint": 0.20,
    },
    "aesthetic": {
        "overlay":    (48, 24, 58),
        "overlay2":   (72, 38, 88),
        "accent":     (236, 178, 218),
        "accent2":    (180, 120, 165),
        "primary":    (255, 250, 255),
        "secondary":  (198, 222, 196),
        "bloom_color":(120, 60, 140),
        "font_h": "lightb", "size_h": 80,
        "font_b": "light",  "size_b": 38,
        "dots":    (236, 178, 218),
        "card_bg": (35, 15, 45, 220),
        "photo_tint": 0.24,
    },
    "dark_jungle": {
        "overlay":    (2, 8, 4),
        "overlay2":   (5, 20, 10),
        "accent":     (72, 230, 115),
        "accent2":    (30, 140, 65),
        "primary":    (255, 255, 255),
        "secondary":  (148, 238, 175),
        "bloom_color":(10, 60, 25),
        "font_h": "bold",   "size_h": 88,
        "font_b": "reg",    "size_b": 40,
        "dots":    (72, 230, 115),
        "card_bg": (1, 5, 2, 222),
        "photo_tint": 0.18,
        "glow": True,
    },
}


# ── Background generators ──────────────────────────────────────────────────────

def _make_radial_bloom(width: int, height: int,
                       cx: float, cy: float, radius: int,
                       color: tuple, max_alpha: int = 60) -> np.ndarray:
    """Fast numpy radial gradient bloom — no loops."""
    ys = np.arange(height, dtype=np.float32)[:, np.newaxis]
    xs = np.arange(width,  dtype=np.float32)[np.newaxis, :]
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    mask = np.clip(1.0 - dist / radius, 0, 1) ** 1.8
    alpha = (mask * max_alpha).astype(np.uint8)
    layer = np.zeros((height, width, 4), dtype=np.uint8)
    layer[:, :, 0] = color[0]
    layer[:, :, 1] = color[1]
    layer[:, :, 2] = color[2]
    layer[:, :, 3] = alpha
    return layer


def _gradient_bg(style: dict) -> Image.Image:
    """
    Rich editorial gradient background with:
    - Diagonal multi-stop gradient in style colors
    - Accent color blooms (radial glows in corners)
    - Subtle horizontal color band
    - Dramatic vignette
    - Film noise
    """
    c1 = style["overlay"]
    c2 = style["overlay2"]
    ac = style["bloom_color"]

    # ── Base diagonal gradient (numpy, fast) ─────────────────────────────────
    ys = np.linspace(0, 1, H, dtype=np.float32)[:, np.newaxis]
    xs = np.linspace(0, 1, W, dtype=np.float32)[np.newaxis, :]
    t  = np.clip(ys * 0.65 + xs * 0.35, 0, 1) ** 0.85

    R = np.clip(c1[0] + (c2[0] - c1[0]) * t, 0, 255).astype(np.uint8)
    G = np.clip(c1[1] + (c2[1] - c1[1]) * t, 0, 255).astype(np.uint8)
    B = np.clip(c1[2] + (c2[2] - c1[2]) * t, 0, 255).astype(np.uint8)
    base = Image.fromarray(np.stack([R, G, B], axis=2), "RGB").convert("RGBA")

    # ── Accent bloom — top-right ──────────────────────────────────────────────
    b1 = _make_radial_bloom(W, H, W * 0.78, H * 0.20, 460, ac, max_alpha=55)
    base = Image.alpha_composite(base, Image.fromarray(b1, "RGBA"))

    # ── Second bloom — bottom-left ────────────────────────────────────────────
    b2 = _make_radial_bloom(W, H, W * 0.18, H * 0.82, 340, ac, max_alpha=38)
    base = Image.alpha_composite(base, Image.fromarray(b2, "RGBA"))

    # ── Warm horizontal mid-band (adds depth) ────────────────────────────────
    band = np.zeros((H, W, 4), dtype=np.uint8)
    ys2  = np.linspace(0, 1, H, dtype=np.float32)
    band_a = (np.sin(np.clip(ys2, 0, 1) * np.pi) * 22).astype(np.uint8)
    band[:, :, 0] = min(255, ac[0] + 20)
    band[:, :, 1] = min(255, ac[1] + 15)
    band[:, :, 2] = min(255, ac[2] + 10)
    band[:, :, 3] = band_a[:, np.newaxis]
    base = Image.alpha_composite(base, Image.fromarray(band, "RGBA"))

    # ── Dramatic vignette (numpy) ─────────────────────────────────────────────
    ys3 = np.linspace(-1, 1, H, dtype=np.float32)[:, np.newaxis]
    xs3 = np.linspace(-1, 1, W, dtype=np.float32)[np.newaxis, :]
    vig = np.clip((xs3 ** 2 * 0.6 + ys3 ** 2 * 0.9) ** 1.2, 0, 1)
    vig_alpha = (vig * 185).astype(np.uint8)
    vignette = np.zeros((H, W, 4), dtype=np.uint8)
    vignette[:, :, 3] = vig_alpha
    base = Image.alpha_composite(base, Image.fromarray(vignette, "RGBA"))

    base = base.convert("RGB")

    # ── Film noise ────────────────────────────────────────────────────────────
    arr   = np.array(base, dtype=np.int16)
    noise = np.random.randint(-8, 9, arr.shape, dtype=np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")


def _prep_photo(img: Image.Image, style: dict) -> Image.Image:
    """
    Color-grade background photo to match the style palette.
    - Smart crop keeps plant subjects upper-center
    - Subtle style tint for visual cohesion
    - Contrast + saturation boost for punch
    - Soft unsharp mask for crispness
    """
    if img.size != (W, H):
        img = ImageOps.fit(img, (W, H), Image.LANCZOS, centering=(0.5, 0.28))

    # Subtle color tint — blends the style palette into the photo
    tint = Image.new("RGB", img.size, style["overlay2"])
    img  = Image.blend(img, tint, alpha=style["photo_tint"])

    # Contrast boost
    img = ImageEnhance.Contrast(img).enhance(1.12)

    # Sharpening for print-quality crispness
    img = img.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=3))

    return img


# ── Overlay helpers ────────────────────────────────────────────────────────────

def _overlay_bottom(base: Image.Image, color: tuple, alpha_top: int, alpha_bot: int) -> Image.Image:
    ov   = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    r, g, b = color
    for y in range(H):
        t = y / H
        a = int(alpha_top + (alpha_bot - alpha_top) * (t ** 0.6))
        draw.line([(0, y), (W, y)], fill=(r, g, b, a))
    return Image.alpha_composite(base.convert("RGBA"), ov)


def _grain_overlay(img: Image.Image, intensity: int = 12) -> Image.Image:
    arr   = np.array(img.convert("RGB"), dtype=np.int16)
    grain = np.random.normal(0, intensity, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + grain, 0, 255).astype(np.uint8), "RGB")


# ── Typography helpers ─────────────────────────────────────────────────────────

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
        r"[\U00010000-\U0010ffff\U0001F300-\U0001F9FF☀-➿︀-️‍]+",
        "", text,
    ).strip()


def _draw_text(
    draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
    color: tuple, max_w: int, cx: int, y: int, gap: int = 16,
    shadow_strength: int = 110,
) -> int:
    """Draw centered text with a multi-layer shadow for depth."""
    text = _strip_emoji(text)
    for line in _wrap(text, font, max_w):
        if not line:
            y += gap
            continue
        bb = draw.textbbox((0, 0), line, font=font)
        lw, lh = bb[2] - bb[0], bb[3] - bb[1]
        x = cx - lw // 2
        # Multi-layer shadow: far soft + near hard
        draw.text((x + 5, y + 5), line, font=font, fill=(0, 0, 0, shadow_strength - 40))
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, shadow_strength))
        draw.text((x, y), line, font=font, fill=color)
        y += lh + gap
    return y


def _accent_line(draw: ImageDraw.Draw, color: tuple, cx: int, y: int, w: int = 72) -> int:
    """Thin editorial accent separator."""
    draw.rectangle([cx - w // 2, y + 14, cx + w // 2, y + 16], fill=color)
    return y + 36


def _glow_accent_line(base: Image.Image, color: tuple, cx: int, y: int, w: int = 72) -> tuple[Image.Image, int]:
    """Accent line with a soft glow — for dark_jungle style."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d     = ImageDraw.Draw(layer)
    # Glow halo
    for thickness in range(8, 1, -1):
        alpha = int(40 * (thickness / 8) ** 2)
        d.rectangle([cx - w // 2 - thickness, y + 14 - thickness,
                     cx + w // 2 + thickness, y + 16 + thickness],
                    fill=(*color, alpha))
    # Core line
    d.rectangle([cx - w // 2, y + 14, cx + w // 2, y + 16], fill=(*color, 255))
    result = Image.alpha_composite(base.convert("RGBA"), layer)
    return result.convert("RGB"), y + 36


def _progress_dots(draw: ImageDraw.Draw, style: dict, current: int, total: int = 10):
    r, sp = 4, 18
    tw    = (total - 1) * sp
    sx    = (W - tw) // 2
    y     = 56
    for i in range(total):
        x = sx + i * sp
        if i == current:
            draw.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=style["dots"])
        else:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 45))


def _handle(draw: ImageDraw.Draw, style: dict):
    f = _font("light", 25)
    draw.text((W - 68, H - 44), CHANNEL_HANDLE, font=f,
              fill=(*style["accent"][:3], 160), anchor="rm")


def _page_number(draw: ImageDraw.Draw, current: int, total: int, s: dict):
    f = _font("light", 24)
    draw.text((62, H - 44), f"{current + 1:02d} / {total:02d}", font=f,
              fill=(*s["accent"][:3], 145))


def _text_block(
    draw: ImageDraw.Draw, base_img: Image.Image,
    slide: dict, s: dict,
    cx: int, mw: int, ty: int,
    fh: ImageFont.FreeTypeFont, fb: ImageFont.FreeTypeFont,
    gap_h: int = 18, gap_b: int = 13,
) -> Image.Image:
    """Headline → accent line → body → handle. Returns updated image (glow line may modify it)."""
    ey = _draw_text(draw, slide["headline"], fh, s["primary"], mw, cx, ty, gap=gap_h)
    ey += 4

    # Use glow accent for dark styles (flagged with "glow": True), plain for others
    if s.get("glow"):
        base_img = base_img.convert("RGB")
        base_img, ey = _glow_accent_line(base_img, s["accent"], cx, ey)
        draw = ImageDraw.Draw(base_img)
    else:
        ey = _accent_line(draw, s["accent"], cx, ey)

    if slide.get("body"):
        _draw_text(draw, slide["body"], fb, s["secondary"], mw, cx, ey, gap=gap_b)
    _handle(draw, s)
    return base_img


# ── Layout renderers ──────────────────────────────────────────────────────────

def _layout_hero(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Full-bleed, minimal overlay on bottom 45%, dramatic large headline."""
    result = _overlay_bottom(img, s["overlay"], alpha_top=0, alpha_bot=205)
    draw   = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    fh  = _font(s["font_h"], s["size_h"] + 10)
    cx, mw = W // 2, W - 140
    ty  = int(H * 0.58)
    ey  = _draw_text(draw, slide["headline"], fh, s["primary"], mw, cx, ty, gap=24)
    ey += 4
    _accent_line(draw, s["accent"], cx, ey)
    _handle(draw, s)
    return result.convert("RGB")


def _layout_split(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Photo top 52%, bold text area bottom 48%."""
    result = _overlay_bottom(img, s["overlay"], alpha_top=18, alpha_bot=235)
    draw   = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    split_y = int(H * 0.52)
    draw.rectangle([0, split_y, W, split_y + 2], fill=(*s["accent"][:3], 150))

    fh  = _font(s["font_h"], s["size_h"])
    fb  = _font(s["font_b"], s["size_b"])
    result = _text_block(draw, result, slide, s, cx=W // 2, mw=W - 160,
                         ty=split_y + 46, fh=fh, fb=fb)
    return result.convert("RGB")


def _layout_card(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Blurred photo + frosted floating card with border glow."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=9))
    result  = _overlay_bottom(blurred, s["overlay"], alpha_top=85, alpha_bot=175)
    draw    = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    pad = 52
    cx1, cx2 = pad, W - pad
    cy1, cy2 = int(H * 0.26), int(H * 0.88)

    card = Image.new("RGBA", result.size, (0, 0, 0, 0))
    cd   = ImageDraw.Draw(card)
    # Card fill
    cd.rounded_rectangle([cx1, cy1, cx2, cy2], radius=30, fill=s["card_bg"])
    # Card border
    cd.rounded_rectangle([cx1, cy1, cx2, cy2], radius=30,
                          outline=(*s["accent"][:3], 60), width=1)
    # Subtle inner glow at top of card
    cd.rounded_rectangle([cx1+1, cy1+1, cx2-1, cy1+80], radius=28,
                          fill=(*s["accent"][:3], 18))
    result = Image.alpha_composite(result.convert("RGBA"), card)
    draw   = ImageDraw.Draw(result)

    fh = _font(s["font_h"], s["size_h"] - 6)
    fb = _font(s["font_b"], s["size_b"])
    result = _text_block(draw, result, slide, s, cx=W // 2, mw=cx2 - cx1 - 60,
                         ty=cy1 + 52, fh=fh, fb=fb, gap_h=16, gap_b=13)
    return result.convert("RGB")


def _layout_quote(img: Image.Image, slide: dict, s: dict) -> Image.Image:
    """Heavy blur + oversized centered text — pure typographic power."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=14))
    result  = _overlay_bottom(blurred, s["overlay"], alpha_top=170, alpha_bot=238)
    draw    = ImageDraw.Draw(result)
    _progress_dots(draw, s, slide["index"])

    # Large decorative quote mark (very faint — editorial texture)
    fq  = _font("bold", 220)
    bb  = draw.textbbox((0, 0), "“", font=fq)
    qx  = W // 2 - (bb[2] - bb[0]) // 2
    draw.text((qx, int(H * 0.06)), "“", font=fq,
              fill=(*s["accent"][:3], 35))

    fh  = _font(s["font_h"], s["size_h"] + 12)
    fb  = _font(s["font_b"], s["size_b"])
    mw  = W - 110
    lines_h = len(_wrap(slide["headline"], fh, mw)) * (s["size_h"] + 26)
    ty  = max(int(H * 0.28), (H - lines_h) // 2 - 70)
    result = _text_block(draw, result, slide, s, cx=W // 2, mw=mw,
                         ty=ty, fh=fh, fb=fb, gap_h=22, gap_b=13)
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
        raw = Image.open(bg_image).convert("RGB")
        img = _prep_photo(raw, s)
    else:
        img = _gradient_bg(s)

    result = fn(img, slide, s)

    # Editorial page counter
    draw = ImageDraw.Draw(result)
    _page_number(draw, slide.get("index", 0), total_slides, s)

    # Film grain — analog editorial texture
    result = _grain_overlay(result.convert("RGB"), intensity=12)

    result.save(output_path, quality=95)
    log.info(f"  Slide {slide['index']:02d} [{layout}] -> {output_path.name}")
    return output_path
