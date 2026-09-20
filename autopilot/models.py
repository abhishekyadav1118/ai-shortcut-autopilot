"""Core Pydantic data models for the autopilot pipeline."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Candidate(BaseModel):
    """Candidate news or topic item from RSS/Hacker News feeds."""

    title: str
    url: str
    published: str = ""
    summary: str = ""
    source_name: str = ""
    score: float = 0.0


class Topic(BaseModel):
    """Selected topic for script synthesis."""

    title: str
    url: str = ""
    angle: str = ""
    format: str = "news_breakdown"
    why: str = ""
    target_keyword: str = ""
    source_texts: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)


class Scene(BaseModel):
    """Individual visual and audio segment in a video."""

    id: int
    narration: str
    visual_type: Literal["stock", "card", "screenshot"] = "stock"
    visual_query: str = ""
    on_screen_text: str = ""
    bullets: list[str] = Field(default_factory=list)
    source_ids: list[int] = Field(default_factory=list)
    duration_sec: float = 0.0
    audio_path: str = ""
    video_path: str = ""

    @field_validator("narration")
    @classmethod
    def validate_narration_not_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Scene narration cannot be empty")
        return cleaned


class Chapter(BaseModel):
    """YouTube chapter marker."""

    start_scene_id: int
    title: str
    start_time_sec: float = 0.0
    formatted_time: str = "00:00"


class Disclosures(BaseModel):
    """Compliance and transparency disclosures."""

    ai_voice: bool = True
    sources_listed: bool = True
    synthetic_media: bool = True


class Script(BaseModel):
    """Complete structured video script."""

    title: str
    hook: str
    scenes: list[Scene]
    chapters: list[Chapter]
    description: str
    tags: list[str]
    thumbnail_text: str
    thumbnail_visual_query: str = ""
    disclosures: Disclosures = Field(default_factory=Disclosures)

    @field_validator("scenes")
    @classmethod
    def validate_scenes_present(cls, v: list[Scene]) -> list[Scene]:
        if not v:
            raise ValueError("Script must have at least one scene")
        return v


class FactCheckClaim(BaseModel):
    """Individual factual claim evaluated against source grounding."""

    text: str
    status: Literal["SUPPORTED", "PARTIAL", "UNSUPPORTED"]
    scene_id: int = 1


class FactCheckResult(BaseModel):
    """Fact check evaluation result from LLM pass."""

    claims: list[FactCheckClaim] = Field(default_factory=list)
    unsupported_count: int = 0
    corrected_script: dict[str, Any] = Field(default_factory=dict)
    factcheck_ran: bool = False  # True only when the LLM call actually completed


class VideoPackage(BaseModel):
    """Local artifact package output."""

    output_dir: str
    video_path: str
    thumbnail_a_path: str
    thumbnail_b_path: str
    metadata_path: str
    script_path: str
    credits_path: str
    subtitles_path: str


class PublishedItem(BaseModel):
    """Record in state/published.json."""

    date: str
    topic_id: str
    source_urls: list[str] = Field(default_factory=list)
    title: str
    video_id: str = ""
    mode: str = "review"
    status: str = "success"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class DoctorCheckResult(BaseModel):
    """Individual system or prerequisite check for CLI doctor."""

    name: str
    status: Literal["OK", "WARNING", "ERROR"]
    message: str
    fix_hint: str = ""
