"""Topics collection, filtering, and ranking exports."""

from autopilot.topics.fetch_text import fetch_article_text
from autopilot.topics.ranker import get_evergreen_fallback, select_topic
from autopilot.topics.sources import collect_all_candidates

__all__ = [
    "collect_all_candidates",
    "fetch_article_text",
    "select_topic",
    "get_evergreen_fallback",
]
