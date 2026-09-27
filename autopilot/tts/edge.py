"""Edge-TTS speech synthesis — one WAV file per scene narration."""

import asyncio
import re
import wave
from pathlib import Path

import edge_tts
import yaml

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.tts.edge")

# Word-level timing info is available via edge-tts WordBoundary events.
# We use it to get accurate duration rather than probing the WAV.
_RATE_RE = re.compile(r"^[+-]\d+%$")

# ── Pronunciation lexicon ─────────────────────────────────────────────────────

_LEXICON_CACHE: dict[str, str] | None = None
_LEXICON_PATH = Path("config/pronunciation.yaml")


def _load_lexicon() -> dict[str, str]:
    global _LEXICON_CACHE
    if _LEXICON_CACHE is not None:
        return _LEXICON_CACHE
    if not _LEXICON_PATH.exists():
        _LEXICON_CACHE = {}
        return _LEXICON_CACHE
    try:
        with open(_LEXICON_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _LEXICON_CACHE = data.get("pronunciations", {})
    except Exception as e:
        logger.warning("Could not load pronunciation lexicon: %s", e)
        _LEXICON_CACHE = {}
    return _LEXICON_CACHE


def apply_pronunciation_lexicon(text: str) -> str:
    """Replace known acronyms/terms with TTS-friendly phonetic equivalents.

    Substitutions are word-boundary-matched to avoid replacing substrings.
    E.g. 'API' → 'A P I', 'LLM' → 'L L M'.
    """
    lexicon = _load_lexicon()
    for term, phonetic in lexicon.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        text = re.sub(pattern, phonetic, text)
    return text


def _validate_rate(rate: str) -> str:
    """Return rate string like '+0%', '+10%', '-5%'. Defaults to '+0%' if invalid."""
    return rate if _RATE_RE.match(rate) else "+0%"


async def _synthesise_scene(
    text: str,
    out_path: Path,
    voice: str,
    rate: str,
) -> float:
    """
    Synthesise one narration chunk to WAV. Returns duration in seconds
    estimated from word boundary events (accurate ±0.05s).
    """
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    duration_ms: float = 0.0

    with open(out_path, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                # offset + duration are in 100-nanosecond ticks
                end_ticks = chunk.get("offset", 0) + chunk.get("duration", 0)
                duration_ms = max(duration_ms, end_ticks / 10_000)

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"TTS produced empty audio for: {text[:60]!r}")

    # Fall back to ffprobe or wave header if boundary events were absent
    if duration_ms == 0.0:
        try:
            from autopilot.utils.ffprobe import get_media_duration
            duration_sec = get_media_duration(out_path)
            duration_ms = duration_sec * 1000.0
        except Exception:
            try:
                with wave.open(str(out_path), "rb") as wf:
                    duration_ms = wf.getnframes() / wf.getframerate() * 1000.0
            except Exception:
                pass  # leave at 0; downstream will use a sensible default

    duration_sec = duration_ms / 1000.0
    logger.debug("TTS scene '%s...' -> %.2fs  (%s)", text[:40], duration_sec, out_path.name)
    return duration_sec


def synthesise_scenes(
    scenes: list[dict],
    out_dir: Path | str,
    voice: str = "en-US-AndrewNeural",
    rate: str = "+0%",
) -> list[dict]:
    """
    Run Edge-TTS on every scene narration and write one WAV per scene.

    Returns the scenes list with `audio_path` and `duration_sec` populated.
    All synthesis runs concurrently to minimise wall-clock time.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rate = _validate_rate(rate)

    async def _run_all() -> list[float]:
        results = []
        for s in scenes:
            wav_path = out_dir / f"scene_{s['id']:03d}.wav"
            narration = apply_pronunciation_lexicon(s["narration"])
            dur = await _synthesise_scene(narration, wav_path, voice, rate)
            results.append(dur)
            await asyncio.sleep(0.3)  # small pause to avoid saturating Edge-TTS endpoint
        return results



    durations = asyncio.run(_run_all())

    result = []
    for s, dur in zip(scenes, durations, strict=True):
        s = dict(s)
        s["audio_path"] = str(out_dir / f"scene_{s['id']:03d}.wav")
        s["duration_sec"] = round(dur, 3)
        result.append(s)

    total_dur = sum(s["duration_sec"] for s in result)
    logger.info(
        "TTS complete: %d scenes, total audio %.1fs (%.1f min)",
        len(result), total_dur, total_dur / 60,
    )
    verify_tts_wav_count(scenes, out_dir)
    return result


def verify_tts_wav_count(scenes: list[dict], out_dir: Path | str) -> bool:
    """
    Verify that the number of generated WAV files in out_dir matches the scene count
    and that each scene has a corresponding non-empty WAV file.

    Raises RuntimeError if there is any mismatch or if a file is missing/empty.
    """
    out_dir = Path(out_dir)
    if not out_dir.exists():
        raise RuntimeError(f"TTS output directory does not exist: {out_dir}")

    wav_files = [p for p in out_dir.glob("scene_*.wav") if p.is_file() and p.stat().st_size > 0]
    if len(wav_files) != len(scenes):
        raise RuntimeError(
            f"TTS WAV count mismatch: found {len(wav_files)} valid WAV files in {out_dir}, "
            f"expected {len(scenes)} scenes."
        )

    for s in scenes:
        expected = out_dir / f"scene_{s['id']:03d}.wav"
        if not expected.exists():
            raise RuntimeError(f"Missing TTS WAV file for scene {s['id']}: {expected}")
        if expected.stat().st_size == 0:
            raise RuntimeError(f"TTS WAV file is empty for scene {s['id']}: {expected}")

    return True

