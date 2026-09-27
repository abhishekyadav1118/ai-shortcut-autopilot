"""Unit tests for full pipeline orchestration (autopilot.run)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.models import Script
from autopilot.render.qa import QAResult, RenderQAError
from autopilot.run import run_pipeline
from autopilot.upload.youtube import UploadResult


@pytest.fixture
def mock_script():
    """Sample Script object for testing."""
    return Script(
        title="Test Title",
        hook="Test Hook",
        core_takeaway="Takeaway",
        sections=[],
        cta="Subscribe",
        description="Description",
        tags=["ai"],
        pinned_comment="Comment",
        thumbnail_text="Thumbnail Title",
        chapters=[],
        fact_check_confidence=0.9,
        scenes=[
            {
                "id": 1,
                "narration": "Scene 1 narration text.",
                "visual_type": "card",
                "visual_query": "AI",
                "on_screen_text": "Scene 1",
                "bullets": ["Bullet 1"],
                "source_ids": [1],
                "duration_sec": 5.0,
            }
        ],
    )


def test_run_pipeline_success_step_order(tmp_path, mock_script):
    """Verifies that all 7 pipeline steps execute in exact sequence."""
    mock_qa = QAResult(passed=True, video_codec="h264", audio_codec="aac", width=1920, height=1080, fps=30.0, duration_sec=400.0, size_mb=5.0)
    mock_upload = UploadResult(success=True, video_id="vid123", url="https://youtu.be/vid123", privacy_status="private")

    call_order = []

    def mock_gen_script(*args, **kwargs):
        call_order.append("script")
        return mock_script

    def mock_tts(scenes, *args, **kwargs):
        call_order.append("tts")
        return scenes

    def mock_cards(scenes, *args, **kwargs):
        call_order.append("cards")
        return scenes

    def mock_subtitles(scenes, *args, **kwargs):
        call_order.append("subtitles")
        out_path = kwargs.get("out_path", tmp_path / "sub.srt")
        return Path(out_path)

    def mock_assemble(scenes, *args, **kwargs):
        call_order.append("assemble")
        out_dir = kwargs.get("out_dir", tmp_path / "out")
        return Path(out_dir) / "final.mp4"

    def mock_qa_func(*args, **kwargs):
        call_order.append("qa")
        return mock_qa

    def mock_upload_func(*args, **kwargs):
        call_order.append("upload")
        return mock_upload

    with (
        patch("autopilot.run.get_settings"),
        patch("autopilot.run.get_llm_provider"),
        patch("autopilot.run.generate_and_validate_script", side_effect=mock_gen_script),
        patch("autopilot.run.synthesise_scenes", side_effect=mock_tts),
        patch("autopilot.run.render_all_cards", side_effect=mock_cards),
        patch("autopilot.run.generate_srt", side_effect=mock_subtitles),
        patch("autopilot.run.generate_both_thumbnails", return_value=(tmp_path / "a.png", tmp_path / "b.png")),
        patch("autopilot.run.assemble_video", side_effect=mock_assemble),
        patch("autopilot.run.qa_mp4", side_effect=mock_qa_func),
        patch("autopilot.run.upload_video", side_effect=mock_upload_func),
    ):
        result = run_pipeline(
            topic="Test Topic",
            dry_run=True,
            privacy="private",
            work_dir=tmp_path / "work",
            out_dir=tmp_path / "out",
        )

    assert call_order == ["script", "tts", "cards", "subtitles", "assemble", "qa", "upload"]
    assert result["script"] == mock_script
    assert result["qa_result"].passed is True
    assert result["upload_result"].success is True


def test_run_pipeline_stops_on_script_failure(tmp_path):
    """Pipeline must stop immediately if script generation fails."""
    mock_tts = MagicMock()
    mock_upload = MagicMock()

    with (
        patch("autopilot.run.get_settings"),
        patch("autopilot.run.get_llm_provider"),
        patch("autopilot.run.already_published_today", return_value=False),
        patch("autopilot.run.generate_and_validate_script", side_effect=ValueError("LLM Error")),
        patch("autopilot.run.synthesise_scenes", mock_tts),
        patch("autopilot.run.upload_video", mock_upload),
    ):
        with pytest.raises(ValueError, match="LLM Error"):
            run_pipeline("Topic", work_dir=tmp_path / "work", out_dir=tmp_path / "out")

    mock_tts.assert_not_called()
    mock_upload.assert_not_called()


def test_run_pipeline_stops_on_qa_failure_never_uploads(tmp_path, mock_script):
    """Pipeline must raise RenderQAError and NEVER upload if QA gate fails."""
    mock_qa = QAResult(passed=False, failures=["Duration too short: 300s < 360s"])
    mock_upload = MagicMock()

    with (
        patch("autopilot.run.get_settings"),
        patch("autopilot.run.get_llm_provider"),
        patch("autopilot.run.already_published_today", return_value=False),
        patch("autopilot.run.generate_and_validate_script", return_value=mock_script),
        patch("autopilot.run.synthesise_scenes", side_effect=lambda scenes, *args, **kwargs: scenes),
        patch("autopilot.run.render_all_cards", side_effect=lambda scenes, *args, **kwargs: scenes),
        patch("autopilot.run.generate_srt", return_value=tmp_path / "sub.srt"),
        patch("autopilot.run.generate_both_thumbnails", return_value=(tmp_path / "a.png", tmp_path / "b.png")),
        patch("autopilot.run.assemble_video", return_value=tmp_path / "final.mp4"),
        patch("autopilot.run.qa_mp4", return_value=mock_qa),
        patch("autopilot.run.upload_video", mock_upload),
    ):
        with pytest.raises(RenderQAError, match="QA Gate failed"):
            run_pipeline("Topic", work_dir=tmp_path / "work", out_dir=tmp_path / "out")

    mock_upload.assert_not_called()


def test_run_pipeline_stops_on_upload_failure(tmp_path, mock_script):
    """Pipeline raises RuntimeError if YouTube upload returns success=False."""
    mock_qa = QAResult(passed=True)
    mock_upload = UploadResult(success=False, error="Quota exceeded")

    with (
        patch("autopilot.run.get_settings"),
        patch("autopilot.run.get_llm_provider"),
        patch("autopilot.run.already_published_today", return_value=False),
        patch("autopilot.run.generate_and_validate_script", return_value=mock_script),
        patch("autopilot.run.synthesise_scenes", side_effect=lambda scenes, *args, **kwargs: scenes),
        patch("autopilot.run.render_all_cards", side_effect=lambda scenes, *args, **kwargs: scenes),
        patch("autopilot.run.generate_srt", return_value=tmp_path / "sub.srt"),
        patch("autopilot.run.generate_both_thumbnails", return_value=(tmp_path / "a.png", tmp_path / "b.png")),
        patch("autopilot.run.assemble_video", return_value=tmp_path / "final.mp4"),
        patch("autopilot.run.qa_mp4", return_value=mock_qa),
        patch("autopilot.run.upload_video", return_value=mock_upload),
    ):
        with pytest.raises(RuntimeError, match="YouTube upload failed: Quota exceeded"):
            run_pipeline("Topic", work_dir=tmp_path / "work", out_dir=tmp_path / "out")


def test_run_pipeline_passes_dry_run_flag(tmp_path, mock_script):
    """Verifies that dry_run flag is passed down to upload_video."""
    mock_qa = QAResult(passed=True)
    mock_upload = UploadResult(success=True, dry_run=True)

    with (
        patch("autopilot.run.get_settings"),
        patch("autopilot.run.get_llm_provider"),
        patch("autopilot.run.generate_and_validate_script", return_value=mock_script),
        patch("autopilot.run.synthesise_scenes", side_effect=lambda scenes, *args, **kwargs: scenes),
        patch("autopilot.run.render_all_cards", side_effect=lambda scenes, *args, **kwargs: scenes),
        patch("autopilot.run.generate_srt", return_value=tmp_path / "sub.srt"),
        patch("autopilot.run.generate_both_thumbnails", return_value=(tmp_path / "a.png", tmp_path / "b.png")),
        patch("autopilot.run.assemble_video", return_value=tmp_path / "final.mp4"),
        patch("autopilot.run.qa_mp4", return_value=mock_qa),
        patch("autopilot.run.upload_video", return_value=mock_upload) as mock_upload_call,
    ):
        run_pipeline(
            topic="Topic",
            dry_run=True,
            privacy="unlisted",
            work_dir=tmp_path / "work",
            out_dir=tmp_path / "out",
        )

    mock_upload_call.assert_called_once()
    assert mock_upload_call.call_args.kwargs["dry_run"] is True
    assert mock_upload_call.call_args.kwargs["privacy_status"] == "unlisted"
