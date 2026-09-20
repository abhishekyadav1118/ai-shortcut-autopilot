"""Rank candidates and select the optimal video topic using LLM."""

import json
import random
from pathlib import Path
from typing import Any

import yaml

from autopilot.llm.base import LLMProvider
from autopilot.models import Candidate, Topic
from autopilot.state import get_past_titles
from autopilot.topics.fetch_text import fetch_article_text
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.topics.ranker")


def load_formats_config(path: Path | str = "prompts/formats.yaml") -> list[dict[str, Any]]:
    """Load video formats from formats.yaml."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def load_evergreen_topics(path: Path | str = "config/evergreen_topics.yaml") -> list[dict[str, Any]]:
    """Load evergreen topic fallbacks."""
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        return data.get("evergreen_topics", [])


def get_evergreen_fallback(evergreen_path: Path | str = "config/evergreen_topics.yaml") -> Topic:
    """Select a fallback topic from evergreen list."""
    topics = load_evergreen_topics(evergreen_path)
    if not topics:
        return Topic(
            title="Top 5 Free AI Tools You Should Use in 2025",
            format="top_n_list",
            angle="Overlooked free AI tools that save time and replace expensive subscriptions.",
            why="Evergreen fallback topic.",
            target_keyword="free ai tools",
            source_texts=["A curated guide to top free open-source and free-tier artificial intelligence utilities."],
            source_urls=["https://github.com"],
        )

    chosen = random.choice(topics)
    return Topic(
        title=chosen.get("title", ""),
        format=chosen.get("format", "top_n_list"),
        angle=chosen.get("angle", ""),
        why="Selected from evergreen fallback catalogue.",
        target_keyword=chosen.get("target_keyword", "ai tools"),
        source_texts=[chosen.get("source_summary", "")],
        source_urls=[],
    )


def select_topic(
    candidates: list[Candidate],
    llm: LLMProvider,
    prompt_path: Path | str = "prompts/topic_rank.md",
    formats_path: Path | str = "prompts/formats.yaml",
    evergreen_path: Path | str = "config/evergreen_topics.yaml",
) -> Topic:
    """
    Rank candidate items and pick the best topic for today's video.
    Falls back to evergreen topic if no candidates exist or ranking fails.
    """
    if not candidates:
        logger.warning("No candidate topics available. Falling back to evergreen topic.")
        return get_evergreen_fallback(evergreen_path)

    p_prompt = Path(prompt_path)
    if not p_prompt.exists():
        logger.error("Prompt file %s not found. Falling back to evergreen.", prompt_path)
        return get_evergreen_fallback(evergreen_path)

    prompt_template = p_prompt.read_text(encoding="utf-8")
    past_titles = get_past_titles()
    formats = load_formats_config(formats_path)

    # Format candidates JSON for prompt
    candidates_payload = [
        {
            "index": i,
            "title": c.title,
            "source": c.source_name,
            "summary": c.summary,
            "score": c.score,
        }
        for i, c in enumerate(candidates[:20])  # limit to top 20 candidates
    ]

    prompt = (
        prompt_template.replace("{{candidates_json}}", json.dumps(candidates_payload, indent=2))
        .replace("{{past_titles}}", json.dumps(past_titles[-20:], indent=2))
        .replace("{{formats}}", json.dumps(formats, indent=2))
    )

    try:
        response = llm.generate_json(prompt)
        chosen_idx = int(response.get("chosen_index", 0))
        if chosen_idx < 0 or chosen_idx >= len(candidates):
            chosen_idx = 0

        chosen_candidate = candidates[chosen_idx]
        chosen_format = response.get("format", "news_breakdown")
        angle = response.get("angle", chosen_candidate.title)
        why = response.get("why", "")
        target_keyword = response.get("target_keyword", "ai tools")

        logger.info("LLM selected candidate #%d: '%s' (Format: %s)", chosen_idx, chosen_candidate.title, chosen_format)

        # Fetch source grounding text
        source_text = fetch_article_text(chosen_candidate.url)
        source_texts = [source_text] if source_text else [chosen_candidate.summary]
        source_urls = [chosen_candidate.url] if chosen_candidate.url else []

        return Topic(
            title=chosen_candidate.title,
            url=chosen_candidate.url,
            angle=angle,
            format=chosen_format,
            why=why,
            target_keyword=target_keyword,
            source_texts=source_texts,
            source_urls=source_urls,
        )

    except Exception as e:
        logger.error("Error during LLM topic ranking: %s. Falling back to evergreen.", e)
        return get_evergreen_fallback(evergreen_path)
