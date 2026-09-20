"""Stock footage provider (Pexels) with graceful card/slide fallback."""

from typing import Any

import httpx

from autopilot.models import Scene
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.visuals.stock")


def fetch_pexels_video(
    query: str,
    api_key: str | None = None,
    min_duration: int = 5,
    max_duration: int = 30,
) -> dict[str, Any] | None:
    """
    Search Pexels API for a royalty-free stock video clip.
    Returns metadata dict if found, or None if api_key is missing or query fails.
    Never throws on missing API key; cleanly falls back to text cards/slides.
    """
    if not api_key:
        logger.debug("PEXELS_API_KEY is not configured. Falling back to generated text cards/slides.")
        return None

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": 5,
        "orientation": "landscape",
        "size": "medium",
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                logger.warning("Pexels API responded with status %d: %s", resp.status_code, resp.text)
                return None

            data = resp.json()
            videos = data.get("videos", [])
            for vid in videos:
                dur = vid.get("duration", 0)
                if min_duration <= dur <= max_duration:
                    files = vid.get("video_files", [])
                    # Prefer 1080p HD
                    hd_files = [f for f in files if f.get("width") == 1920 or f.get("height") == 1080]
                    target_file = hd_files[0] if hd_files else (files[0] if files else None)
                    if target_file:
                        return {
                            "video_id": vid.get("id"),
                            "url": target_file.get("link"),
                            "width": target_file.get("width"),
                            "height": target_file.get("height"),
                            "duration": dur,
                            "user_name": vid.get("user", {}).get("name", "Pexels Creator"),
                            "user_url": vid.get("user", {}).get("url", "https://pexels.com"),
                        }
    except Exception as e:
        logger.warning("Failed to fetch Pexels video clip for query '%s': %s", query, e)

    return None


def resolve_scene_visual_strategy(
    scene: Scene,
    pexels_api_key: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """
    Determine whether to render a stock video clip or text card/slide for a scene.
    If PEXELS_API_KEY is missing or scene.visual_type == 'card', returns ('card', None).
    """
    if scene.visual_type == "card" or not pexels_api_key:
        return "card", None

    # Try fetching stock video
    clip_info = fetch_pexels_video(scene.visual_query, api_key=pexels_api_key)
    if clip_info:
        return "stock", clip_info

    # Fallback to card if stock clip unavailable
    return "card", None
