"""LLM provider interfaces and implementations."""

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers (Gemini, Anthropic)."""

    @abstractmethod
    def generate_json(self, prompt: str, schema_model: type | None = None) -> dict[str, Any]:
        """Generate structured JSON response adhering to prompt and optional schema."""
        pass
