"""Render package exports."""

from autopilot.render.assemble import assemble_video
from autopilot.render.audio import select_background_music
from autopilot.render.cards import render_all_cards, render_text_card
from autopilot.render.qa import QAResult, RenderQAError, qa_mp4, verify_tts_wav_count
from autopilot.render.subtitles import generate_srt

__all__ = [
    "assemble_video",
    "select_background_music",
    "render_text_card",
    "render_all_cards",
    "generate_srt",
    "qa_mp4",
    "verify_tts_wav_count",
    "QAResult",
    "RenderQAError",
]
