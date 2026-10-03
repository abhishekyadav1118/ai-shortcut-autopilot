"""Unit tests for OpenRouterProvider."""

import pytest
import respx

from autopilot.llm.openrouter import OPENROUTER_API_URL, OpenRouterProvider


@respx.mock
def test_openrouter_provider_generate_json_success():
    """Verify OpenRouterProvider makes correct request and parses JSON."""
    respx.post(OPENROUTER_API_URL).respond(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"title": "Test Title", "scenes": []}'
                    }
                }
            ]
        },
    )

    provider = OpenRouterProvider(api_key="sk-or-v1-testkey", model="google/gemini-2.5-flash")
    result = provider.generate_json("Generate script")

    assert result == {"title": "Test Title", "scenes": []}


@respx.mock
def test_openrouter_provider_strips_markdown_backticks():
    """Verify OpenRouterProvider removes markdown backticks from response."""
    respx.post(OPENROUTER_API_URL).respond(
        status_code=200,
        json={
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"status": "ok"}\n```'
                    }
                }
            ]
        },
    )

    provider = OpenRouterProvider(api_key="sk-or-v1-testkey")
    result = provider.generate_json("Status check")

    assert result == {"status": "ok"}


def test_openrouter_missing_api_key(monkeypatch):
    """Verify ValueError is raised if no API key is provided or found."""
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(api_key="")
