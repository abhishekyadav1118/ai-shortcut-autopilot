"""Command Line Interface for ai-tools-yt-autopilot."""

import argparse
import shutil
import sys
from pathlib import Path

from autopilot.config import get_settings
from autopilot.models import DoctorCheckResult
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.cli")


def run_doctor() -> int:
    """Perform system, prerequisite, environment, and asset checks."""
    print("=" * 65)
    print(" AI Tools YouTube Autopilot - System Diagnostic (Doctor)")
    print("=" * 65)

    checks: list[DoctorCheckResult] = []

    # 1. Python Version
    py_version = sys.version_info
    if py_version >= (3, 11):
        checks.append(
            DoctorCheckResult(
                name="Python Version",
                status="OK",
                message=f"Python {py_version.major}.{py_version.minor}.{py_version.micro} (>= 3.11)",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="Python Version",
                status="ERROR",
                message=f"Python {py_version.major}.{py_version.minor} is below 3.11",
                fix_hint="Install Python 3.11 or higher.",
            )
        )

    # 2. FFmpeg & FFprobe
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        checks.append(
            DoctorCheckResult(
                name="FFmpeg Binary",
                status="OK",
                message=f"Found at {ffmpeg_bin}",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="FFmpeg Binary",
                status="WARNING",
                message="FFmpeg not found in system PATH",
                fix_hint="Install FFmpeg (e.g., winget install Gyan.FFmpeg or apt install ffmpeg)",
            )
        )

    ffprobe_bin = shutil.which("ffprobe")
    if ffprobe_bin:
        checks.append(
            DoctorCheckResult(
                name="FFprobe Binary",
                status="OK",
                message=f"Found at {ffprobe_bin}",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="FFprobe Binary",
                status="WARNING",
                message="FFprobe not found in system PATH",
                fix_hint="Install FFprobe / FFmpeg package.",
            )
        )

    # 3. Configuration Files
    config_files = [
        ("config/config.yaml", True),
        ("config/feeds.yaml", True),
        ("config/evergreen_topics.yaml", True),
        ("config/pronunciation.yaml", True),
        ("prompts/topic_rank.md", True),
        ("prompts/script.md", True),
        ("prompts/factcheck.md", True),
        ("prompts/formats.yaml", True),
    ]
    for cfg_path, required in config_files:
        p = Path(cfg_path)
        if p.exists():
            checks.append(
                DoctorCheckResult(
                    name=f"Config: {cfg_path}",
                    status="OK",
                    message="Present and readable",
                )
            )
        else:
            checks.append(
                DoctorCheckResult(
                    name=f"Config: {cfg_path}",
                    status="ERROR" if required else "WARNING",
                    message="File missing",
                    fix_hint=f"Create {cfg_path}",
                )
            )

    # 4. Music Assets (Optional)
    music_dir = Path("assets/music")
    music_files = (
        list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav")) if music_dir.exists() else []
    )
    if music_files:
        checks.append(
            DoctorCheckResult(
                name="Background Music",
                status="OK",
                message=f"Found {len(music_files)} track(s) in {music_dir}",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="Background Music",
                status="OK",
                message="No music files in assets/music/ (optional, will render voice-only)",
            )
        )

    # 5. Environment Variables & Secrets
    settings = get_settings()

    # LLM Key
    if settings.llm_api_key:
        checks.append(
            DoctorCheckResult(
                name="LLM API Key (LLM_API_KEY)",
                status="OK",
                message="Configured",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="LLM API Key (LLM_API_KEY)",
                status="WARNING",
                message="Not set in environment or .env",
                fix_hint="Get a free Gemini API key from Google AI Studio or Anthropic and add to .env",
            )
        )

    # Pexels Key
    if settings.pexels_api_key:
        checks.append(
            DoctorCheckResult(
                name="Pexels Key (PEXELS_API_KEY)",
                status="OK",
                message="Configured",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="Pexels Key (PEXELS_API_KEY)",
                status="WARNING",
                message="Not set in environment or .env",
                fix_hint="Get a free key from pexels.com/api and add PEXELS_API_KEY to .env",
            )
        )

    # YouTube Secrets
    yt_secrets = [
        ("YOUTUBE_CLIENT_ID", settings.youtube_client_id),
        ("YOUTUBE_CLIENT_SECRET", settings.youtube_client_secret),
        ("YOUTUBE_REFRESH_TOKEN", settings.youtube_refresh_token),
    ]
    for secret_name, secret_val in yt_secrets:
        if secret_val:
            checks.append(
                DoctorCheckResult(
                    name=f"YouTube Secret ({secret_name})",
                    status="OK",
                    message="Configured",
                )
            )
        else:
            checks.append(
                DoctorCheckResult(
                    name=f"YouTube Secret ({secret_name})",
                    status="WARNING",
                    message="Not set (required only for live YouTube upload)",
                    fix_hint=f"Set {secret_name} in .env or use 'python -m autopilot auth'",
                )
            )

    # Telegram (Optional)
    if settings.telegram_bot_token and settings.telegram_chat_id:
        checks.append(
            DoctorCheckResult(
                name="Telegram Bot Notifications",
                status="OK",
                message="Configured",
            )
        )
    else:
        checks.append(
            DoctorCheckResult(
                name="Telegram Bot Notifications",
                status="OK",
                message="Optional notifications not configured",
            )
        )

    # Output Summary Table
    errors_count = 0
    warnings_count = 0
    print(f"\n{'STATUS':<10} | {'CHECK ITEM':<32} | {'DETAILS / FIX HINT'}")
    print("-" * 80)
    for c in checks:
        if c.status == "OK":
            status_str = "[OK]    "
        elif c.status == "WARNING":
            status_str = "[WARN]  "
            warnings_count += 1
        else:
            status_str = "[ERROR] "
            errors_count += 1

        details = c.message
        if c.fix_hint:
            details += f" -> Hint: {c.fix_hint}"
        print(f"{status_str:<10} | {c.name:<32} | {details}")

    print("=" * 80)
    print(f" Summary: {len(checks)} checks completed. {errors_count} error(s), {warnings_count} warning(s).\n")

    if errors_count > 0:
        return 1
    return 0


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="autopilot",
        description="AI Tools YouTube Autopilot - Daily Automated Content Pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # doctor command
    subparsers.add_parser("doctor", help="Inspect environment, dependencies, tools and assets")

    # auth command
    subparsers.add_parser("auth", help="Perform one-time YouTube OAuth Desktop App authentication")

    # run command
    run_parser = subparsers.add_parser("run", help="Execute the daily automated pipeline")
    run_parser.add_argument(
        "--mode",
        choices=["review", "auto", "package"],
        default=None,
        help="Publish mode override (review | auto | package)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute pipeline without paid/external side effects or uploads",
    )
    run_parser.add_argument(
        "--topic-url",
        type=str,
        default=None,
        help="Force pipeline to run on a specific article URL",
    )
    run_parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="Run pipeline using a local script JSON fixture",
    )

    # render-fixture command
    rf_parser = subparsers.add_parser(
        "render-fixture",
        help="Render video completely offline from a script fixture without external API calls",
    )
    rf_parser.add_argument(
        "fixture_path",
        type=str,
        help="Path to script JSON fixture (e.g. tests/fixtures/sample_script.json)",
    )

    args = parser.parse_args()

    if args.command == "doctor":
        exit_code = run_doctor()
        sys.exit(exit_code)
    elif args.command == "auth":
        print("OAuth flow will be initialized in Phase 3. Please run 'doctor' for diagnostics.")
    elif args.command == "run":
        print(f"Pipeline run invoked with mode={args.mode}, dry_run={args.dry_run}. Modules load in subsequent phases.")
    elif args.command == "render-fixture":
        print(f"Render fixture invoked with path={args.fixture_path}.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
