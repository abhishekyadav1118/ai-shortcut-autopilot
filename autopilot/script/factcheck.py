"""Fact-checking and claim verification pass — fails closed on LLM errors."""

import json
import time
from pathlib import Path
from typing import Any

from autopilot.llm.base import LLMProvider
from autopilot.models import FactCheckClaim, FactCheckResult, Topic
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.script.factcheck")

# Retry schedule: waits in seconds between each attempt (4 retries = 5 total attempts)
_FACTCHECK_RETRY_WAITS = (10, 30, 60, 120)


class FactCheckUnverifiedError(RuntimeError):
    """
    Raised when the fact-check LLM call fails on ALL retry attempts.

    The pipeline MUST stop before any upload when this is raised.
    Never silently continue with unsupported_count=0 when the fact-check
    did not actually run.
    """


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception is a transient API error worth retrying."""
    msg = str(exc).upper()
    return any(code in msg for code in ("503", "UNAVAILABLE", "429", "RATE_LIMIT", "500", "502", "DEADLINE"))


def run_factcheck_pass(
    script_dict: dict[str, Any],
    topic: Topic,
    llm: LLMProvider,
    prompt_path: Path | str = "prompts/factcheck.md",
) -> tuple[dict[str, Any], FactCheckResult]:
    """
    Run LLM fact-checking pass comparing script against grounding sources.

    Retry schedule: 4 retries with waits of 10s, 30s, 60s, 120s (5 total attempts).
    If ALL attempts fail, raise FactCheckUnverifiedError — do NOT silently fall back.
    Never report unsupported_count=0 when the fact-check did not actually run.

    Returns (corrected_script_dict, FactCheckResult) on success.
    Raises FactCheckUnverifiedError on total failure.
    """
    p_prompt = Path(prompt_path)
    if not p_prompt.exists():
        raise FactCheckUnverifiedError(
            f"Fact-check prompt file '{prompt_path}' not found. "
            "Cannot verify script — pipeline halted."
        )

    prompt_template = p_prompt.read_text(encoding="utf-8")

    # Format sources with IDs
    sources_formatted = "\n\n".join(
        f"[SOURCE ID {i + 1}]:\n{txt}"
        for i, txt in enumerate(topic.source_texts)
    )
    if not sources_formatted.strip():
        sources_formatted = f"[SOURCE ID 1]:\n{topic.title}\nAngle: {topic.angle}"

    prompt = (
        prompt_template
        .replace("{{script_json}}", json.dumps(script_dict, indent=2))
        .replace("{{sources_with_ids}}", sources_formatted)
    )

    last_exc: Exception | None = None
    max_attempts = len(_FACTCHECK_RETRY_WAITS) + 1  # 5 total

    for attempt in range(max_attempts):
        try:
            response = llm.generate_json(prompt)

            claims_data = response.get("claims", [])
            unsupported_count = int(response.get("unsupported_count", 0))
            corrected = response.get("corrected_script", {})

            claims = [
                FactCheckClaim(
                    text=c.get("text", ""),
                    status=c.get("status", "SUPPORTED"),
                    scene_id=int(c.get("scene_id", 1)),
                )
                for c in claims_data
            ]

            result = FactCheckResult(
                claims=claims,
                unsupported_count=unsupported_count,
                corrected_script=corrected or script_dict,
                factcheck_ran=True,
            )

            logger.info(
                "Fact-check PASSED on attempt %d/%d. Claims: %d, Unsupported: %d",
                attempt + 1,
                max_attempts,
                len(claims),
                unsupported_count,
            )

            final_script = corrected if (corrected and "scenes" in corrected) else script_dict
            return final_script, result

        except Exception as exc:
            last_exc = exc
            is_last = attempt == max_attempts - 1

            if is_last:
                break

            wait_sec = _FACTCHECK_RETRY_WAITS[attempt]
            if _is_retryable(exc):
                logger.warning(
                    "Fact-check attempt %d/%d failed (transient): %s. "
                    "Retrying in %ds...",
                    attempt + 1, max_attempts, exc, wait_sec,
                )
            else:
                # Non-retryable error (bad JSON, schema mismatch): still retry since
                # Gemini sometimes returns garbled JSON under high load
                logger.warning(
                    "Fact-check attempt %d/%d failed (error): %s. "
                    "Retrying in %ds...",
                    attempt + 1, max_attempts, exc, wait_sec,
                )
            time.sleep(wait_sec)

    # All attempts exhausted — fail CLOSED, never silently continue
    raise FactCheckUnverifiedError(
        f"Fact-check FAILED after {max_attempts} attempts "
        f"(waits: {_FACTCHECK_RETRY_WAITS}s). "
        f"Last error: {last_exc}. "
        "Pipeline halted — script is UNVERIFIED. Fix the API issue and re-run."
    )
