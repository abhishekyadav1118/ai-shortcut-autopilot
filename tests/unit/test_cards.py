"""Unit tests for render/cards.py."""

from pathlib import Path


def test_render_text_card_creates_png(tmp_path):
    """render_text_card produces a non-empty PNG at the expected path."""
    from autopilot.render.cards import render_text_card

    out = tmp_path / "card_001.png"
    result = render_text_card(
        title="AI Tools Explained",
        bullets=["Fast", "Accurate", "Free"],
        out_path=out,
        scene_id=1,
    )
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 10_000  # must be a real image, not empty


def test_render_text_card_correct_dimensions(tmp_path):
    """Output PNG must be exactly 1920x1080."""
    from PIL import Image

    from autopilot.render.cards import CARD_H, CARD_W, render_text_card

    out = tmp_path / "card_dim.png"
    render_text_card("Dimensions Test", ["Bullet"], out_path=out, scene_id=2)

    img = Image.open(out)
    assert img.size == (CARD_W, CARD_H)
    assert img.mode == "RGB"


def test_render_text_card_long_title_wraps(tmp_path):
    """Long titles don't raise — they wrap within the card."""
    from autopilot.render.cards import render_text_card

    long_title = "This Is a Very Long Title That Should Be Wrapped Properly Without Crashing"
    out = tmp_path / "card_long.png"
    render_text_card(long_title, bullets=[], out_path=out, scene_id=3)
    assert out.exists()


def test_render_text_card_no_bullets(tmp_path):
    """Cards with zero bullets render without error."""
    from autopilot.render.cards import render_text_card

    out = tmp_path / "card_nobullets.png"
    render_text_card("Just A Title", bullets=[], out_path=out, scene_id=4)
    assert out.stat().st_size > 5_000


def test_render_all_cards_returns_video_paths(tmp_path):
    """render_all_cards populates video_path for every scene."""
    from autopilot.render.cards import render_all_cards

    scenes = [
        {"id": 1, "visual_type": "card", "on_screen_text": "Scene One", "bullets": ["A", "B"]},
        {"id": 2, "visual_type": "stock", "on_screen_text": "Scene Two", "bullets": []},
    ]
    result = render_all_cards(scenes, tmp_path / "cards")

    assert len(result) == 2
    for s in result:
        assert "video_path" in s
        assert Path(s["video_path"]).exists()
        assert s["video_path"].endswith(".png")
