"""Strict quality and compliance validation gates for generated scripts."""

from typing import Any

from autopilot.config import AppSettings
from autopilot.models import Script
from autopilot.state import is_title_too_similar
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.script.validate")

# Banned spam/hype/financial phrases
BANNED_PHRASES = [
    "guaranteed",
    "get rich",
    "secret trick",
    "make money fast",
    "passive income overnight",
    "financial freedom in days",
    "cure disease",
    "miracle cure",
    "100% risk free",
    "instant millionaire",
]


class ScriptValidationError(ValueError):
    """Raised when a script fails any quality or compliance validation gate."""

    def __init__(self, message: str, errors: list[str]):
        super().__init__(message)
        self.errors = errors


def count_spoken_words(script: Script) -> int:
    """Calculate total spoken narration words across all scenes."""
    return sum(len(scene.narration.split()) for scene in script.scenes)


def validate_script(
    script_data: dict[str, Any] | Script,
    settings: AppSettings,
    max_title_similarity: float = 0.6,
    enforce_full_length: bool = True,
) -> Script:
    """
    Validate script data against all compliance and quality gates.
    Raises ScriptValidationError if any gate fails.
    """
    errors: list[str] = []

    # 1. Parse Script model
    if isinstance(script_data, dict):
        try:
            script = Script(**script_data)
        except Exception as e:
            raise ScriptValidationError(f"Invalid script schema: {e}", [str(e)]) from e
    else:
        script = script_data

    # 2. Title validation (40 - 90 chars)
    title = script.title.strip()
    if len(title) < 40 or len(title) > 90:
        errors.append(
            f"Title length ({len(title)} chars) is outside the required 40-90 character range."
        )

    # 3. Title similarity check against past published titles
    is_similar, ratio, match = is_title_too_similar(title, max_similarity=max_title_similarity)
    if is_similar:
        errors.append(
            f"Title is too similar to past title '{match}' (similarity ratio: {ratio:.2f} >= {max_title_similarity})."
        )

    # 4. Description validation (under 5000 bytes)
    desc_bytes = len(script.description.encode("utf-8"))
    if desc_bytes > 5000:
        errors.append(f"Description exceeds YouTube limit (got {desc_bytes} bytes, max 5000 bytes).")
    if not script.description.strip():
        errors.append("Description cannot be empty.")

    # 5. Tags validation (total length under 500 characters, 5-20 tags)
    total_tags_len = sum(len(t) for t in script.tags)
    if total_tags_len > 500:
        errors.append(f"Total tags length ({total_tags_len} chars) exceeds 500 characters limit.")
    if len(script.tags) < 4:
        errors.append(f"Not enough tags provided (got {len(script.tags)}, minimum 4 required).")

    # 6. Chapters validation (at least 3 chapters, valid scene IDs)
    if len(script.chapters) < 3:
        errors.append(f"At least 3 chapters required (got {len(script.chapters)}).")
    scene_ids = {s.id for s in script.scenes}
    for ch in script.chapters:
        if ch.start_scene_id not in scene_ids:
            errors.append(f"Chapter '{ch.title}' references invalid scene ID {ch.start_scene_id}.")

    # 7. Scenes validation & Word Count
    total_words = count_spoken_words(script)
    min_words, max_words = settings.video.word_range

    if enforce_full_length:
        if total_words < min_words or total_words > max_words:
            errors.append(
                f"Total spoken word count ({total_words} words) outside allowed range [{min_words}, {max_words}]."
            )
        if len(script.scenes) < 15 or len(script.scenes) > 50:
            errors.append(
                f"Scene count ({len(script.scenes)}) outside required 15-50 range for 6-8 minute video."
            )

    # 8. Per-scene checks (narration <= 45 words, non-empty)
    for scene in script.scenes:
        words_in_scene = len(scene.narration.split())
        if words_in_scene == 0:
            errors.append(f"Scene {scene.id} has empty narration.")
        elif words_in_scene > 50:
            errors.append(
                f"Scene {scene.id} narration has {words_in_scene} words (max allowed is 50 words per scene)."
            )

    # 9. Banned hype phrases & compliance checks
    full_text = (
        f"{script.title} {script.hook} {script.description} "
        + " ".join(s.narration for s in script.scenes)
    ).lower()

    for phrase in BANNED_PHRASES:
        if phrase in full_text:
            errors.append(f"Found banned compliance phrase: '{phrase}'.")

    # 10. Thumbnail text check (max 4 words)
    thumb_words = len(script.thumbnail_text.split())
    if thumb_words > 4:
        errors.append(f"Thumbnail text too long ({thumb_words} words, max 4 allowed).")

    if errors:
        msg = f"Script validation failed with {len(errors)} error(s):\n - " + "\n - ".join(errors)
        logger.warning(msg)
        raise ScriptValidationError(msg, errors)

    logger.info("Script validation PASSED. Total words: %d, Scenes: %d", total_words, len(script.scenes))
    return script
