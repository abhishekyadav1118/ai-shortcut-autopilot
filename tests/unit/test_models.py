"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from autopilot.models import Candidate, Scene, Script


def test_candidate_model():
    cand = Candidate(
        title="OpenAI Releases New Model",
        url="https://openai.com/news/123",
        summary="Short description",
        source_name="OpenAI News",
    )
    assert cand.title == "OpenAI Releases New Model"
    assert cand.score == 0.0


def test_scene_model_validation():
    scene = Scene(
        id=1,
        narration="Hello and welcome to this video.",
        visual_type="card",
        on_screen_text="Welcome",
    )
    assert scene.id == 1
    assert scene.narration == "Hello and welcome to this video."

    # Empty narration should fail validation
    with pytest.raises(ValidationError):
        Scene(id=2, narration="   ")


def test_script_model_parsing(sample_script_data):
    script = Script(**sample_script_data)
    assert len(script.scenes) == 10
    assert len(script.chapters) == 3
    assert script.chapters[0].title == "Introduction to Artifacts"
    assert script.disclosures.ai_voice is True
    assert script.thumbnail_text == "CLAUDE ARTIFACTS GUIDE"
