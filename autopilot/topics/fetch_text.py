"""Fetch and clean source web text for grounding."""

import trafilatura

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.topics.fetch_text")


def fetch_article_text(url: str, max_chars: int = 8000) -> str:
    """
    Download and extract main clean text from a web article URL.
    Returns cleaned markdown/plain text for grounding.
    """
    if not url:
        return ""

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning("Could not download page content from: %s", url)
            return ""

        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_precision=True,
        )

        if not extracted:
            logger.warning("Trafilatura failed to extract text from: %s", url)
            return ""

        cleaned = extracted.strip()
        if len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars] + "\n\n[... truncated for length ...]"

        logger.info("Successfully extracted %d characters from %s", len(cleaned), url)
        return cleaned

    except Exception as e:
        logger.error("Error fetching article text from %s: %s", url, e)
        return ""
