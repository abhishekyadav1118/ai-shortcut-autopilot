"""Comprehensive unit tests for script quality, compliance, and validation gates."""

import copy

import pytest

from autopilot.config import get_settings
from autopilot.script.validate import ScriptValidationError, count_spoken_words, validate_script


def _create_full_length_script_data(sample_script_data, word_count_per_scene=40, scene_count=25):
    """Helper to generate a valid full-length script fixture with N scenes and target words."""
    data = copy.deepcopy(sample_script_data)
    scenes = []
    for i in range(1, scene_count + 1):
        words = ["word" + str(w) for w in range(word_count_per_scene)]
        narration = " ".join(words)
        scenes.append({
            "id": i,
            "narration": narration,
            "visual_type": "card",
            "visual_query": "technology topic",
            "on_screen_text": f"Point {i}",
            "bullets": ["Detail A", "Detail B"],
            "source_ids": [1],
        })
    data["scenes"] = scenes
    data["chapters"] = [
        {"start_scene_id": 1, "title": "Introduction"},
        {"start_scene_id": 10, "title": "Core Breakdown"},
        {"start_scene_id": 20, "title": "Summary & Next Steps"},
    ]
    return data


def test_validate_good_fixture_preview(sample_script_data):
    """Short fixture passes when enforce_full_length is False."""
    settings = get_settings("config/config.yaml")
    script = validate_script(sample_script_data, settings, enforce_full_length=False)
    assert script.title == sample_script_data["title"]
    assert count_spoken_words(script) > 100


def test_validate_valid_full_length_script(sample_script_data):
    """Full-length 1000-word script with 25 scenes passes full validation."""
    settings = get_settings("config/config.yaml")
    full_data = _create_full_length_script_data(sample_script_data, word_count_per_scene=40, scene_count=25)
    script = validate_script(full_data, settings, enforce_full_length=True)
    assert count_spoken_words(script) == 1000
    assert len(script.scenes) == 25


def test_validate_script_too_short_fails(sample_script_data):
    """Scripts under min_words (950) fail when enforce_full_length is True."""
    settings = get_settings("config/config.yaml")
    # 20 scenes * 30 words = 600 words (< 950)
    short_data = _create_full_length_script_data(sample_script_data, word_count_per_scene=30, scene_count=20)
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(short_data, settings, enforce_full_length=True)
    assert "Total spoken word count (600 words) outside allowed range" in str(exc.value)


def test_validate_script_too_long_fails(sample_script_data):
    """Scripts over max_words (1150) fail when enforce_full_length is True."""
    settings = get_settings("config/config.yaml")
    # 30 scenes * 45 words = 1350 words (> 1150)
    long_data = _create_full_length_script_data(sample_script_data, word_count_per_scene=45, scene_count=30)
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(long_data, settings, enforce_full_length=True)
    assert "outside allowed range [950, 1150]" in str(exc.value)


def test_validate_too_few_scenes_fails(sample_script_data):
    """Scripts with fewer than 15 scenes fail full validation."""
    settings = get_settings("config/config.yaml")
    # 10 scenes
    data = _create_full_length_script_data(sample_script_data, word_count_per_scene=45, scene_count=10)
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(data, settings, enforce_full_length=True)
    assert "Scene count (10) outside required 15-50 range" in str(exc.value)


def test_validate_too_many_scenes_fails(sample_script_data):
    """Scripts with more than 50 scenes fail full validation."""
    settings = get_settings("config/config.yaml")
    data = _create_full_length_script_data(sample_script_data, word_count_per_scene=20, scene_count=55)
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(data, settings, enforce_full_length=True)
    assert "Scene count (55) outside required 15-50 range" in str(exc.value)


def test_validate_title_too_short(sample_script_data):
    """Title under 40 characters fails."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["title"] = "Short Title"
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "Title length" in str(exc.value)


def test_validate_title_too_long(sample_script_data):
    """Title over 90 characters fails."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["title"] = "A" * 95
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "Title length" in str(exc.value)


def test_validate_duplicate_title_similarity_fails(sample_script_data, monkeypatch):
    """Title with high similarity to past published video fails."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    # Mock state returning this exact title in past titles
    monkeypatch.setattr(
        "autopilot.script.validate.is_title_too_similar",
        lambda title, max_similarity=0.6: (True, 0.95, "Past Similar Title Example"),
    )
    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "too similar to past title" in str(exc.value)


def test_validate_banned_compliance_phrase(sample_script_data):
    """Banned hype words trigger validation failure."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["scenes"][0]["narration"] = "This method is guaranteed to make money fast."

    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "banned compliance phrase" in str(exc.value)


def test_validate_invalid_chapter_scene(sample_script_data):
    """Non-existent chapter start scene IDs fail."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["chapters"][0]["start_scene_id"] = 999

    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "invalid scene ID 999" in str(exc.value)


def test_validate_empty_scene_narration(sample_script_data):
    """Empty scene narration triggers failure."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["scenes"][0]["narration"] = "   "

    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "empty" in str(exc.value).lower()


def test_validate_scene_narration_too_long(sample_script_data):
    """Scene narration > 50 words triggers failure."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["scenes"][0]["narration"] = "word " * 55

    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "max allowed is 50 words" in str(exc.value)


def test_validate_thumbnail_text_too_long(sample_script_data):
    """Thumbnail text > 4 words triggers failure."""
    settings = get_settings("config/config.yaml")
    bad_data = copy.deepcopy(sample_script_data)
    bad_data["thumbnail_text"] = "This Thumbnail Text Is Too Long Here"

    with pytest.raises(ScriptValidationError) as exc:
        validate_script(bad_data, settings, enforce_full_length=False)
    assert "Thumbnail text too long" in str(exc.value)
