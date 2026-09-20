"""Unit tests for RSS and Hacker News candidate topic sources."""

from unittest.mock import MagicMock, patch

from autopilot.topics.sources import (
    fetch_hacker_news_candidates,
    fetch_rss_candidates,
)


def test_fetch_rss_candidates_mocked():
    mock_feed = MagicMock()
    mock_entry = MagicMock()
    mock_entry.title = "Anthropic Unveils Claude 3.7 Sonnet"
    mock_entry.link = "https://www.anthropic.com/news/claude-3-7"
    mock_entry.summary = "A major update with hybrid reasoning capabilities."
    mock_entry.published = "2026-09-19T12:00:00Z"
    mock_entry.published_parsed = (2026, 9, 19, 12, 0, 0, 4, 262, 0)
    mock_feed.entries = [mock_entry]

    with patch("feedparser.parse", return_value=mock_feed):
        candidates = fetch_rss_candidates("https://example.com/rss", "Anthropic News", max_age_hours=72)
        assert len(candidates) == 1
        assert candidates[0].title == "Anthropic Unveils Claude 3.7 Sonnet"
        assert candidates[0].source_name == "Anthropic News"


def test_fetch_hacker_news_candidates_mocked(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hits": [
            {
                "title": "Show HN: Open Source Local LLM Runner",
                "url": "https://github.com/example/runner",
                "points": 150,
                "num_comments": 42,
                "created_at": "2026-09-19T10:00:00Z",
            }
        ]
    }

    with patch("httpx.Client.get", return_value=mock_response):
        candidates = fetch_hacker_news_candidates(min_points=30, max_age_hours=72)
        assert len(candidates) == 1
        assert "Local LLM" in candidates[0].title
        assert candidates[0].score == 150.0
