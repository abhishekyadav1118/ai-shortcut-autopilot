"""Unit tests for configuration loading and validation."""

from autopilot.config import get_settings, load_yaml_config


def test_load_default_yaml_config():
    data = load_yaml_config("config/config.yaml")
    assert "channel" in data
    assert "video" in data
    assert data["channel"]["language"] == "en"
    assert data["video"]["resolution"] == "1920x1080"


def test_settings_defaults_and_types():
    settings = get_settings("config/config.yaml")
    assert settings.channel.niche == "AI tools tutorials and explainers"
    assert settings.channel.category_id == "28"
    assert settings.video.fps == 30
    assert settings.schedule.publish_local_time == "10:00"
    assert settings.quality.max_title_similarity == 0.6


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test_gemini_key_12345")
    monkeypatch.setenv("PEXELS_API_KEY", "test_pexels_key_67890")
    settings = get_settings("config/config.yaml")
    assert settings.llm_api_key == "test_gemini_key_12345"
    assert settings.pexels_api_key == "test_pexels_key_67890"


def test_settings_secret_paths_env_override(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_FILE", "custom_secret.json")
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", "custom_token.json")
    settings = get_settings("config/config.yaml")
    assert settings.youtube_client_secret_file == "custom_secret.json"
    assert settings.youtube_token_file == "custom_token.json"

