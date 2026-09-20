"""LLM module exports and factory."""

from autopilot.config import AppSettings
from autopilot.llm.anthropic import AnthropicProvider
from autopilot.llm.base import LLMProvider
from autopilot.llm.gemini import GeminiProvider


def get_llm_provider(settings: AppSettings) -> LLMProvider:
    """Factory to instantiate the configured LLM provider."""
    provider_name = settings.llm.provider.lower()
    if provider_name == "gemini":
        return GeminiProvider(
            api_key=settings.llm_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=settings.llm_api_key,
            model=settings.llm.model,
            temperature=settings.llm.temperature,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")


__all__ = ["LLMProvider", "GeminiProvider", "AnthropicProvider", "get_llm_provider"]
