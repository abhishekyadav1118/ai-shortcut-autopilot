"""OpenRouter LLM Provider using OpenRouter Chat Completions API."""

import os
from typing import Any

import httpx

from autopilot.llm.base import LLMProvider
from autopilot.utils.logging import get_logger
from autopilot.utils.retry import with_retry

logger = get_logger("autopilot.llm.openrouter")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider supporting Gemini, Claude, Llama, and other models."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "qwen/qwen3.8-27b:free",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        raw_key = (
            api_key
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("LLM_API_KEY")
            or ""
        )
        self.api_key = "".join(raw_key.split())  # removes all whitespace, newlines, tabs, and carriage returns
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY (or LLM_API_KEY) is required for OpenRouterProvider.\n"
                "Please configure 'OPENROUTER_API_KEY' or 'LLM_API_KEY' in your GitHub Repository Secrets "
                "(Settings -> Secrets and variables -> Actions) or in your local .env file."
            )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @with_retry(max_attempts=3, min_wait=2.0, max_wait=10.0)
    def generate_json(self, prompt: str, schema_model: type | None = None) -> dict[str, Any]:
        """Generate structured JSON response adhering to prompt."""
        clean_key = "".join(self.api_key.split())
        headers = {
            "Authorization": f"Bearer {clean_key}",
            "HTTP-Referer": "https://github.com/abhishekyadav1118/ai-shortcut-autopilot",
            "X-Title": "AI Shortcut Autopilot",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert AI scriptwriter and editor. You must always return strictly valid JSON "
                        "with no preamble, no markdown formatting, and no commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        # Only set max_tokens for paid models; free (:free) models don't need it
        # and setting it triggers 402 credit errors when credits are exhausted
        if ":free" not in self.model:
            payload["max_tokens"] = self.max_tokens

        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(OPENROUTER_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("OpenRouter API error [%d]: %s", e.response.status_code, e.response.text)
            raise ValueError(f"OpenRouter API error ({e.response.status_code}): {e.response.text}") from e
        except Exception as e:
            logger.error("HTTP request to OpenRouter failed: %s", e)
            raise

        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"OpenRouter returned empty choices: {data}")

        raw_text = choices[0].get("message", {}).get("content", "") or ""
        from autopilot.utils.json_repair import repair_and_parse_json
        return repair_and_parse_json(raw_text)
