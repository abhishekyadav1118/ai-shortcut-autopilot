"""Unit tests for script generation and fact-checking flow."""

from unittest.mock import MagicMock, patch

import pytest

from autopilot.config import get_settings
from autopilot.models import Topic
from autopilot.script.factcheck import (
    _FACTCHECK_RETRY_WAITS,
    FactCheckUnverifiedError,
    run_factcheck_pass,
)
from autopilot.script.generate import generate_and_validate_script

# ---------------------------------------------------------------------------
# run_factcheck_pass — success path
# ---------------------------------------------------------------------------


def test_factcheck_pass_mocked(sample_script_data):
    """Successful factcheck sets factcheck_ran=True and returns real counts."""
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "claims": [
            {"text": "Interactive workspaces support live coding preview", "status": "SUPPORTED", "scene_id": 1},
            {"text": "Guaranteed 10x ROI", "status": "UNSUPPORTED", "scene_id": 2},
        ],
        "unsupported_count": 1,
        "corrected_script": sample_script_data,
    }

    topic = Topic(
        title="Modern AI Coding Workspaces",
        source_texts=["Official docs confirming interactive workspace preview."],
    )

    corrected, result = run_factcheck_pass(sample_script_data, topic, mock_llm)
    assert result.factcheck_ran is True
    assert result.unsupported_count == 1
    assert len(result.claims) == 2
    assert result.claims[0].status == "SUPPORTED"
    assert result.claims[1].status == "UNSUPPORTED"
    # verify we never get unsupported_count=0 when there is an UNSUPPORTED claim
    assert result.unsupported_count != 0


# ---------------------------------------------------------------------------
# run_factcheck_pass — fail-closed paths
# ---------------------------------------------------------------------------


def test_factcheck_raises_unverified_after_all_retries(sample_script_data):
    """
    If EVERY attempt fails, run_factcheck_pass must raise FactCheckUnverifiedError.
    It must NOT silently return unsupported_count=0.
    """
    mock_llm = MagicMock()
    mock_llm.generate_json.side_effect = Exception("503 UNAVAILABLE overloaded")

    topic = Topic(
        title="Test Topic",
        source_texts=["Some grounding text."],
    )

    # Patch time.sleep to avoid 220s real wait in tests
    with patch("autopilot.script.factcheck.time.sleep"):
        with pytest.raises(FactCheckUnverifiedError) as exc_info:
            run_factcheck_pass(sample_script_data, topic, mock_llm)

    assert "UNVERIFIED" in str(exc_info.value)
    assert "Pipeline halted" in str(exc_info.value)
    # Confirm all 5 attempts were made (1 initial + 4 retries)
    assert mock_llm.generate_json.call_count == len(_FACTCHECK_RETRY_WAITS) + 1


def test_factcheck_retries_correct_number_of_times(sample_script_data):
    """Exactly 4 retries (5 total attempts) are made before giving up."""
    mock_llm = MagicMock()
    mock_llm.generate_json.side_effect = RuntimeError("503 temporary server error")

    topic = Topic(title="Test Topic", source_texts=["grounding"])

    with patch("autopilot.script.factcheck.time.sleep") as mock_sleep:
        with pytest.raises(FactCheckUnverifiedError):
            run_factcheck_pass(sample_script_data, topic, mock_llm)

    # 4 sleeps between 5 attempts
    assert mock_sleep.call_count == len(_FACTCHECK_RETRY_WAITS)
    # Confirm the sleep durations follow the spec (10, 30, 60, 120)
    actual_waits = [call.args[0] for call in mock_sleep.call_args_list]
    assert actual_waits == list(_FACTCHECK_RETRY_WAITS)


def test_factcheck_succeeds_on_third_attempt(sample_script_data):
    """If the third attempt succeeds, factcheck_ran=True and no error is raised."""
    mock_llm = MagicMock()
    mock_llm.generate_json.side_effect = [
        Exception("503 overloaded"),
        Exception("503 overloaded"),
        {
            "claims": [{"text": "Claim A", "status": "SUPPORTED", "scene_id": 1}],
            "unsupported_count": 0,
            "corrected_script": sample_script_data,
        },
    ]

    topic = Topic(title="Test Topic", source_texts=["grounding"])

    with patch("autopilot.script.factcheck.time.sleep"):
        corrected, result = run_factcheck_pass(sample_script_data, topic, mock_llm)

    assert result.factcheck_ran is True
    assert result.unsupported_count == 0
    assert mock_llm.generate_json.call_count == 3


def test_factcheck_unverified_propagates_immediately_from_generate(sample_script_data):
    """
    FactCheckUnverifiedError from run_factcheck_pass propagates out of
    generate_and_validate_script immediately — it does NOT consume a
    regeneration attempt or get swallowed.
    """
    settings = get_settings("config/config.yaml")
    mock_llm = MagicMock()

    # Generation succeeds, but factcheck always fails
    mock_llm.generate_json.side_effect = [
        sample_script_data,   # generation call succeeds
        Exception("503 overloaded"),  # factcheck attempt 1
        Exception("503 overloaded"),  # factcheck attempt 2
        Exception("503 overloaded"),  # factcheck attempt 3
        Exception("503 overloaded"),  # factcheck attempt 4
        Exception("503 overloaded"),  # factcheck attempt 5
    ]

    topic = Topic(
        title="AI Code Assistants and Web Development: Build Web Apps Fast",
        format="how_to_walkthrough",
        angle="Build full web tools.",
        target_keyword="ai coding tools",
        source_texts=["Official docs."],
    )

    with patch("autopilot.script.factcheck.time.sleep"):
        with pytest.raises(FactCheckUnverifiedError) as exc_info:
            generate_and_validate_script(
                topic=topic,
                settings=settings,
                llm=mock_llm,
                enforce_full_length=False,
            )

    assert "UNVERIFIED" in str(exc_info.value)
    assert "Pipeline halted" in str(exc_info.value)


# ---------------------------------------------------------------------------
# generate_and_validate_script — success path
# ---------------------------------------------------------------------------


def test_generate_and_validate_script_mocked(sample_script_data):
    """Full happy-path: generation + factcheck + validation all succeed."""
    settings = get_settings("config/config.yaml")
    mock_llm = MagicMock()
    mock_llm.generate_json.side_effect = [
        sample_script_data,
        {
            "claims": [{"text": "Claim", "status": "SUPPORTED", "scene_id": 1}],
            "unsupported_count": 0,
            "corrected_script": sample_script_data,
        },
    ]

    topic = Topic(
        title="AI Code Assistants and Web Development: Build Web Apps Fast",
        format="how_to_walkthrough",
        angle="Build full web tools inside modern AI workspaces.",
        target_keyword="ai coding tools",
        source_texts=["Official documentation on modern AI developer workspaces."],
    )

    script, fact_res = generate_and_validate_script(
        topic=topic,
        settings=settings,
        llm=mock_llm,
        enforce_full_length=False,
    )

    assert script.title == sample_script_data["title"]
    assert fact_res.factcheck_ran is True
    assert fact_res.unsupported_count == 0


def test_generate_retries_when_word_count_outside_950_1150(sample_script_data):
    """When generated script has word count outside 950-1150, generator retries and succeeds on 2nd attempt."""
    import copy
    settings = get_settings("config/config.yaml")
    mock_llm = MagicMock()

    # Attempt 1: 904 words (too short for 950-1150 target)
    short_script_data = copy.deepcopy(sample_script_data)
    short_script_data["scenes"] = [
        {
            "id": i,
            "narration": " ".join(["word" + str(w) for w in range(35)]),
            "visual_type": "card",
            "visual_query": "tech",
            "on_screen_text": f"Point {i}",
            "bullets": ["A", "B"],
            "source_ids": [1],
        }
        for i in range(1, 26)  # 25 scenes * 35 words = 875 words (< 950)
    ]

    # Attempt 2: 1050 words (25 scenes * 42 words = 1050 words, within 950-1150)
    good_script_data = copy.deepcopy(sample_script_data)
    good_script_data["scenes"] = [
        {
            "id": i,
            "narration": " ".join(["word" + str(w) for w in range(42)]),
            "visual_type": "card",
            "visual_query": "tech",
            "on_screen_text": f"Point {i}",
            "bullets": ["A", "B"],
            "source_ids": [1],
        }
        for i in range(1, 26)
    ]

    factcheck_response = {
        "claims": [{"text": "Claim", "status": "SUPPORTED", "scene_id": 1}],
        "unsupported_count": 0,
        "corrected_script": None,
    }

    mock_llm.generate_json.side_effect = [
        short_script_data,   # 1st attempt generation (875 words)
        factcheck_response,  # 1st attempt factcheck
        good_script_data,    # 2nd attempt generation (1050 words)
        factcheck_response,  # 2nd attempt factcheck
    ]

    topic = Topic(
        title="AI Code Assistants and Web Development: Build Web Apps Fast",
        format="how_to_walkthrough",
        angle="Build full web tools inside modern AI workspaces.",
        target_keyword="ai coding tools",
        source_texts=["Official documentation on modern AI developer workspaces."],
    )

    script, fact_res = generate_and_validate_script(
        topic=topic,
        settings=settings,
        llm=mock_llm,
        enforce_full_length=True,
    )

    # 1st attempt failed word count validation, 2nd attempt succeeded
    assert sum(len(s.narration.split()) for s in script.scenes) == 1050
    assert mock_llm.generate_json.call_count == 4

