"""Unit tests for audio utilities and optional music handling."""

from pathlib import Path

from autopilot.render.audio import select_background_music


def test_select_background_music_when_empty(tmp_path: Path):
    empty_music_dir = tmp_path / "empty_music"
    empty_music_dir.mkdir()
    assert select_background_music(empty_music_dir) is None


def test_select_background_music_when_nonexistent(tmp_path: Path):
    nonexistent = tmp_path / "does_not_exist"
    assert select_background_music(nonexistent) is None


def test_select_background_music_with_files(tmp_path: Path):
    music_dir = tmp_path / "music"
    music_dir.mkdir()
    track1 = music_dir / "track1.mp3"
    track1.write_text("dummy mp3 content")
    track2 = music_dir / "track2.wav"
    track2.write_text("dummy wav content")

    selected = select_background_music(music_dir)
    assert selected is not None
    assert selected.name in ["track1.mp3", "track2.wav"]
