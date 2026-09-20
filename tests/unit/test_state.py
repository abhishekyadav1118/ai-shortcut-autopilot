"""Unit tests for state management, deduplication and title similarity."""

from pathlib import Path

from autopilot.models import PublishedItem
from autopilot.state import (
    already_published_today,
    has_source_url_been_used,
    is_title_too_similar,
    load_state,
    record_publication,
    save_state,
)


def test_state_load_save_and_already_published(tmp_path: Path):
    state_file = tmp_path / "published.json"

    # Empty initially
    assert load_state(state_file) == []
    assert already_published_today("2026-09-20", state_file) is False

    # Add publication item
    item = PublishedItem(
        date="2026-09-20",
        topic_id="test-topic-1",
        source_urls=["https://example.com/ai-tool-1"],
        title="10 Amazing AI Tools You Must Try Today",
        video_id="abc123xyz",
        mode="review",
        status="success",
    )
    record_publication(item, state_file)

    # Now verify state
    records = load_state(state_file)
    assert len(records) == 1
    assert records[0].title == "10 Amazing AI Tools You Must Try Today"
    assert already_published_today("2026-09-20", state_file) is True
    assert already_published_today("2026-09-21", state_file) is False
    assert has_source_url_been_used("https://example.com/ai-tool-1", state_file) is True
    assert has_source_url_been_used("https://example.com/other-tool", state_file) is False


def test_title_similarity_check(tmp_path: Path):
    state_file = tmp_path / "published.json"
    save_state(
        [
            PublishedItem(
                date="2026-09-18",
                topic_id="topic-1",
                title="Top 5 AI Code Editors Compared in 2025",
            ),
            PublishedItem(
                date="2026-09-19",
                topic_id="topic-2",
                title="Complete Beginner Guide to Local LLMs with Ollama",
            ),
        ],
        state_file,
    )

    # Test nearly identical title
    is_similar, ratio, match = is_title_too_similar(
        "Top 5 AI Code Editors Compared in 2025!", max_similarity=0.6, file_path=state_file
    )
    assert is_similar is True
    assert ratio > 0.8
    assert "Code Editors" in match

    # Test completely distinct title
    is_distinct, ratio, _ = is_title_too_similar(
        "How NASA Uses Generative AI for Satellite Mapping",
        max_similarity=0.6,
        file_path=state_file,
    )
    assert is_distinct is False
    assert ratio < 0.5
