"""Unit tests for render/qa.py."""

from pathlib import Path
from unittest.mock import patch


def _fake_probe(streams, duration_sec=400.0):
    """Build a minimal ffprobe JSON response."""
    return {
        "streams": streams,
        "format": {"duration": str(duration_sec)},
    }


def _good_streams():
    return [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "sample_rate": "44100",
        },
    ]


def test_qa_mp4_passes_good_file(tmp_path):
    """A well-formed MP4 with correct streams and duration inside 360-480s passes default gates."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "final.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)  # 2 MB dummy

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(_good_streams(), 390.0)):
        result = qa_mp4(mp4)  # default duration gate: 360-480s

    assert result.passed is True
    assert result.failures == []
    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.width == 1920
    assert result.height == 1080
    assert result.duration_sec == 390.0


def test_qa_mp4_fails_wrong_codec(tmp_path):
    """Wrong video codec fails the gate."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "bad.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)

    streams = _good_streams()
    streams[0]["codec_name"] = "vp9"

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(streams, 390.0)):
        result = qa_mp4(mp4)

    assert result.passed is False
    assert any("h264" in f for f in result.failures)


def test_qa_mp4_fails_wrong_resolution(tmp_path):
    """Non-1920x1080 resolution fails."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "bad_res.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)

    streams = _good_streams()
    streams[0]["width"] = 1280
    streams[0]["height"] = 720

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(streams, 390.0)):
        result = qa_mp4(mp4)

    assert result.passed is False
    assert any("1280x720" in f for f in result.failures)


def test_qa_mp4_fails_too_short(tmp_path):
    """Duration below 360.0s fails the default duration gate."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "short.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(_good_streams(), 350.0)):
        result = qa_mp4(mp4)

    assert result.passed is False
    assert any("too short" in f for f in result.failures)
    assert any("360" in f for f in result.failures)


def test_qa_mp4_fails_too_long(tmp_path):
    """Duration above 480.0s fails the default duration gate."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "long.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(_good_streams(), 490.0)):
        result = qa_mp4(mp4)

    assert result.passed is False
    assert any("too long" in f for f in result.failures)
    assert any("480" in f for f in result.failures)


def test_qa_mp4_fails_file_too_small(tmp_path):
    """File under 1 MB minimum fails."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "tiny.mp4"
    mp4.write_bytes(b"\x00" * 100)  # 100 bytes

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(_good_streams(), 390.0)):
        result = qa_mp4(mp4)

    assert result.passed is False
    assert any("small" in f for f in result.failures)


def test_qa_mp4_file_not_found():
    """Missing file raises RenderQAError."""
    import pytest

    from autopilot.render.qa import RenderQAError, qa_mp4
    with pytest.raises(RenderQAError, match="not found"):
        qa_mp4(Path("/nonexistent/final.mp4"))


def test_qa_mp4_fails_no_audio_stream(tmp_path):
    """Missing audio stream fails."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "noaudio.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)

    video_only = [_good_streams()[0]]
    with patch("autopilot.render.qa._probe", return_value=_fake_probe(video_only, 390.0)):
        result = qa_mp4(mp4)

    assert result.passed is False
    assert any("audio" in f.lower() for f in result.failures)


def test_qa_mp4_verifies_tts_wav_count_when_provided(tmp_path):
    """When scenes and tts_dir are provided, qa_mp4 checks TTS WAV count = scene count."""
    from autopilot.render.qa import qa_mp4

    mp4 = tmp_path / "final.mp4"
    mp4.write_bytes(b"\x00" * 2_000_000)

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    # Create only 1 WAV for 2 scenes
    (tts_dir / "scene_001.wav").write_bytes(b"\x00" * 500)

    scenes = [{"id": 1, "narration": "One"}, {"id": 2, "narration": "Two"}]

    with patch("autopilot.render.qa._probe", return_value=_fake_probe(_good_streams(), 400.0)):
        result = qa_mp4(mp4, scenes=scenes, tts_dir=tts_dir)

    assert result.passed is False
    assert any("TTS WAV count mismatch" in f for f in result.failures)
