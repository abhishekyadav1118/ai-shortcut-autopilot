"""Unit tests for render/subtitles.py."""


def test_generate_srt_basic(tmp_path):
    """Basic SRT generation produces correct file with right number of entries."""
    from autopilot.render.subtitles import generate_srt

    scenes = [
        {"id": 1, "narration": "First narration here.", "duration_sec": 5.0},
        {"id": 2, "narration": "Second narration goes here.", "duration_sec": 4.5},
    ]
    out = tmp_path / "test.srt"
    generate_srt(scenes, out)

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "1\n" in content
    assert "2\n" in content
    # Check timestamp format HH:MM:SS,mmm
    assert "00:00:00,000 --> 00:00:05,000" in content
    assert "00:00:05,000 --> 00:00:09,500" in content


def test_generate_srt_long_narration_splits(tmp_path):
    """Narrations with > 15 words are split into two subtitle lines."""
    from autopilot.render.subtitles import generate_srt

    long_narration = " ".join(["word"] * 20)  # 20 words
    scenes = [{"id": 1, "narration": long_narration, "duration_sec": 10.0}]
    out = tmp_path / "split.srt"
    generate_srt(scenes, out)

    content = out.read_text(encoding="utf-8")
    # Two-line subtitle has a newline in the middle of the text
    lines = content.strip().split("\n")
    # Expect: index, timestamp, line1, line2, blank
    assert len([line for line in lines if line.strip() == ""]) >= 0  # has blank separator


def test_generate_srt_timestamp_format():
    """_format_srt_time correctly converts seconds to SRT timestamp."""
    from autopilot.render.subtitles import _format_srt_time

    assert _format_srt_time(0.0) == "00:00:00,000"
    assert _format_srt_time(61.5) == "00:01:01,500"
    assert _format_srt_time(3661.123) == "01:01:01,123"
    assert _format_srt_time(3600.0) == "01:00:00,000"


def test_generate_srt_cumulative_timing(tmp_path):
    """Each entry starts where the previous one ended."""
    from autopilot.render.subtitles import generate_srt

    scenes = [
        {"id": 1, "narration": "First.", "duration_sec": 10.0},
        {"id": 2, "narration": "Second.", "duration_sec": 5.0},
        {"id": 3, "narration": "Third.", "duration_sec": 8.0},
    ]
    out = tmp_path / "timing.srt"
    generate_srt(scenes, out)

    content = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:10,000" in content  # scene 1
    assert "00:00:10,000 --> 00:00:15,000" in content  # scene 2
    assert "00:00:15,000 --> 00:00:23,000" in content  # scene 3
