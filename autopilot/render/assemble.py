"""FFmpeg-based video assembly pipeline.

Stages:
  1. Per-scene: card PNG → looped video clip (duration = TTS audio length)
  2. Per-scene: mux audio (WAV) + video clip → scene MP4
  3. Concat all scene MP4s via FFmpeg concat demuxer
  4. Loudness normalise the mix (EBU R128, target -14 LUFS)
  5. Optional: mix background music under voice (-24 dBFS ducked)
  6. Encode final 1920×1080 H.264/AAC MP4 with faststart

All FFmpeg calls are logged at DEBUG level. Any non-zero exit code raises RuntimeError.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.render.assemble")

# ── helpers ──────────────────────────────────────────────────────────────────

def _ffmpeg(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run an FFmpeg command. Raises RuntimeError on failure."""
    cmd = ["ffmpeg", "-y", *args]
    logger.debug("FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed (exit {result.returncode}):\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR: {result.stderr[-2000:]}"
        )
    return result


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        import os
        try:
            res = subprocess.run(["where.exe", "ffmpeg"], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                bin_dir = str(Path(res.stdout.strip().splitlines()[0]).parent)
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
    if not shutil.which("ffmpeg"):
        raise OSError(
            "FFmpeg not found in PATH. Install FFmpeg 6+ (winget install Gyan.FFmpeg)."
        )


# ── Stage 1+2: per-scene clip ─────────────────────────────────────────────────

def _build_scene_clip(
    card_png: Path,
    audio_wav: Path,
    duration_sec: float,
    out_mp4: Path,
    fps: int = 30,
) -> Path:
    """
    Create one scene MP4: static card image looped for `duration_sec` + voice WAV.
    Uses libx264 + aac. Pad audio to exact video duration with apad filter.
    """
    _ffmpeg(
        "-loop", "1",
        "-framerate", str(fps),
        "-i", str(card_png),
        "-i", str(audio_wav),
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[v];"
        "[1:a]apad[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-t", f"{duration_sec:.3f}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-shortest",
        str(out_mp4),
    )
    return out_mp4


# ── Stage 3: concat ───────────────────────────────────────────────────────────

def _concat_clips(clip_paths: list[Path], out_mp4: Path, work_dir: Path) -> Path:
    """Concatenate scene clips using the FFmpeg concat demuxer (stream copy)."""
    concat_list = work_dir / "concat.txt"
    lines = [f"file '{p.resolve().as_posix()}'" for p in clip_paths]
    concat_list.write_text("\n".join(lines), encoding="utf-8")

    _ffmpeg(
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out_mp4),
    )
    return out_mp4


# ── Stage 4: loudness normalise ───────────────────────────────────────────────

def _loudnorm(
    in_mp4: Path,
    out_mp4: Path,
    target_lufs: float = -14.0,
) -> Path:
    """Two-pass EBU R128 loudness normalisation (voice + music mix)."""
    # Pass 1: measure
    result = subprocess.run(
        [
            "ffmpeg", "-i", str(in_mp4),
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    # Parse JSON from stderr (ffmpeg always prints loudnorm JSON to stderr)
    import json
    import re
    m = re.search(r"\{[^{}]+\}", result.stderr, re.DOTALL)
    if not m:
        logger.warning("loudnorm pass-1 JSON not found; using linear normalise fallback.")
        _ffmpeg(
            "-i", str(in_mp4),
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000",
            str(out_mp4),
        )
        return out_mp4

    ln = json.loads(m.group())
    # Pass 2: normalise with measured values
    af = (
        f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
        f":measured_I={ln['input_i']}"
        f":measured_LRA={ln['input_lra']}"
        f":measured_TP={ln['input_tp']}"
        f":measured_thresh={ln['input_thresh']}"
        f":offset={ln['target_offset']}"
        f":linear=true:print_format=summary"
    )
    _ffmpeg(
        "-i", str(in_mp4),
        "-af", af,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000",
        str(out_mp4),
    )
    return out_mp4


# ── Stage 5: optional music mix ───────────────────────────────────────────────

def _mix_music(
    voice_mp4: Path,
    music_path: Path,
    out_mp4: Path,
    music_vol_db: float = -24.0,
) -> Path:
    """
    Duck background music under the voice track.
    Music is looped to video length, then mixed at music_vol_db.
    """
    _ffmpeg(
        "-i", str(voice_mp4),
        "-stream_loop", "-1",
        "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume={music_vol_db}dB[music];"
        f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000",
        "-shortest",
        str(out_mp4),
    )
    return out_mp4


# ── Stage 6: faststart ────────────────────────────────────────────────────────

def _add_faststart(in_mp4: Path, out_mp4: Path) -> Path:
    """Move moov atom to front of file for instant web playback."""
    _ffmpeg(
        "-i", str(in_mp4),
        "-c", "copy",
        "-movflags", "+faststart",
        str(out_mp4),
    )
    return out_mp4


# ── Public entry point ────────────────────────────────────────────────────────

def assemble_video(
    scenes: list[dict],
    work_dir: Path | str,
    out_dir: Path | str,
    fps: int = 30,
    target_lufs: float = -14.0,
    music_path: Path | None = None,
    music_vol_db: float = -24.0,
) -> Path:
    """
    Full FFmpeg assembly pipeline.

    scenes must have:
      - id (int)
      - video_path (str): PNG card path
      - audio_path (str): WAV path
      - duration_sec (float)

    Returns path to final MP4 in out_dir.
    """
    _require_ffmpeg()

    work_dir = Path(work_dir)
    out_dir = Path(out_dir)
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Verify TTS WAV count == scene count
    tts_dir = work_dir / "tts"
    if tts_dir.exists():
        from autopilot.tts.edge import verify_tts_wav_count
        verify_tts_wav_count(scenes, tts_dir)

    # Stage 1+2: per-scene clips
    clip_paths: list[Path] = []
    for s in scenes:
        clip = clips_dir / f"clip_{s['id']:03d}.mp4"
        audio_wav = Path(s["audio_path"])
        # Rebuild clip if it doesn't exist, is too small, or the source WAV is newer
        clip_stale = (
            not clip.exists()
            or clip.stat().st_size < 1000
            or (audio_wav.exists() and audio_wav.stat().st_mtime > clip.stat().st_mtime)
        )
        if clip_stale:
            _build_scene_clip(
                card_png=Path(s["video_path"]),
                audio_wav=Path(s["audio_path"]),
                duration_sec=s["duration_sec"],
                out_mp4=clip,
                fps=fps,
            )
        clip_paths.append(clip)
        logger.info("Built clip %d/%d (%.1fs)", s["id"], len(scenes), s["duration_sec"])

    # Stage 3: concat
    raw_concat = work_dir / "concat_raw.mp4"
    _concat_clips(clip_paths, raw_concat, work_dir)
    logger.info("Concatenated %d clips -> concat_raw.mp4", len(clip_paths))

    # Stage 4: loudness normalise voice
    normed = work_dir / "normed.mp4"
    _loudnorm(raw_concat, normed, target_lufs)
    logger.info("Loudness normalised -> normed.mp4 (target %.0f LUFS)", target_lufs)

    # Stage 5: optional music
    if music_path and music_path.exists():
        mixed = work_dir / "mixed.mp4"
        _mix_music(normed, music_path, mixed, music_vol_db)
        logger.info("Mixed background music -> mixed.mp4")
        pre_final = mixed
    else:
        pre_final = normed

    # Stage 6: faststart + final rename
    final_mp4 = out_dir / "final.mp4"
    _add_faststart(pre_final, final_mp4)

    size_mb = final_mp4.stat().st_size / 1_048_576
    logger.info(
        "Assembly complete -> %s (%.1f MB)", final_mp4, size_mb
    )
    return final_mp4
