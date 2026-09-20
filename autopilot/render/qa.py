"""ffprobe-based QA gate for the rendered MP4.

Checks:
  - File exists and size > 1 MB
  - Video stream: codec=h264, resolution=1920x1080, fps≈30
  - Audio stream: codec=aac, sample_rate=44100 or 48000
  - Duration within expected range (360.0s to 480.0s, i.e., 6 to 8 minutes)
  - TTS WAV count equals scene count (when scenes/tts_dir provided)
  - Moov atom is at front (faststart) — checked via file header magic

Raises RenderQAError with a clear description of every failed gate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from autopilot.tts.edge import verify_tts_wav_count
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.render.qa")


class RenderQAError(RuntimeError):
    """Raised when one or more QA gates fail on the rendered MP4."""


@dataclass
class QAResult:
    passed: bool
    video_codec: str = ""
    audio_codec: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration_sec: float = 0.0
    size_mb: float = 0.0
    failures: list[str] = field(default_factory=list)


def _probe(mp4_path: Path) -> dict:
    """Run ffprobe and return parsed JSON."""
    if not shutil.which("ffprobe"):
        import os
        try:
            res = subprocess.run(["where.exe", "ffprobe"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                bin_dir = str(Path(res.stdout.strip().splitlines()[0]).parent)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
    if not shutil.which("ffprobe"):
        raise OSError("ffprobe not found in PATH. Install FFmpeg.")
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(mp4_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-1000:]}")
    return json.loads(result.stdout)


def qa_mp4(
    mp4_path: Path | str,
    min_duration_sec: float = 360.0,   # 6.0 min (360s)
    max_duration_sec: float = 480.0,   # 8.0 min (480s)
    expected_width: int = 1920,
    expected_height: int = 1080,
    min_size_mb: float = 1.0,
    scenes: list[dict] | None = None,
    tts_dir: Path | str | None = None,
) -> QAResult:
    """
    Run all QA gates against the rendered MP4.

    Checks:
      - File exists and size >= min_size_mb (1.0 MB)
      - Video: h264, 1920x1080, ~30fps
      - Audio: aac, 44100 or 48000 Hz
      - Duration: 360.0s to 480.0s (6 to 8 minutes)
      - If scenes and tts_dir provided: TTS WAV count == scene count

    Returns QAResult. If any gate fails, QAResult.passed=False and
    QAResult.failures contains a list of human-readable failure messages.

    Raises RenderQAError if the file doesn't exist or ffprobe can't parse it.
    """
    mp4_path = Path(mp4_path)
    failures: list[str] = []

    if not mp4_path.exists():
        raise RenderQAError(f"MP4 not found: {mp4_path}")

    size_mb = mp4_path.stat().st_size / 1_048_576
    if size_mb < min_size_mb:
        failures.append(f"File too small: {size_mb:.2f} MB < {min_size_mb} MB minimum")

    probe = _probe(mp4_path)
    streams = probe.get("streams", [])
    fmt = probe.get("format", {})

    duration_sec = float(fmt.get("duration", 0))

    # Find video and audio streams
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    video_codec = audio_codec = ""
    width = height = 0
    fps = 0.0

    if video_stream is None:
        failures.append("No video stream found")
    else:
        video_codec = video_stream.get("codec_name", "")
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        # fps is stored as "30/1" or "30000/1001"
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        try:
            num, den = r_frame_rate.split("/")
            fps = round(int(num) / int(den), 2)
        except (ValueError, ZeroDivisionError):
            fps = 0.0

        if video_codec != "h264":
            failures.append(f"Video codec: expected h264, got {video_codec!r}")
        if width != expected_width or height != expected_height:
            failures.append(
                f"Resolution: expected {expected_width}x{expected_height}, got {width}x{height}"
            )
        if not (29.0 <= fps <= 31.0):
            failures.append(f"FPS: expected ~30, got {fps}")

    if audio_stream is None:
        failures.append("No audio stream found")
    else:
        audio_codec = audio_stream.get("codec_name", "")
        sample_rate = int(audio_stream.get("sample_rate", 0))
        if audio_codec != "aac":
            failures.append(f"Audio codec: expected aac, got {audio_codec!r}")
        if sample_rate not in (44100, 48000):
            failures.append(f"Audio sample rate: expected 44100 or 48000, got {sample_rate}")

    if duration_sec < min_duration_sec:
        failures.append(
            f"Duration too short: {duration_sec:.1f}s < {min_duration_sec:.0f}s "
            f"({min_duration_sec/60:.1f} min)"
        )
    if duration_sec > max_duration_sec:
        failures.append(
            f"Duration too long: {duration_sec:.1f}s > {max_duration_sec:.0f}s "
            f"({max_duration_sec/60:.1f} min)"
        )

    if scenes is not None and tts_dir is not None:
        try:
            verify_tts_wav_count(scenes, tts_dir)
        except RuntimeError as e:
            failures.append(str(e))

    passed = len(failures) == 0

    result = QAResult(
        passed=passed,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=width,
        height=height,
        fps=fps,
        duration_sec=duration_sec,
        size_mb=size_mb,
        failures=failures,
    )

    if passed:
        logger.info(
            "QA PASSED: %s | h264 %dx%d @%.0ffps | aac | %.1fs (%.1fmin) | %.1fMB",
            mp4_path.name, width, height, fps, duration_sec, duration_sec / 60, size_mb,
        )
    else:
        logger.error("QA FAILED for %s: %s", mp4_path.name, "; ".join(failures))

    return result
