"""Full automated video production pipeline orchestrator.

Executes script synthesis, TTS generation, text card rendering, subtitle generation,
FFmpeg video assembly, ffprobe QA gate verification, and YouTube upload in sequence.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from autopilot.config import get_settings
from autopilot.llm import get_llm_provider
from autopilot.models import Topic
from autopilot.render.assemble import assemble_video
from autopilot.render.cards import render_all_cards
from autopilot.render.qa import RenderQAError, qa_mp4
from autopilot.render.subtitles import generate_srt
from autopilot.script.generate import generate_and_validate_script
from autopilot.tts.edge import synthesise_scenes
from autopilot.upload.youtube import upload_video
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.run")


def run_pipeline(
    topic: str,
    dry_run: bool = False,
    privacy: str = "private",
    publish_at: str | None = None,
    thumbnail_path: Path | str | None = None,
    work_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Execute end-to-end autopilot pipeline.

    Order:
      1. Script synthesis & fact-check
      2. Edge-TTS narration audio synthesis
      3. Text card image rendering
      4. SRT subtitle generation
      5. FFmpeg video assembly
      6. QA gate verification (ffprobe)
      7. YouTube video upload

    Stops immediately on any failure. Never uploads a video that fails QA.
    """
    pipeline_start = time.perf_counter()

    work_path = Path(work_dir) if work_dir else Path("out/pipeline_work")
    out_path = Path(out_dir) if out_dir else Path("out/pipeline_out")

    work_path.mkdir(parents=True, exist_ok=True)
    out_path.mkdir(parents=True, exist_ok=True)

    settings = get_settings()

    # 1. Script Generation
    logger.info("--- Step 1/7: Script Generation ---")
    t0 = time.perf_counter()
    topic_obj = Topic(title=topic)
    llm = get_llm_provider(settings)
    script = generate_and_validate_script(topic_obj, settings, llm)
    t1 = time.perf_counter()
    logger.info("Step 1/7 (Script) completed in %.2fs. Title: %s", t1 - t0, script.title)

    scenes = [s.model_dump() for s in script.scenes]

    # 2. TTS Audio
    logger.info("--- Step 2/7: TTS Synthesis ---")
    t0 = time.perf_counter()
    scenes = synthesise_scenes(scenes, out_dir=work_path / "tts")
    t1 = time.perf_counter()
    logger.info("Step 2/7 (TTS) completed in %.2fs", t1 - t0)

    # 3. Cards Rendering
    logger.info("--- Step 3/7: Visual Cards Rendering ---")
    t0 = time.perf_counter()
    scenes = render_all_cards(scenes, out_dir=work_path / "cards")
    t1 = time.perf_counter()
    logger.info("Step 3/7 (Cards) completed in %.2fs", t1 - t0)

    # 4. Subtitles
    logger.info("--- Step 4/7: Subtitles Generation ---")
    t0 = time.perf_counter()
    srt_path = generate_srt(scenes, out_path=out_path / "subtitles.srt")
    t1 = time.perf_counter()
    logger.info("Step 4/7 (Subtitles) completed in %.2fs -> %s", t1 - t0, srt_path)

    # 5. FFmpeg Render
    logger.info("--- Step 5/7: FFmpeg Video Assembly ---")
    t0 = time.perf_counter()
    final_mp4 = assemble_video(scenes, work_dir=work_path, out_dir=out_path)
    t1 = time.perf_counter()
    logger.info("Step 5/7 (Render) completed in %.2fs -> %s", t1 - t0, final_mp4)

    # 6. QA Gate Check
    logger.info("--- Step 6/7: QA Gate Check ---")
    t0 = time.perf_counter()
    qa_res = qa_mp4(final_mp4, scenes=scenes, tts_dir=work_path / "tts")
    t1 = time.perf_counter()
    if not qa_res.passed:
        err_msg = f"QA Gate failed: {'; '.join(qa_res.failures)}"
        logger.error("Step 6/7 (QA) FAILED in %.2fs: %s. STOPPING PIPELINE.", t1 - t0, err_msg)
        raise RenderQAError(err_msg)
    logger.info("Step 6/7 (QA) PASSED in %.2fs", t1 - t0)

    # 7. YouTube Upload
    logger.info("--- Step 7/7: YouTube Upload ---")
    t0 = time.perf_counter()
    upload_kwargs: dict[str, Any] = {
        "video_path": final_mp4,
        "title": script.title,
        "description": script.description,
        "tags": script.tags,
        "subtitles_path": srt_path,
        "privacy_status": privacy,
        "dry_run": dry_run,
    }
    if publish_at is not None:
        upload_kwargs["publish_at"] = publish_at
    if thumbnail_path is not None:
        upload_kwargs["thumbnail_path"] = thumbnail_path

    upload_res = upload_video(**upload_kwargs)
    t1 = time.perf_counter()
    if not upload_res.success:
        err_msg = f"YouTube upload failed: {upload_res.error}"
        logger.error("Step 7/7 (Upload) FAILED in %.2fs: %s", t1 - t0, err_msg)
        raise RuntimeError(err_msg)

    logger.info("Step 7/7 (Upload) completed in %.2fs", t1 - t0)

    total_time = time.perf_counter() - pipeline_start
    logger.info("Pipeline completed successfully in %.2fs", total_time)

    return {
        "script": script,
        "video_path": final_mp4,
        "subtitles_path": srt_path,
        "qa_result": qa_res,
        "upload_result": upload_res,
        "total_time_sec": total_time,
    }


def main() -> None:
    """CLI entrypoint for running full pipeline via `python -m autopilot.run`."""
    parser = argparse.ArgumentParser(
        prog="autopilot.run",
        description="Run end-to-end AI YouTube Autopilot content pipeline",
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="Topic for script generation and video creation",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run full pipeline except real YouTube API upload",
    )
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
        help="Privacy status for YouTube upload (default: private)",
    )
    parser.add_argument(
        "--publish-at",
        type=str,
        default=None,
        help="ISO 8601 UTC timestamp for scheduled publishing (e.g. 2026-10-01T12:00:00Z)",
    )
    parser.add_argument(
        "--thumbnail",
        type=Path,
        default=None,
        help="Optional custom thumbnail image file override",
    )

    args = parser.parse_args()

    try:
        run_pipeline(
            topic=args.topic,
            dry_run=args.dry_run,
            privacy=args.privacy,
            publish_at=args.publish_at,
            thumbnail_path=args.thumbnail,
        )
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
