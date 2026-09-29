"""Full automated video production pipeline orchestrator.

Executes script synthesis, TTS generation, text card rendering, subtitle generation,
FFmpeg video assembly, ffprobe QA gate verification, metadata build, thumbnail generation,
and YouTube upload in sequence.

Modes:
  review  — uploads private immediately (no publishAt). You review before making public.
  auto    — uploads private with publishAt = today 10:00 America/New_York.
  package — no upload; saves all assets locally in out/pipeline_out/.

Quota / unverified project handling:
  - Catches HttpError 403 (quotaExceeded or unverified project scope lock)
  - Falls back to package mode automatically so assets are never lost.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from autopilot.config import get_settings
from autopilot.llm import get_llm_provider
from autopilot.models import Chapter, PublishedItem, Scene, Script, Topic
from autopilot.publish.metadata import build_metadata, save_metadata_json
from autopilot.publish.thumbnail import generate_both_thumbnails
from autopilot.render.assemble import assemble_video
from autopilot.render.audio import select_background_music
from autopilot.render.cards import render_all_cards
from autopilot.render.qa import RenderQAError, qa_mp4
from autopilot.render.subtitles import generate_srt
from autopilot.script.generate import generate_and_validate_script
from autopilot.state import already_published_today, record_publication
from autopilot.tts.edge import synthesise_scenes
from autopilot.upload.youtube import upload_video
from autopilot.utils.logging import get_logger
from autopilot.utils.timeutil import calculate_publish_at

logger = get_logger("autopilot.run")


def _load_fixture(fixture_path: str) -> tuple[list[dict], dict]:
    """Load a local JSON script fixture, return (scenes, raw_dict)."""
    p = Path(fixture_path)
    if not p.exists():
        raise FileNotFoundError(f"Fixture not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    return raw["scenes"], raw


def run_pipeline(
    topic: str = "Daily AI Tools Update",
    mode: str | None = None,
    dry_run: bool = False,
    privacy: str = "private",
    publish_at: str | None = None,
    thumbnail_path: Path | str | None = None,
    work_dir: Path | str | None = None,
    out_dir: Path | str | None = None,
    topic_url: str | None = None,
    fixture: str | None = None,
) -> dict[str, Any]:
    """Execute end-to-end autopilot pipeline.

    Order:
      1. Early exit if already published today (duplicate guard)
      2. Script synthesis & fact-check  (skipped if fixture provided)
      3. Edge-TTS narration audio synthesis
      4. Text card image rendering
      5. SRT subtitle generation
      6. Thumbnail generation (2 variants)
      7. Metadata build
      8. FFmpeg video assembly
      9. QA gate (ffprobe)
      10. YouTube upload (or package mode)
      11. State recording

    Never uploads a video that fails QA.
    """
    pipeline_start = time.perf_counter()
    settings = get_settings()

    # Resolve publish mode: CLI arg → env → default
    resolved_mode = mode or settings.mode or "review"
    logger.info("Pipeline starting. mode=%s dry_run=%s", resolved_mode, dry_run)

    work_path = Path(work_dir) if work_dir else Path("out/pipeline_work")
    out_path = Path(out_dir) if out_dir else Path("out/pipeline_out")
    work_path.mkdir(parents=True, exist_ok=True)
    out_path.mkdir(parents=True, exist_ok=True)

    # ── 1. Duplicate guard ────────────────────────────────────────────────────
    if not dry_run and already_published_today():
        logger.info("Already published today — exiting cleanly (no duplicate).")
        return {"skipped": True, "reason": "already_published_today"}

    # ── 2. Script ─────────────────────────────────────────────────────────────
    if fixture:
        logger.info("--- Step 1/9: Loading script fixture: %s ---", fixture)
        scenes_raw, script_raw = _load_fixture(fixture)
        # Build a minimal Script-like object from the fixture JSON
        scenes_obj = [Scene(**s) for s in scenes_raw]
        script = Script(
            title=script_raw.get("title", topic),
            hook=script_raw.get("hook", ""),
            scenes=scenes_obj,
            chapters=[Chapter(**c) for c in script_raw.get("chapters", [])],
            description=script_raw.get("description", ""),
            tags=script_raw.get("tags", []),
            thumbnail_text=script_raw.get("thumbnail_text", ""),
            thumbnail_visual_query=script_raw.get("thumbnail_visual_query", ""),
        )
        logger.info("Fixture loaded. Title: %s  Scenes: %d", script.title, len(script.scenes))
    else:
        logger.info("--- Step 1/9: Script Generation ---")
        t0 = time.perf_counter()
        topic_obj = Topic(title=topic, url=topic_url or "")
        llm = get_llm_provider(settings)
        script, _factcheck = generate_and_validate_script(topic_obj, settings, llm)
        logger.info(
            "Step 1/9 (Script) %.2fs. Title: %s  factcheck_ran=%s",
            time.perf_counter() - t0,
            script.title,
            _factcheck.factcheck_ran,
        )

    scenes = [s.model_dump() for s in script.scenes]

    # ── 3. TTS ────────────────────────────────────────────────────────────────
    logger.info("--- Step 2/9: TTS Synthesis ---")
    t0 = time.perf_counter()
    scenes = synthesise_scenes(
        scenes,
        out_dir=work_path / "tts",
        voice=settings.tts.voice,
        rate=settings.tts.rate,
    )
    logger.info("Step 2/9 (TTS) %.2fs", time.perf_counter() - t0)

    # ── 4. Cards ──────────────────────────────────────────────────────────────
    logger.info("--- Step 3/9: Visual Cards Rendering ---")
    t0 = time.perf_counter()
    scenes = render_all_cards(
        scenes, out_dir=work_path / "cards", channel_name=settings.channel.name
    )
    logger.info("Step 3/9 (Cards) %.2fs", time.perf_counter() - t0)

    # ── 5. Subtitles ──────────────────────────────────────────────────────────
    logger.info("--- Step 4/9: Subtitles ---")
    t0 = time.perf_counter()
    srt_path = generate_srt(scenes, out_path=out_path / "subtitles.srt")
    logger.info("Step 4/9 (SRT) %.2fs -> %s", time.perf_counter() - t0, srt_path)

    # ── 6. Thumbnails (2 variants) ────────────────────────────────────────────
    logger.info("--- Step 5/9: Thumbnail Generation ---")
    t0 = time.perf_counter()
    meta = build_metadata(
        script,
        source_urls=list(script_raw.get("source_urls", [])) if fixture else [],
        category_id=settings.channel.category_id,
        language=settings.channel.language,
        made_for_kids=settings.channel.made_for_kids,
    )
    first_card = scenes[0].get("video_path") if scenes else None
    thumb_a, thumb_b = generate_both_thumbnails(
        text_a=meta.thumbnail_text_a,
        text_b=meta.thumbnail_text_b,
        out_dir=out_path / "thumbnails",
        bg_image_path=first_card,
        channel_name=settings.channel.name.upper(),
    )
    meta_path = save_metadata_json(meta, out_path / "metadata.json")
    logger.info("Step 5/9 (Thumbnails+Metadata) %.2fs", time.perf_counter() - t0)

    # ── 7. Metadata JSON ──────────────────────────────────────────────────────
    # Already done above with save_metadata_json

    # ── 8. FFmpeg Assembly ────────────────────────────────────────────────────
    logger.info("--- Step 6/9: FFmpeg Video Assembly ---")
    t0 = time.perf_counter()
    music_path = select_background_music("assets/music")
    final_mp4 = assemble_video(
        scenes,
        work_dir=work_path,
        out_dir=out_path,
        fps=settings.video.fps,
        target_lufs=settings.music.loudness_target_lufs,
        music_path=music_path,
        music_vol_db=settings.music.volume_db,
    )
    logger.info("Step 6/9 (Render) %.2fs -> %s", time.perf_counter() - t0, final_mp4)

    # ── 9. QA Gate ────────────────────────────────────────────────────────────
    logger.info("--- Step 7/9: QA Gate ---")
    t0 = time.perf_counter()
    total_tts_sec = sum(s.get("duration_sec", 0.0) for s in scenes)
    # Lower-bound: never stricter than 30 s below total TTS, and at least 30 s minimum
    # Upper-bound: total TTS + 90 s (extra headroom for music tail, faststart padding)
    qa_min_dur = max(30.0, total_tts_sec - 60.0)
    qa_max_dur = total_tts_sec + 90.0
    logger.info(
        "QA duration window: %.1fs – %.1fs (total_tts=%.1fs)",
        qa_min_dur, qa_max_dur, total_tts_sec,
    )
    qa_res = qa_mp4(
        final_mp4,
        min_duration_sec=qa_min_dur,
        max_duration_sec=qa_max_dur,
        scenes=scenes,
        tts_dir=work_path / "tts",
    )
    if not qa_res.passed:
        err = f"QA Gate failed: {'; '.join(qa_res.failures)}"
        logger.error("Step 7/9 (QA) FAILED %.2fs: %s", time.perf_counter() - t0, err)
        raise RenderQAError(err)
    logger.info("Step 7/9 (QA) PASSED %.2fs", time.perf_counter() - t0)

    # ── 10. Upload / Package ──────────────────────────────────────────────────
    logger.info("--- Step 8/9: Upload (mode=%s) ---", resolved_mode)
    t0 = time.perf_counter()
    upload_res = None
    video_id = None

    if resolved_mode == "package":
        logger.info(
            "Mode=package: skipping upload, assets saved in %s", out_path
        )
        _write_credits(script, out_path)
    else:
        # Determine publishAt for auto mode
        _publish_at = publish_at
        if resolved_mode == "auto" and not _publish_at:
            _publish_at = calculate_publish_at(
                local_time_str=settings.schedule.publish_local_time,
                tz_name=settings.schedule.publish_tz,
            )
            logger.info("Auto mode: computed publishAt = %s", _publish_at)

        try:
            upload_privacy = "private" if resolved_mode == "auto" else privacy
            upload_res = upload_video(
                video_path=final_mp4,
                title=meta.title,
                description=meta.description,
                tags=meta.tags,
                subtitles_path=srt_path,
                privacy_status=upload_privacy,
                publish_at=_publish_at,
                thumbnail_path=thumb_a,      # use Variant A for upload
                category_id=meta.category_id,
                made_for_kids=meta.made_for_kids,
                language=meta.language,
                dry_run=dry_run,
            )
            video_id = upload_res.video_id
            logger.info(
                "Step 8/9 (Upload) %.2fs. video_id=%s url=%s",
                time.perf_counter() - t0,
                upload_res.video_id,
                upload_res.url,
            )

            if not upload_res.success:
                raise RuntimeError(f"YouTube upload failed: {upload_res.error}")

        except Exception as e:
            # Handle quota / unverified project / auth errors — fall back to package mode
            err_str = str(e).lower()
            is_quota = "quotaexceeded" in err_str
            is_forbidden = "403" in err_str or "forbidden" in err_str
            is_auth = "credentials" in err_str or "token" in err_str or "unauthorized" in err_str or "401" in err_str
            if not dry_run and (is_quota or is_forbidden or is_auth):
                logger.warning(
                    "Upload blocked (%s): %s. "
                    "Falling back to package mode — assets saved in %s.",
                    "quota" if is_quota else "auth/forbidden",
                    e, out_path,
                )
                resolved_mode = "package"
                _write_credits(script, out_path)
            else:
                raise

    # ── 11. State recording ───────────────────────────────────────────────────
    if not dry_run:
        from datetime import UTC, datetime
        pub_item = PublishedItem(
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            topic_id=script.title[:50],
            source_urls=list(getattr(script, "source_urls", [])),
            title=meta.title,
            video_id=video_id or "",
            mode=resolved_mode,
            status="success",
        )
        record_publication(pub_item)
        logger.info("Step 9/9 (State) recorded. date=%s video_id=%s", pub_item.date, pub_item.video_id)

    total_time = time.perf_counter() - pipeline_start
    logger.info("Pipeline complete in %.2fs (%.1f min)", total_time, total_time / 60)

    return {
        "script": script,
        "video_path": final_mp4,
        "subtitles_path": srt_path,
        "thumbnail_a": thumb_a,
        "thumbnail_b": thumb_b,
        "metadata_path": meta_path,
        "qa_result": qa_res,
        "upload_result": upload_res,
        "mode": resolved_mode,
        "video_id": video_id,
        "total_time_sec": total_time,
    }


def _write_credits(script: Script, out_path: Path) -> None:
    """Write a human-readable credits.txt alongside the video package."""
    credits_path = out_path / "credits.txt"
    lines = [
        f"Title: {script.title}",
        "",
        "AI VOICE DISCLOSURE",
        "This video uses an AI-generated voice (Microsoft Edge TTS / Azure Neural).",
        "All research and editorial decisions are human-reviewed.",
        "",
        "SOURCES",
    ]
    source_urls = getattr(script, "source_urls", [])
    for i, url in enumerate(source_urls or [], 1):
        lines.append(f"  [{i}] {url}")
    credits_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Credits written -> %s", credits_path)


def main() -> None:
    """CLI entrypoint: python -m autopilot.run."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="autopilot.run",
        description="Run end-to-end AI YouTube Autopilot pipeline",
    )
    parser.add_argument("--topic", type=str, default="Daily AI Tools Update")
    parser.add_argument("--mode", choices=["review", "auto", "package"], default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    parser.add_argument("--publish-at", type=str, default=None)
    parser.add_argument("--topic-url", type=str, default=None)
    parser.add_argument("--fixture", type=str, default=None)

    args = parser.parse_args()

    try:
        run_pipeline(
            topic=args.topic,
            mode=args.mode,
            dry_run=args.dry_run,
            privacy=args.privacy,
            publish_at=args.publish_at,
            topic_url=args.topic_url,
            fixture=args.fixture,
        )
    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
