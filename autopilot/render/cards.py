"""Pillow-based text card generator — 1920×1080 slide per scene."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.render.cards")

# ── Design tokens ────────────────────────────────────────────────────────────
CARD_W, CARD_H = 1920, 1080

# Dark gradient palette (top → bottom): deep navy to dark slate
BG_TOP = (10, 12, 30)
BG_BOTTOM = (18, 22, 48)

ACCENT = (99, 179, 237)        # soft electric blue
TITLE_COLOR = (240, 245, 255)  # near-white
BULLET_COLOR = (180, 200, 230) # muted blue-white
LINE_COLOR = (99, 179, 237)    # accent underline

# Font sizes
TITLE_SIZE = 72
BULLET_SIZE = 44

# Where to look for fonts (shipped fonts take priority, system fallback)
_FONT_CANDIDATES = [
    "assets/fonts/Inter-Bold.ttf",
    "assets/fonts/Roboto-Bold.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_FONT_CAND_REGULAR = [
    "assets/fonts/Inter-Regular.ttf",
    "assets/fonts/Roboto-Regular.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    logger.warning("No TrueType font found; using Pillow default bitmap font.")
    return ImageFont.load_default()


def _vertical_gradient(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    """Draw a smooth vertical linear gradient background."""
    for y in range(height):
        t = y / height
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def render_text_card(
    title: str,
    bullets: list[str],
    out_path: Path | str,
    scene_id: int = 0,
    channel_name: str = "The AI Shortcut",
) -> Path:
    """
    Render one 1920×1080 PNG text card.

    Layout:
      • Full-bleed dark gradient background
      • Top-right: channel watermark
      • Centred bold title (wrapped at 32 chars)
      • Accent underline below title
      • Up to 4 bullet points below
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (CARD_W, CARD_H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # Background gradient
    _vertical_gradient(draw, CARD_W, CARD_H)

    # Subtle corner accent glow
    for radius, alpha in [(300, 8), (200, 12), (120, 18)]:
        draw.ellipse(
            [CARD_W - radius, -radius // 2, CARD_W + radius // 2, radius],
            fill=(*ACCENT, alpha),
        )

    # Fonts
    font_title = _load_font(_FONT_CANDIDATES, TITLE_SIZE)
    font_bullet = _load_font(_FONT_CAND_REGULAR, BULLET_SIZE)
    font_watermark = _load_font(_FONT_CAND_REGULAR, 30)

    # Channel watermark (top-right)
    wm_text = channel_name
    wm_bbox = draw.textbbox((0, 0), wm_text, font=font_watermark)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text((CARD_W - wm_w - 48, 36), wm_text, font=font_watermark, fill=(*ACCENT, 180))

    # Title — wrap and centre
    wrapped = "\n".join(textwrap.wrap(title, width=32))
    title_bbox = draw.multiline_textbbox((0, 0), wrapped, font=font_title, spacing=16)
    title_h = title_bbox[3] - title_bbox[1]

    # Vertical centering: title + gap + accent bar + gap + bullets
    n_bullets = min(len(bullets), 4)
    block_h = title_h + 20 + 6 + 24 + n_bullets * (BULLET_SIZE + 18)
    start_y = max(120, (CARD_H - block_h) // 2)

    draw.multiline_text(
        (CARD_W // 2, start_y),
        wrapped,
        font=font_title,
        fill=TITLE_COLOR,
        anchor="ma",
        align="center",
        spacing=16,
    )

    # Accent underline
    bar_y = start_y + title_h + 20
    bar_x0 = CARD_W // 2 - 120
    bar_x1 = CARD_W // 2 + 120
    draw.rectangle([bar_x0, bar_y, bar_x1, bar_y + 5], fill=ACCENT)

    # Bullets
    bul_y = bar_y + 30
    for bullet in bullets[:4]:
        dot_x = CARD_W // 2 - 380
        draw.ellipse([dot_x, bul_y + 14, dot_x + 14, bul_y + 28], fill=ACCENT)
        draw.text((dot_x + 28, bul_y), bullet, font=font_bullet, fill=BULLET_COLOR)
        bul_y += BULLET_SIZE + 18

    img.save(out_path, format="PNG", optimize=False)
    logger.debug("Rendered card scene %d → %s", scene_id, out_path.name)
    return out_path


def render_all_cards(
    scenes: list[dict],
    out_dir: Path | str,
    channel_name: str = "The AI Shortcut",
) -> list[dict]:
    """
    Render a PNG card for every scene with visual_type == 'card'.
    Scenes with visual_type == 'stock' also get a card (Pexels fallback).
    Returns scenes list with video_path populated for card scenes.
    """
    out_dir = Path(out_dir)
    result = []
    for s in scenes:
        s = dict(s)
        png = out_dir / f"card_{s['id']:03d}.png"
        render_text_card(
            title=s.get("on_screen_text", s.get("visual_query", "AI Shortcut")),
            bullets=s.get("bullets", []),
            out_path=png,
            scene_id=s["id"],
            channel_name=channel_name,
        )
        s["video_path"] = str(png)
        result.append(s)

    logger.info("Rendered %d text cards in %s", len(result), out_dir)
    return result


THUMB_W, THUMB_H = 1280, 720


def generate_thumbnail(
    title: str,
    out_path: Path | str,
    bg_image_path: Path | str | None = None,
    channel_name: str = "THE AI SHORTCUT",
) -> Path:
    """Generate a 1280x720 video thumbnail with title text, strictly under 2 MB."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if bg_image_path and Path(bg_image_path).exists():
        bg = Image.open(bg_image_path).convert("RGBA")
        bg = bg.resize((THUMB_W, THUMB_H), Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (10, 12, 30, 180))
        img = Image.alpha_composite(bg, overlay).convert("RGB")
    else:
        img = Image.new("RGB", (THUMB_W, THUMB_H))
        draw_temp = ImageDraw.Draw(img)
        for y in range(THUMB_H):
            r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * y / THUMB_H)
            g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * y / THUMB_H)
            b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * y / THUMB_H)
            draw_temp.line([(0, y), (THUMB_W, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(img)
    font_title = _load_font(_FONT_CANDIDATES, 54)
    font_badge = _load_font(_FONT_CAND_REGULAR, 26)

    # Top pill badge
    badge_text = channel_name.upper()
    badge_bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_w = badge_bbox[2] - badge_bbox[0]
    badge_x0 = (THUMB_W - badge_w) // 2 - 20
    badge_x1 = (THUMB_W + badge_w) // 2 + 20
    draw.rounded_rectangle([badge_x0, 80, badge_x1, 125], radius=8, fill=ACCENT)
    draw.text((THUMB_W // 2, 85), badge_text, font=font_badge, fill=(10, 12, 30), anchor="ma")

    # Title text
    wrapped = textwrap.fill(title, width=28)
    lines = wrapped.splitlines()
    line_h = 64
    total_h = len(lines) * line_h
    start_y = (THUMB_H - total_h) // 2 + 30

    draw.multiline_text(
        (THUMB_W // 2, start_y),
        wrapped,
        font=font_title,
        fill=TITLE_COLOR,
        anchor="ma",
        align="center",
        spacing=16,
    )

    img.save(out_path, format="PNG", optimize=True)
    if out_path.stat().st_size > 2 * 1024 * 1024:
        jpg_path = out_path.with_suffix(".jpg")
        img.save(jpg_path, format="JPEG", quality=85)
        out_path = jpg_path

    logger.info("Generated 1280x720 thumbnail (%.2f MB) -> %s", out_path.stat().st_size / 1024 / 1024, out_path)
    return out_path

