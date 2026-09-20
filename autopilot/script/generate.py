"""Grounded script synthesis pipeline with fact-checking and regeneration loops."""

import json
from pathlib import Path

from autopilot.config import AppSettings
from autopilot.llm.base import LLMProvider
from autopilot.models import FactCheckResult, Script, Topic
from autopilot.script.factcheck import run_factcheck_pass
from autopilot.script.validate import ScriptValidationError, validate_script
from autopilot.state import get_past_titles
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.script.generate")


def build_script_prompt(
    topic: Topic,
    settings: AppSettings,
    prompt_path: Path | str = "prompts/script.md",
) -> str:
    """Interpolate topic grounding, channel guidelines, and parameters into script prompt."""
    p_prompt = Path(prompt_path)
    if not p_prompt.exists():
        raise FileNotFoundError(f"Script prompt template {prompt_path} not found")

    prompt_template = p_prompt.read_text(encoding="utf-8")
    past_titles = get_past_titles()

    min_mins, max_mins = settings.video.target_minutes
    min_words, max_words = settings.video.word_range

    sources_formatted = "\n\n".join(
        f"[SOURCE ID {i+1}]:\n{txt}"
        for i, txt in enumerate(topic.source_texts)
    )
    if not sources_formatted.strip():
        sources_formatted = f"[SOURCE ID 1]:\nTopic: {topic.title}\nAngle: {topic.angle}"

    prompt = (
        prompt_template.replace("{{minutes}}", f"{min_mins}-{max_mins}")
        .replace("{{min_words}}", str(min_words))
        .replace("{{max_words}}", str(max_words))
        .replace("{{format}}", topic.format)
        .replace("{{topic}}", topic.title)
        .replace("{{angle}}", topic.angle)
        .replace("{{target_keyword}}", topic.target_keyword)
        .replace("{{sources_with_ids}}", sources_formatted)
        .replace("{{past_titles}}", json.dumps(past_titles[-20:], indent=2))
    )

    return prompt


def generate_and_validate_script(
    topic: Topic,
    settings: AppSettings,
    llm: LLMProvider,
    prompt_path: Path | str = "prompts/script.md",
    factcheck_prompt_path: Path | str = "prompts/factcheck.md",
    max_regenerations: int | None = None,
    enforce_full_length: bool = True,
) -> tuple[Script, FactCheckResult]:
    """
    Generate a grounded script from topic, pass it through fact-checking,
    and validate against all quality gates. Retries up to max_regenerations on failure.
    """
    if max_regenerations is None:
        max_regenerations = settings.quality.max_regenerations

    prompt = build_script_prompt(topic, settings, prompt_path)
    last_error: Exception | None = None

    for attempt in range(max_regenerations + 1):
        logger.info("Script generation attempt %d / %d for topic '%s'", attempt + 1, max_regenerations + 1, topic.title)

        try:
            # 1. LLM Generation
            raw_script_dict = llm.generate_json(prompt)

            # 2. Fact-Checking Pass
            checked_dict, factcheck_result = run_factcheck_pass(
                raw_script_dict,
                topic,
                llm,
                prompt_path=factcheck_prompt_path,
            )

            # 3. Quality and Compliance Validation Gates
            validated_script = validate_script(
                checked_dict,
                settings=settings,
                max_title_similarity=settings.quality.max_title_similarity,
                enforce_full_length=enforce_full_length,
            )

            logger.info("Script successfully synthesized and validated on attempt %d", attempt + 1)
            return validated_script, factcheck_result

        except (ScriptValidationError, ValueError, Exception) as e:
            last_error = e
            logger.warning("Attempt %d failed validation: %s", attempt + 1, e)
            if attempt < max_regenerations:
                # Add correction feedback into prompt for next attempt
                prompt += f"\n\nCRITICAL FIX REQUIRED: Previous attempt failed validation with error: {e}. Please correct this strictly in your next output."

    raise RuntimeError(f"Script generation failed after {max_regenerations + 1} attempts. Last error: {last_error}")
