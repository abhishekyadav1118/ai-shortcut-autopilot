"""YouTube video metadata builder.

Generates:
- Title (≤100 chars, contains target keyword)
- Description with timestamped chapters, source URLs, credits, AI-voice disclosure
- Tags list (≤500 chars total)
- Category, language, made_for_kids
- Thumbnail text variants (Variant A: hook, Variant B: title-based, max 4 words each)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autopilot.models import Script
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.publish.metadata")

# YouTube limits
_TITLE_MAX = 100
_DESC_MAX = 5000
_TAGS_MAX_CHARS = 500

# Channel branding
_CHANNEL_NAME = "The AI Shortcut"
_CHANNEL_URL = "https://www.youtube.com/@TheAIShortcut"


@dataclass
class VideoMetadata:
    """Complete metadata package ready for YouTube upload."""

    title: str
    description: str
    tags: list[str]
    category_id: str = "28"          # Science & Technology
    language: str = "en"
    made_for_kids: bool = False
    thumbnail_text_a: str = ""       # Variant A: hook-based, max 4 words
    thumbnail_text_b: str = ""       # Variant B: title-based, max 4 words
    chapters: list[dict[str, Any]] = field(default_factory=list)


def _truncate_words(text: str, max_words: int = 4) -> str:
    """Return the first `max_words` words of a string."""
    words = text.strip().split()
    return " ".join(words[:max_words])


def _build_chapters_block(script: Script, scenes: list[dict] | None = None) -> str:
    """Build the YouTube chapters block (00:00 Intro format)."""
    if not script.chapters:
        return ""

    scene_list = scenes or [s.model_dump() for s in script.scenes]

    lines = ["⏱️ CHAPTERS"]

    # Calculate cumulative start time for each scene
    scene_start_times: dict[int, float] = {}
    current_time = 0.0
    for s in scene_list:
        sid = s["id"]
        scene_start_times[sid] = current_time
        current_time += float(s.get("duration_sec", 0.0))

    last_sec = -1.0
    for idx, ch in enumerate(script.chapters):
        if idx == 0:
            sec = 0.0
        else:
            sec = scene_start_times.get(ch.start_scene_id, ch.start_time_sec)
            if sec <= last_sec + 10.0:
                sec = last_sec + 10.0

        last_sec = sec
        m, s_rem = divmod(int(sec), 60)
        ts_str = f"{m:02d}:{s_rem:02d}"
        lines.append(f"{ts_str} {ch.title}")

    return "\n".join(lines)


def _build_source_block(script: Script) -> str:
    """Build a source references block from script disclosures."""
    sources = getattr(script, "source_urls", None) or []
    if not sources:
        return ""
    lines = ["📚 SOURCES"]
    for i, url in enumerate(sources, 1):
        lines.append(f"[{i}] {url}")
    return "\n".join(lines)


def build_description(
    script: Script,
    source_urls: list[str] | None = None,
    channel_name: str = _CHANNEL_NAME,
    channel_url: str = _CHANNEL_URL,
) -> str:
    """Assemble the full YouTube description (≤5000 chars) adhering to Content Quality Bar.

    Sections:
      1. Strong 2-3 line hook & summary
      2. Video overview paragraph
      3. Timestamped chapters (starting at 00:00)
      4. Sources & references
      5. One-line AI-voice disclosure
      6. Relevant CTA
      7. 3-5 hashtags at the end
    """
    parts: list[str] = []

    # 1 & 2. Hook and Overview
    hook = getattr(script, "hook", "").strip() or script.title
    summary = getattr(script, "summary", "").strip()

    parts.append(hook)
    if summary:
        parts.append(summary)
    else:
        parts.append(f"In this video, we dive deep into {script.title} and explore how these breakthrough AI tools are transforming automation and daily workflows.")

    parts.append("")

    # 3. Chapters
    chapters_block = _build_chapters_block(script)
    if chapters_block:
        parts.append(chapters_block)
        parts.append("")

    # 4. Source URLs
    urls = source_urls or getattr(script, "source_urls", None) or []
    if urls:
        parts.append("📚 SOURCES & REFERENCES")
        for i, url in enumerate(urls, 1):
            parts.append(f"[{i}] {url}")
        parts.append("")

    # 5. One-line AI-voice disclosure
    parts.append("🎙️ Voice disclosure: AI-generated narration (Microsoft Azure Neural TTS). Research & content editorially reviewed.")
    parts.append("")

    # 6. Call-to-action
    parts.append(
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📺 {channel_name}\n"
        f"Enjoying the breakdown? Subscribe to stay updated on the latest AI tools, automation shortcuts, and tech news!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    parts.append("")

    # 7. 3-5 relevant hashtags at the end
    base_hashtags = ["#AITools", "#ArtificialIntelligence", "#TechNews", "#AIUpdate", "#Automation"]
    # Derive from script tags if available
    script_tags = getattr(script, "tags", []) or []
    derived_hashtags = []
    for t in script_tags:
        cleaned = "".join(c for c in t if c.isalnum())
        if cleaned and len(cleaned) > 2:
            derived_hashtags.append(f"#{cleaned}")

    combined_hashtags = list(dict.fromkeys(derived_hashtags + base_hashtags))[:5]
    if len(combined_hashtags) < 3:
        combined_hashtags = base_hashtags[:3]

    parts.append(" ".join(combined_hashtags))

    description = "\n".join(parts)

    if len(description) > _DESC_MAX:
        logger.warning(
            "Description too long (%d chars); truncating to %d.", len(description), _DESC_MAX
        )
        description = description[: _DESC_MAX - 3] + "..."

    return description


def build_tags(script: Script, extra_tags: list[str] | None = None) -> list[str]:
    """Build 10-15 relevant keyword tags, trimmed so total comma-joined string ≤500 chars."""
    base_tags = list(getattr(script, "tags", []) or [])
    topic_words = [w for w in script.title.split() if len(w) > 3]

    default_broad_tags = [
        "AI tools",
        "artificial intelligence",
        "tech news",
        "AI update",
        "automation",
        "future tech",
        "The AI Shortcut",
    ]

    all_tags = base_tags + topic_words + (extra_tags or []) + default_broad_tags

    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for t in all_tags:
        tl = t.strip().lower()
        if tl and tl not in seen:
            seen.add(tl)
            deduped.append(t.strip())

    # Ensure 10-15 tags
    result: list[str] = []
    total = 0
    for tag in deduped:
        addition = len(tag) + (1 if result else 0)
        if total + addition > _TAGS_MAX_CHARS:
            break
        result.append(tag)
        total += addition
        if len(result) >= 15:
            break

    return result


def build_title(script: Script, max_len: int = _TITLE_MAX) -> str:
    """Return a YouTube-safe title, truncated to max_len characters."""
    title = script.title.strip()
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title


def build_thumbnail_texts(script: Script) -> tuple[str, str]:
    """Return (variant_a, variant_b) thumbnail text, max 4 words each.

    Variant A: first 4 words of the thumbnail_text field (hook-phrased, punchy).
    Variant B: first 4 words of the script title (keyword-rich).
    """
    thumb_raw = getattr(script, "thumbnail_text", "").strip() or script.hook
    variant_a = _truncate_words(thumb_raw, 4)
    variant_b = _truncate_words(script.title, 4)
    return variant_a, variant_b


def build_metadata(
    script: Script,
    source_urls: list[str] | None = None,
    category_id: str = "28",
    language: str = "en",
    made_for_kids: bool = False,
) -> VideoMetadata:
    """Build a complete VideoMetadata object from a Script.

    Args:
        script: Completed Script model from the pipeline.
        source_urls: Explicit source URLs to embed in description.
        category_id: YouTube category. 28 = Science & Technology.
        language: ISO 639-1 language code.
        made_for_kids: COPPA / YouTube children's content flag.

    Returns:
        VideoMetadata ready to pass to upload_video().
    """
    title = build_title(script)
    description = build_description(script, source_urls=source_urls)
    tags = build_tags(script)
    variant_a, variant_b = build_thumbnail_texts(script)

    chapters_dicts = [ch.model_dump() for ch in script.chapters] if script.chapters else []

    logger.info(
        "Metadata built: title=%r  tags=%d  desc=%d chars  thumb_a=%r  thumb_b=%r",
        title, len(tags), len(description), variant_a, variant_b,
    )

    return VideoMetadata(
        title=title,
        description=description,
        tags=tags,
        category_id=category_id,
        language=language,
        made_for_kids=made_for_kids,
        thumbnail_text_a=variant_a,
        thumbnail_text_b=variant_b,
        chapters=chapters_dicts,
    )


def save_metadata_json(metadata: VideoMetadata, out_path: Path | str) -> Path:
    """Persist metadata to a JSON file alongside the video package."""
    import json
    from dataclasses import asdict

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(asdict(metadata), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.info("Saved metadata JSON -> %s", out_path)
    return out_path
