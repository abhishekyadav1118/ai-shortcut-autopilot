"""LLM module exports and factory."""

import os

from autopilot.config import AppSettings
from autopilot.llm.anthropic import AnthropicProvider
from autopilot.llm.base import LLMProvider
from autopilot.llm.gemini import GeminiProvider
from autopilot.llm.openrouter import OpenRouterProvider


def get_llm_provider(settings: AppSettings) -> LLMProvider:
    """Factory to instantiate the configured LLM provider."""
    provider_name = settings.llm.provider.lower()
    api_key = settings.llm_api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY") or ""

    # Auto-detect OpenRouter if key starts with sk-or- or provider is openrouter
    if provider_name == "openrouter" or api_key.startswith("sk-or-"):
        model = settings.llm.model
        if not model or "/" not in model:
            model = "google/gemini-2.5-flash"
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            temperature=settings.llm.temperature,
        )
    elif provider_name == "gemini":
        return GeminiProvider(
            api_key=api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")


__all__ = ["LLMProvider", "GeminiProvider", "AnthropicProvider", "OpenRouterProvider", "get_llm_provider"]
