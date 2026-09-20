"""Collect candidate topics from RSS feeds and Hacker News."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import feedparser
import httpx
import yaml

from autopilot.models import Candidate
from autopilot.state import has_source_url_been_used, is_title_too_similar
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.topics.sources")


def load_feeds_config(path: Path | str = "config/feeds.yaml") -> dict[str, Any]:
    """Load feed definitions from YAML config."""
    p = Path(path)
    if not p.exists():
        return {"feeds": [], "hacker_news": {"enabled": False}}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch_rss_candidates(feed_url: str, source_name: str, max_age_hours: int = 72) -> list[Candidate]:
    """Fetch entries from a single RSS feed."""
    candidates: list[Candidate] = []
    cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

    try:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries:
            title = getattr(entry, "title", "").strip()
            link = getattr(entry, "link", "").strip()
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
            if not title or not link:
                continue

            # Check publication timestamp if available
            published_parsed = getattr(entry, "published_parsed", None) or getattr(
                entry, "updated_parsed", None
            )
            if published_parsed:
                entry_dt = datetime(*published_parsed[:6], tzinfo=UTC)
                if entry_dt < cutoff_time:
                    continue

            pub_val = getattr(entry, "published", "")
            pub_str = str(pub_val) if pub_val is not None else ""

            candidates.append(
                Candidate(
                    title=title,
                    url=link,
                    published=pub_str,
                    summary=summary[:300].strip(),
                    source_name=source_name,
                )
            )
    except Exception as e:
        logger.warning("Error fetching RSS feed %s (%s): %s", source_name, feed_url, e)

    return candidates


def fetch_hacker_news_candidates(
    query: str = "AI OR LLM OR GPT OR Claude OR Gemini OR open-source",
    min_points: int = 30,
    max_age_hours: int = 72,
) -> list[Candidate]:
    """Fetch top AI-related stories from Hacker News Algolia search API."""
    candidates: list[Candidate] = []
    cutoff_timestamp = int(
        (datetime.now(UTC) - timedelta(hours=max_age_hours)).timestamp()
    )

    url = "https://hn.algolia.com/api/v1/search_by_date"
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{cutoff_timestamp},points>={min_points}",
        "hitsPerPage": 25,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                for hit in data.get("hits", []):
                    title = hit.get("title", "").strip()
                    story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                    points = hit.get("points", 0)
                    if title and story_url:
                        candidates.append(
                            Candidate(
                                title=title,
                                url=story_url,
                                published=hit.get("created_at", ""),
                                summary=f"HN Story with {points} points and {hit.get('num_comments', 0)} comments",
                                source_name="Hacker News",
                                score=float(points),
                            )
                        )
    except Exception as e:
        logger.warning("Error fetching Hacker News candidates: %s", e)

    return candidates


def collect_all_candidates(
    feeds_config_path: Path | str = "config/feeds.yaml",
    max_age_hours: int = 72,
    max_title_similarity: float = 0.6,
) -> list[Candidate]:
    """
    Collect candidates from all configured RSS feeds and Hacker News,
    filtering out previously used URLs and duplicate/similar titles.
    """
    cfg = load_feeds_config(feeds_config_path)
    all_candidates: list[Candidate] = []

    # 1. Fetch RSS Feeds
    for feed in cfg.get("feeds", []):
        feed_url = feed.get("url")
        feed_name = feed.get("name", "RSS Feed")
        if feed_url:
            all_candidates.extend(fetch_rss_candidates(feed_url, feed_name, max_age_hours))

    # 2. Fetch Hacker News
    hn_cfg = cfg.get("hacker_news", {})
    if hn_cfg.get("enabled", True):
        query = hn_cfg.get("query", "AI OR LLM OR Claude OR Gemini")
        min_points = hn_cfg.get("min_points", 30)
        hn_items = fetch_hacker_news_candidates(query=query, min_points=min_points, max_age_hours=max_age_hours)
        all_candidates.extend(hn_items)

    # 3. Deduplicate against state and seen candidates
    filtered: list[Candidate] = []
    seen_urls: set[str] = set()

    for cand in all_candidates:
        clean_url = cand.url.strip().rstrip("/")
        if clean_url in seen_urls:
            continue
        if has_source_url_been_used(clean_url):
            logger.debug("Skipping already published source URL: %s", clean_url)
            continue

        is_similar, ratio, _ = is_title_too_similar(cand.title, max_similarity=max_title_similarity)
        if is_similar:
            logger.debug("Skipping candidate with title too similar to past published title: %s (ratio %.2f)", cand.title, ratio)
            continue

        seen_urls.add(clean_url)
        filtered.append(cand)

    logger.info("Collected %d candidate topics across all sources (%d total raw)", len(filtered), len(all_candidates))
    return filtered
