"""Gemini LLM Provider using Google Gen AI SDK."""

import json
import re
from typing import Any

from google import genai
from google.genai import types

from autopilot.llm.base import LLMProvider
from autopilot.utils.logging import get_logger
from autopilot.utils.retry import with_retry

logger = get_logger("autopilot.llm.gemini")


class GeminiProvider(LLMProvider):
    """Gemini LLM provider using the modern google.genai SDK."""

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash", temperature: float = 0.7):
        import os
        api_key = (
            api_key
            or os.getenv("LLM_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or ""
        )
        if not api_key:
            raise ValueError(
                "LLM_API_KEY is required for GeminiProvider. "
                "In GitHub Actions: Please configure 'LLM_API_KEY' (or 'GEMINI_API_KEY') in your GitHub repository secrets "
                "(Settings -> Secrets and variables -> Actions -> Repository secrets). "
                "Locally: Add LLM_API_KEY to your .env file."
            )
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)

    @with_retry(max_attempts=3, min_wait=2.0, max_wait=10.0)
    def generate_json(self, prompt: str, schema_model: type | None = None) -> dict[str, Any]:
        """Generate structured JSON response adhering to prompt."""
        config = types.GenerateContentConfig(
            temperature=self.temperature,
            response_mime_type="application/json",
        )
        if schema_model is not None:
            config.response_schema = schema_model

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

        raw_text = response.text or ""
        # Clean any accidental markdown backticks
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response from Gemini: %s\nRaw output: %s", e, raw_text)
            raise ValueError(f"Gemini returned invalid JSON: {e}") from e
