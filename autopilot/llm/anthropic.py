"""Anthropic LLM Provider using Anthropic Python SDK."""

import json
import re
from typing import Any

import anthropic

from autopilot.llm.base import LLMProvider
from autopilot.utils.logging import get_logger
from autopilot.utils.retry import with_retry

logger = get_logger("autopilot.llm.anthropic")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude LLM provider."""

    def __init__(
        self, api_key: str, model: str = "claude-3-5-sonnet-20241022", temperature: float = 0.7
    ):
        if not api_key:
            raise ValueError("LLM_API_KEY is required for AnthropicProvider")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.client = anthropic.Anthropic(api_key=self.api_key)

    @with_retry(max_attempts=3, min_wait=2.0, max_wait=10.0)
    def generate_json(self, prompt: str, schema_model: type | None = None) -> dict[str, Any]:
        """Generate structured JSON response adhering to prompt."""
        system_prompt = (
            "You are an expert AI scriptwriter and editor. You must always return strictly valid JSON "
            "with no preamble, no commentary, and no surrounding markdown blocks unless specified."
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        content_text = ""
        for block in message.content:
            if block.type == "text":
                content_text += block.text

        cleaned = content_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON response from Anthropic: %s\nRaw output: %s", e, content_text
            )
            raise ValueError(f"Anthropic returned invalid JSON: {e}") from e
