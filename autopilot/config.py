"""Configuration loader and management."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConfig(BaseModel):
    name: str = "The AI Shortcut"
    niche: str = "AI tools tutorials and explainers"
    language: str = "en"
    category_id: str = "28"
    made_for_kids: bool = False


class VideoConfig(BaseModel):
    target_minutes: list[int] = Field(default_factory=lambda: [6, 8])
    word_range: list[int] = Field(default_factory=lambda: [950, 1150])
    resolution: str = "1920x1080"
    fps: int = 30


class ScheduleConfig(BaseModel):
    publish_local_time: str = "10:00"
    publish_tz: str = "America/New_York"


class LLMConfig(BaseModel):
    provider: Literal["gemini", "anthropic", "openrouter"] = "openrouter"
    model: str = "google/gemini-2.5-flash"
    temperature: float = 0.7


class TTSConfig(BaseModel):
    provider: Literal["edge", "elevenlabs"] = "edge"
    voice: str = "en-US-AndrewNeural"
    rate: str = "+0%"


class VisualsConfig(BaseModel):
    stock_provider: Literal["pexels", "pixabay"] = "pexels"
    use_screenshots: bool = False


class MusicConfig(BaseModel):
    volume_db: float = -24.0
    loudness_target_lufs: float = -14.0


class QualityConfig(BaseModel):
    max_regenerations: int = 2
    max_title_similarity: float = 0.6


class AppSettings(BaseSettings):
    """Global settings loaded from config.yaml and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment variables (Secrets)
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    pexels_api_key: str = Field(default="", alias="PEXELS_API_KEY")
    youtube_client_id: str = Field(default="", alias="YOUTUBE_CLIENT_ID")
    youtube_client_secret: str = Field(default="", alias="YOUTUBE_CLIENT_SECRET")
    youtube_refresh_token: str = Field(default="", alias="YOUTUBE_REFRESH_TOKEN")
    youtube_client_secret_file: str = Field(default="client_secret.json", alias="YOUTUBE_CLIENT_SECRET_FILE")
    youtube_token_file: str = Field(default="token.json", alias="YOUTUBE_TOKEN_FILE")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    # Mode and sub-configs
    mode: Literal["review", "auto", "package"] = "review"
    channel: ChannelConfig = Field(default_factory=ChannelConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    visuals: VisualsConfig = Field(default_factory=VisualsConfig)
    music: MusicConfig = Field(default_factory=MusicConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)

    @model_validator(mode="after")
    def resolve_environment_fallbacks(self) -> "AppSettings":
        if not self.llm_api_key:
            import os
            self.llm_api_key = (
                self.openrouter_api_key
                or os.getenv("OPENROUTER_API_KEY")
                or os.getenv("LLM_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
                or os.getenv("ANTHROPIC_API_KEY")
                or ""
            )
        self.llm_api_key = "".join(self.llm_api_key.split())
        if not self.openrouter_api_key and self.llm_api_key.startswith("sk-or-"):
            self.openrouter_api_key = self.llm_api_key
        if self.openrouter_api_key:
            self.openrouter_api_key = "".join(self.openrouter_api_key.split())
        if not self.pexels_api_key:
            import os
            self.pexels_api_key = (
                os.getenv("PEXELS_API_KEY")
                or os.getenv("PEXELS_KEY")
                or ""
            )
        if self.pexels_api_key:
            self.pexels_api_key = "".join(self.pexels_api_key.split())
        return self


def load_yaml_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load YAML config from path or default config/config.yaml."""
    if path is None:
        path = Path("config/config.yaml")
    else:
        path = Path(path)

    if not path.exists():
        return {}

    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_settings(yaml_path: Path | str | None = None) -> AppSettings:
    """Instantiate AppSettings with YAML defaults and environment variable overrides."""
    yaml_data = load_yaml_config(yaml_path)
    return AppSettings(**yaml_data)
