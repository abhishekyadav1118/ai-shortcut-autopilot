"""Unit tests for script generation and fact-checking flow."""

from unittest.mock import MagicMock

from autopilot.config import get_settings
from autopilot.models import Topic
from autopilot.script.factcheck import run_factcheck_pass
from autopilot.script.generate import generate_and_validate_script


def test_factcheck_pass_mocked(sample_script_data):
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
    assert result.unsupported_count == 1
    assert len(result.claims) == 2
    assert result.claims[0].status == "SUPPORTED"
    assert result.claims[1].status == "UNSUPPORTED"


def test_generate_and_validate_script_mocked(sample_script_data):
    settings = get_settings("config/config.yaml")
    mock_llm = MagicMock()
    # 1st call for generation, 2nd call for factcheck
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
    assert fact_res.unsupported_count == 0
