"""State management for published items, deduplication, and similarity checks."""

import difflib
import json
from datetime import UTC, datetime
from pathlib import Path

from autopilot.models import PublishedItem

STATE_FILE_PATH = Path("state/published.json")


def load_state(file_path: Path = STATE_FILE_PATH) -> list[PublishedItem]:
    """Load published records from JSON state file."""
    if not file_path.exists():
        return []

    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return [PublishedItem(**item) for item in data]
    except (json.JSONDecodeError, ValueError):
        return []


def save_state(items: list[PublishedItem], file_path: Path = STATE_FILE_PATH) -> None:
    """Save published records to JSON state file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([item.model_dump() for item in items], f, indent=2, ensure_ascii=False)


def already_published_today(
    target_date: str | None = None, file_path: Path = STATE_FILE_PATH
) -> bool:
    """Check if a successful publication has already been recorded for today (YYYY-MM-DD)."""
    if target_date is None:
        target_date = datetime.now(UTC).strftime("%Y-%m-%d")

    records = load_state(file_path)
    return any(item.date == target_date and item.status == "success" for item in records)


def get_past_titles(file_path: Path = STATE_FILE_PATH) -> list[str]:
    """Return all past published video titles."""
    records = load_state(file_path)
    return [item.title for item in records if item.title]


def is_title_too_similar(
    new_title: str, max_similarity: float = 0.6, file_path: Path = STATE_FILE_PATH
) -> tuple[bool, float, str]:
    """
    Check if new_title is too similar to any past published title.
    Returns (is_too_similar, highest_ratio, most_similar_title).
    """
    past_titles = get_past_titles(file_path)
    if not past_titles:
        return False, 0.0, ""

    normalized_new = new_title.strip().lower()
    highest_ratio = 0.0
    most_similar = ""

    for past in past_titles:
        normalized_past = past.strip().lower()
        ratio = difflib.SequenceMatcher(None, normalized_new, normalized_past).ratio()
        if ratio > highest_ratio:
            highest_ratio = ratio
            most_similar = past

    is_similar = highest_ratio >= max_similarity
    return is_similar, highest_ratio, most_similar


def has_source_url_been_used(url: str, file_path: Path = STATE_FILE_PATH) -> bool:
    """Check if a source URL has already been processed in any published record."""
    if not url:
        return False
    normalized_url = url.strip().rstrip("/")
    records = load_state(file_path)
    for item in records:
        for source in item.source_urls:
            if source.strip().rstrip("/") == normalized_url:
                return True
    return False


def record_publication(item: PublishedItem, file_path: Path = STATE_FILE_PATH) -> None:
    """Append a new publication record to state."""
    items = load_state(file_path)
    items.append(item)
    save_state(items, file_path)
