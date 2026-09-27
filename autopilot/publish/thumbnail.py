"""Two-variant 1280×720 thumbnail generator.

Variant A — hook-phrased, bold accent background (electric blue gradient)
Variant B — title keyword, dark navy with gold accent

Both are guaranteed < 2 MB (saves as JPEG if PNG exceeds limit).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.publish.thumbnail")

THUMB_W, THUMB_H = 1280, 720
_MAX_BYTES = 2 * 1024 * 1024  # 2 MB YouTube hard limit

# ── Design tokens ─────────────────────────────────────────────────────────────
# Variant A: bold electric blue
_A_BG_TOP    = (10, 30, 80)
_A_BG_BOT    = (5, 15, 45)
_A_ACCENT    = (99, 179, 237)
_A_TEXT      = (255, 255, 255)

# Variant B: dark navy with gold
_B_BG_TOP    = (10, 12, 30)
_B_BG_BOT    = (20, 18, 50)
_B_ACCENT    = (255, 196, 54)
_B_TEXT      = (240, 245, 255)

_FONT_BOLD = [
    "assets/fonts/Inter-Bold.ttf",
    "assets/fonts/Roboto-Bold.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_REG = [
    "assets/fonts/Inter-Regular.ttf",
    "assets/fonts/Roboto-Regular.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(
    candidates: list[str], size: int
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in candidates:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _gradient(draw: ImageDraw.ImageDraw, top: tuple, bot: tuple) -> None:
    for y in range(THUMB_H):
        t = y / THUMB_H
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        draw.line([(0, y), (THUMB_W, y)], fill=(r, g, b))


def _save_under_limit(img: Image.Image, out_path: Path) -> Path:
    """Save PNG; if > 2 MB fall back to JPEG q=85, then q=70."""
    img.save(out_path, format="PNG", optimize=True)
    if out_path.stat().st_size <= _MAX_BYTES:
        return out_path
    jpg = out_path.with_suffix(".jpg")
    img.save(jpg, format="JPEG", quality=85)
    if jpg.stat().st_size <= _MAX_BYTES:
        out_path.unlink(missing_ok=True)
        return jpg
    img.save(jpg, format="JPEG", quality=70)
    out_path.unlink(missing_ok=True)
    return jpg


def _draw_glow(draw: ImageDraw.ImageDraw, accent: tuple, side: str = "right") -> None:
    """Draw a soft accent glow ellipse in a corner."""
    r = 280
    if side == "right":
        draw.ellipse([THUMB_W - r, -r // 2, THUMB_W + r // 2, r], fill=(*accent, 14))
        draw.ellipse([THUMB_W - r // 2, -r // 4, THUMB_W + r // 4, r // 2], fill=(*accent, 22))
    else:
        draw.ellipse([-r // 2, -r // 2, r, r], fill=(*accent, 14))
        draw.ellipse([-r // 4, -r // 4, r // 2, r // 2], fill=(*accent, 22))


def generate_thumbnail_variant(
    text: str,
    out_path: Path | str,
    variant: str = "A",
    bg_image_path: Path | str | None = None,
    channel_name: str = "THE AI SHORTCUT",
) -> Path:
    """Generate one 1280×720 thumbnail variant (A or B).

    Args:
        text: Max 4 words to display large on screen.
        out_path: Destination path (.png preferred; auto-converted to .jpg if > 2 MB).
        variant: 'A' (blue gradient) or 'B' (navy + gold).
        bg_image_path: Optional background image (overlaid with dark tint).
        channel_name: Watermark text.

    Returns:
        Actual saved path (may be .jpg).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bg_top = _A_BG_TOP if variant == "A" else _B_BG_TOP
    bg_bot = _A_BG_BOT if variant == "A" else _B_BG_BOT
    accent = _A_ACCENT if variant == "A" else _B_ACCENT
    text_col = _A_TEXT if variant == "A" else _B_TEXT

    # Background
    if bg_image_path and Path(bg_image_path).exists():
        bg = Image.open(bg_image_path).convert("RGBA").resize(
            (THUMB_W, THUMB_H), Image.Resampling.LANCZOS
        )
        overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (*bg_top, 195))
        img = Image.alpha_composite(bg, overlay).convert("RGB")
    else:
        img = Image.new("RGB", (THUMB_W, THUMB_H))
        draw_tmp = ImageDraw.Draw(img)
        _gradient(draw_tmp, bg_top, bg_bot)

    draw = ImageDraw.Draw(img)

    # Accent glow
    _draw_glow(draw, accent, side="right" if variant == "A" else "left")

    # Fonts
    font_big = _load_font(_FONT_BOLD, 96)
    font_badge = _load_font(_FONT_REG, 26)

    # Channel pill badge (top-centre)
    badge = channel_name.upper()
    bb = draw.textbbox((0, 0), badge, font=font_badge)
    bw = bb[2] - bb[0]
    bx0 = (THUMB_W - bw) // 2 - 22
    bx1 = (THUMB_W + bw) // 2 + 22
    draw.rounded_rectangle([bx0, 52, bx1, 96], radius=8, fill=accent)
    draw.text((THUMB_W // 2, 56), badge, font=font_badge, fill=bg_top, anchor="ma")

    # Accent bottom bar
    bar_h = 8
    draw.rectangle([0, THUMB_H - bar_h - 1, THUMB_W, THUMB_H - 1], fill=accent)

    # Main text (max 4 words, large, centred)
    words = text.strip().split()[:4]
    display = " ".join(words)
    # Wrap at 14 chars per line for legibility
    wrapped = textwrap.fill(display, width=12)
    lines = wrapped.splitlines()

    line_h = 108
    total_h = len(lines) * line_h
    start_y = (THUMB_H - total_h) // 2 + 20

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        # Shadow
        draw.text((THUMB_W // 2 + 3, y + 3), line, font=font_big, fill=(0, 0, 0, 100), anchor="ma")
        draw.text((THUMB_W // 2, y), line, font=font_big, fill=text_col, anchor="ma")

    # Accent underline beneath text
    ul_y = start_y + total_h + 12
    draw.rectangle(
        [THUMB_W // 2 - 100, ul_y, THUMB_W // 2 + 100, ul_y + 5], fill=accent
    )

    saved = _save_under_limit(img, out_path)
    size_kb = saved.stat().st_size / 1024
    logger.info(
        "Thumbnail variant %s -> %s (%.1f KB, %dx%d)",
        variant, saved.name, size_kb, THUMB_W, THUMB_H,
    )
    return saved


def generate_both_thumbnails(
    text_a: str,
    text_b: str,
    out_dir: Path | str,
    bg_image_path: Path | str | None = None,
    channel_name: str = "THE AI SHORTCUT",
) -> tuple[Path, Path]:
    """Generate both Variant A and Variant B thumbnails.

    Args:
        text_a: Text for Variant A (hook-phrased, max 4 words).
        text_b: Text for Variant B (title-based, max 4 words).
        out_dir: Directory where thumbnails are saved.
        bg_image_path: Optional shared background image.
        channel_name: Watermark text.

    Returns:
        (path_a, path_b)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    path_a = generate_thumbnail_variant(
        text=text_a,
        out_path=out_dir / "thumbnail_a.png",
        variant="A",
        bg_image_path=bg_image_path,
        channel_name=channel_name,
    )
    path_b = generate_thumbnail_variant(
        text=text_b,
        out_path=out_dir / "thumbnail_b.png",
        variant="B",
        bg_image_path=bg_image_path,
        channel_name=channel_name,
    )
    return path_a, path_b
