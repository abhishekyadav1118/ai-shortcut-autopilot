"""Unit tests for visuals module and Pexels API fallback behavior."""

from autopilot.models import Scene
from autopilot.visuals.stock import fetch_pexels_video, resolve_scene_visual_strategy


def test_pexels_api_key_missing_falls_back_to_card_no_error():
    """When PEXELS_API_KEY is None or empty, fetch returns None without error."""
    # 1. Direct fetch with None/empty API key
    assert fetch_pexels_video("artificial intelligence", api_key=None) is None
    assert fetch_pexels_video("artificial intelligence", api_key="") is None

    # 2. Scene strategy resolution returns ('card', None)
    scene = Scene(
        id=1,
        narration="Test narration for intro scene.",
        visual_type="stock",
        visual_query="cyberpunk city",
        on_screen_text="Intro",
        bullets=[],
        source_ids=[1],
    )

    strategy, clip_data = resolve_scene_visual_strategy(scene, pexels_api_key=None)
    assert strategy == "card"
    assert clip_data is None


def test_card_visual_type_always_resolves_to_card():
    """Scenes explicitly marked as 'card' always use text cards regardless of key."""
    scene = Scene(
        id=2,
        narration="Summary comparison slide.",
        visual_type="card",
        visual_query="data charts",
        on_screen_text="Comparison",
        bullets=["Point A", "Point B"],
        source_ids=[1],
    )

    strategy, clip_data = resolve_scene_visual_strategy(scene, pexels_api_key="fake_key")
    assert strategy == "card"
    assert clip_data is None


def test_pexels_api_success_mocked(monkeypatch):
    """When Pexels returns valid video clips, resolve strategy returns 'stock' with clip metadata."""
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "videos": [
                    {
                        "id": 12345,
                        "duration": 12,
                        "video_files": [
                            {"width": 1920, "height": 1080, "link": "https://example.com/video.mp4"}
                        ],
                        "user": {"name": "Video Creator", "url": "https://pexels.com/@creator"},
                    }
                ]
            }

    import httpx

    monkeypatch.setattr(httpx.Client, "get", lambda self, url, headers, params: MockResponse())

    scene = Scene(
        id=3,
        narration="Test stock query scene.",
        visual_type="stock",
        visual_query="futuristic robot coding",
        on_screen_text="AI Assistant",
        bullets=[],
        source_ids=[1],
    )

    strategy, clip_data = resolve_scene_visual_strategy(scene, pexels_api_key="valid_test_key")
    assert strategy == "stock"
    assert clip_data is not None
    assert clip_data["video_id"] == 12345
    assert clip_data["url"] == "https://example.com/video.mp4"
