"""FFprobe helper utilities for media inspection and quality checks."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg binary exists in PATH."""
    return shutil.which("ffmpeg") is not None


def is_ffprobe_available() -> bool:
    """Check if ffprobe binary exists in PATH."""
    return shutil.which("ffprobe") is not None


def run_ffprobe_json(file_path: str | Path) -> dict[str, Any]:
    """Execute ffprobe and return parsed JSON metadata."""
    if not is_ffprobe_available():
        raise FileNotFoundError("ffprobe is not installed or not found in system PATH")

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def get_media_duration(file_path: str | Path) -> float:
    """Get precise duration of an audio or video file in seconds."""
    data = run_ffprobe_json(file_path)
    format_info = data.get("format", {})
    return float(format_info.get("duration", 0.0))
