"""Unit tests for Edge-TTS synthesise_scenes and verify_tts_wav_count."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


def test_synthesise_scenes_writes_wav_and_returns_duration(tmp_path):
    """Each scene gets a WAV file, count is verified, and duration_sec is populated."""
    from autopilot.tts.edge import synthesise_scenes

    scenes = [
        {"id": 1, "narration": "Hello world, this is a test narration."},
        {"id": 2, "narration": "Second scene narration goes here."},
    ]

    # Patch _synthesise_scene to write a dummy WAV and return 3.5s
    async def fake_synth(text, out_path, voice, rate):
        out_path.write_bytes(b"\x00" * 100)  # write dummy bytes
        return 3.5

    with patch("autopilot.tts.edge._synthesise_scene", side_effect=fake_synth):
        result = synthesise_scenes(scenes, tmp_path / "tts", voice="en-US-AndrewNeural")

    assert len(result) == 2
    for s in result:
        assert s["duration_sec"] == 3.5
        assert "audio_path" in s
        assert s["audio_path"].endswith(".wav")


def test_synthesise_scenes_invalid_rate_defaults_to_zero(tmp_path):
    """Invalid rate string is normalised to '+0%' silently."""
    from autopilot.tts.edge import _validate_rate

    assert _validate_rate("bad_rate") == "+0%"
    assert _validate_rate("+10%") == "+10%"
    assert _validate_rate("-5%") == "-5%"


def test_synthesise_scenes_empty_audio_raises(tmp_path):
    """Empty WAV output raises RuntimeError."""
    from autopilot.tts.edge import _synthesise_scene as orig

    async def _fake_stream(*args, **kwargs):
        yield {"type": "audio", "data": b""}  # empty audio

    communicate_mock = MagicMock()
    communicate_mock.stream.return_value = _fake_stream()

    async def run_real():
        out = tmp_path / "scene_001.wav"
        with patch("edge_tts.Communicate", return_value=communicate_mock):
            with pytest.raises(RuntimeError, match="empty audio"):
                await orig("test", out, "voice", "+0%")

    asyncio.run(run_real())


def test_verify_tts_wav_count_success(tmp_path):
    """verify_tts_wav_count passes when every scene has a non-empty WAV file."""
    from autopilot.tts.edge import verify_tts_wav_count

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    scenes = [
        {"id": 1, "narration": "Scene 1"},
        {"id": 2, "narration": "Scene 2"},
        {"id": 3, "narration": "Scene 3"},
    ]
    for s in scenes:
        (tts_dir / f"scene_{s['id']:03d}.wav").write_bytes(b"\x00" * 1000)

    assert verify_tts_wav_count(scenes, tts_dir) is True


def test_verify_tts_wav_count_mismatch_too_few(tmp_path):
    """verify_tts_wav_count raises RuntimeError when fewer WAV files exist than scenes."""
    from autopilot.tts.edge import verify_tts_wav_count

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    scenes = [
        {"id": 1, "narration": "Scene 1"},
        {"id": 2, "narration": "Scene 2"},
    ]
    # Only 1 WAV created
    (tts_dir / "scene_001.wav").write_bytes(b"\x00" * 1000)

    with pytest.raises(RuntimeError, match="TTS WAV count mismatch: found 1 valid WAV files.*expected 2"):
        verify_tts_wav_count(scenes, tts_dir)


def test_verify_tts_wav_count_mismatch_too_many(tmp_path):
    """verify_tts_wav_count raises RuntimeError when extra WAV files exist."""
    from autopilot.tts.edge import verify_tts_wav_count

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    scenes = [
        {"id": 1, "narration": "Scene 1"},
    ]
    (tts_dir / "scene_001.wav").write_bytes(b"\x00" * 1000)
    (tts_dir / "scene_002.wav").write_bytes(b"\x00" * 1000)

    with pytest.raises(RuntimeError, match="TTS WAV count mismatch: found 2 valid WAV files.*expected 1"):
        verify_tts_wav_count(scenes, tts_dir)


def test_verify_tts_wav_count_empty_wav_raises(tmp_path):
    """verify_tts_wav_count raises RuntimeError when a WAV file is 0 bytes."""
    from autopilot.tts.edge import verify_tts_wav_count

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir()
    scenes = [
        {"id": 1, "narration": "Scene 1"},
        {"id": 2, "narration": "Scene 2"},
    ]
    (tts_dir / "scene_001.wav").write_bytes(b"\x00" * 1000)
    (tts_dir / "scene_002.wav").write_bytes(b"")  # 0 bytes

    with pytest.raises(RuntimeError):
        verify_tts_wav_count(scenes, tts_dir)
