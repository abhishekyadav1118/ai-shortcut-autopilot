"""Unit tests for topic ranking and evergreen fallbacks."""

from unittest.mock import MagicMock

from autopilot.models import Candidate
from autopilot.topics.ranker import get_evergreen_fallback, select_topic


def test_get_evergreen_fallback():
    topic = get_evergreen_fallback("config/evergreen_topics.yaml")
    assert topic.title != ""
    assert topic.format != ""
    assert topic.target_keyword != ""


def test_select_topic_empty_candidates_fallback():
    mock_llm = MagicMock()
    topic = select_topic([], mock_llm)
    assert topic.title != ""
    # LLM should not even be called when candidate list is empty
    mock_llm.generate_json.assert_not_called()


def test_select_topic_with_candidates():
    candidates = [
        Candidate(
            title="OpenAI Releases Revolutionary Voice Feature",
            url="https://openai.com/blog/voice",
            summary="Advanced real-time speech interaction.",
            source_name="OpenAI News",
            score=100.0,
        )
    ]

    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "chosen_index": 0,
        "format": "how_to_walkthrough",
        "angle": "How to set up and leverage the new real-time voice feature for workflow automation.",
        "why": "High creator utility and actionable value.",
        "target_keyword": "openai advanced voice",
    }

    topic = select_topic(candidates, mock_llm)
    assert topic.title == "OpenAI Releases Revolutionary Voice Feature"
    assert topic.format == "how_to_walkthrough"
    assert topic.target_keyword == "openai advanced voice"
