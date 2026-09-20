"""SRT subtitle generation from scene timings."""

from __future__ import annotations

from pathlib import Path

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.render.subtitles")


def _format_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp HH:MM:SS,mmm."""
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(scenes: list[dict], out_path: Path | str) -> Path:
    """
    Generate an SRT subtitle file from scene list.

    Each scene's narration becomes one subtitle entry spanning its duration.
    Scenes must have `duration_sec` populated (set by TTS pass).
    Long narrations (> 15 words) are split into two lines at the midpoint.

    Returns the path to the written SRT file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    entries: list[str] = []
    cursor: float = 0.0

    for i, scene in enumerate(scenes, start=1):
        dur = scene.get("duration_sec", 5.0)
        narration = scene.get("narration", "").strip()
        start_ts = _format_srt_time(cursor)
        end_ts = _format_srt_time(cursor + dur)

        # Split long narrations into two subtitle lines
        words = narration.split()
        if len(words) > 15:
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            text = f"{line1}\n{line2}"
        else:
            text = narration

        entries.append(f"{i}\n{start_ts} --> {end_ts}\n{text}\n")
        cursor += dur

    srt_content = "\n".join(entries)
    out_path.write_text(srt_content, encoding="utf-8")

    logger.info(
        "Generated SRT: %d entries, total %.1fs -> %s",
        len(entries), cursor, out_path.name,
    )
    return out_path
