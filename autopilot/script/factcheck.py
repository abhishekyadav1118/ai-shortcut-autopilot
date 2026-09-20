"""Fact-checking and claim verification pass."""

import json
from pathlib import Path
from typing import Any

from autopilot.llm.base import LLMProvider
from autopilot.models import FactCheckClaim, FactCheckResult, Topic
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.script.factcheck")


def run_factcheck_pass(
    script_dict: dict[str, Any],
    topic: Topic,
    llm: LLMProvider,
    prompt_path: Path | str = "prompts/factcheck.md",
) -> tuple[dict[str, Any], FactCheckResult]:
    """
    Run LLM fact-checking pass comparing script against grounding sources.
    Returns (corrected_script_dict, factcheck_result).
    """
    p_prompt = Path(prompt_path)
    if not p_prompt.exists():
        logger.warning("Factcheck prompt file %s not found. Skipping factcheck pass.", prompt_path)
        return script_dict, FactCheckResult(unsupported_count=0, corrected_script=script_dict)

    prompt_template = p_prompt.read_text(encoding="utf-8")

    # Format sources with IDs
    sources_formatted = "\n\n".join(
        f"[SOURCE ID {i+1}]:\n{txt}"
        for i, txt in enumerate(topic.source_texts)
    )
    if not sources_formatted.strip():
        sources_formatted = f"[SOURCE ID 1]:\n{topic.title}\nAngle: {topic.angle}"

    prompt = (
        prompt_template.replace("{{script_json}}", json.dumps(script_dict, indent=2))
        .replace("{{sources_with_ids}}", sources_formatted)
    )

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
        )

        logger.info(
            "Fact-check pass complete. Evaluated %d claims. Unsupported claims: %d",
            len(claims),
            unsupported_count,
        )

        # Use corrected script if provided and valid, otherwise fallback to original
        final_script = corrected if (corrected and "scenes" in corrected) else script_dict
        return final_script, result

    except Exception as e:
        logger.warning("Error during LLM fact-checking pass: %s. Using original script.", e)
        return script_dict, FactCheckResult(unsupported_count=0, corrected_script=script_dict)
