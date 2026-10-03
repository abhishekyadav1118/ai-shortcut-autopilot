"""JSON repair utilities for handling truncated or malformed LLM JSON responses."""

import json
import re
from typing import Any

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.utils.json_repair")


def clean_markdown_fences(text: str) -> str:
    """Remove surrounding markdown backticks and code block markers."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
    return cleaned


def repair_and_parse_json(text: str) -> dict[str, Any]:
    """Parse JSON string, attempting automated repairs if truncated or malformed."""
    cleaned = clean_markdown_fences(text)

    # 1. Try standard json.loads first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Attempt to repair truncated JSON (common when hitting token limits)
    repaired = _attempt_json_repair(cleaned)
    try:
        data = json.loads(repaired)
        logger.warning("Successfully repaired truncated JSON from LLM output.")
        return data
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON even after repair attempt: %s\nSnippet: %s", e, cleaned[-300:])
        raise ValueError(f"Invalid JSON from LLM: {e}") from e


def _attempt_json_repair(s: str) -> str:
    """Heuristic repair for truncated JSON by closing open strings, objects, and arrays."""
    # Find if we are inside an unclosed string
    in_string = False
    escape = False
    stack = []

    for char in s:
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if not in_string:
            if char in ("{", "["):
                stack.append(char)
            elif char in ("}", "]"):
                if stack:
                    stack.pop()

    repaired = s
    # If open string, close it
    if in_string:
        repaired += '"'

    # Close remaining open structures in reverse
    for open_char in reversed(stack):
        if open_char == "{":
            repaired += "}"
        elif open_char == "[":
            repaired += "]"

    return repaired
