"""YouTube Data API v3 upload module.

Handles OAuth authentication, resumable video uploading (chunked),
caption/subtitle insertion, and input validation.
Default privacy status is PRIVATE.
Supports --dry-run mode to validate inputs without network/API calls.
"""

from __future__ import annotations

import argparse
import http.client
import os
import random
import socket
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from autopilot.config import get_settings
from autopilot.utils.logging import get_logger

logger = get_logger("autopilot.upload.youtube")

# YouTube API scopes needed for video and captions management
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Retriable status codes and exceptions for resumable uploads
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
RETRIABLE_EXCEPTIONS = (
    HttpError,
    http.client.HTTPException,
    socket.error,
    socket.timeout,
    IOError,
)

MAX_RETRIES = 5


@dataclass
class UploadResult:
    """Result returned from an upload operation."""

    success: bool
    video_id: str | None = None
    url: str | None = None
    privacy_status: str = "private"
    dry_run: bool = False
    caption_uploaded: bool = False
    error: str | None = None


def validate_upload_inputs(
    video_path: Path | str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    subtitles_path: Path | str | None = None,
    privacy_status: str = "private",
    publish_at: str | None = None,
) -> None:
    """Validate all video upload inputs before contacting the YouTube API.

    Raises ValueError if any input violates YouTube API requirements.
    """
    # 1. Video file validation
    v_path = Path(video_path)
    if not v_path.exists():
        raise ValueError(f"Video file not found: {v_path}")
    if not v_path.is_file():
        raise ValueError(f"Video path is not a file: {v_path}")
    if v_path.stat().st_size == 0:
        raise ValueError(f"Video file is empty (0 bytes): {v_path}")

    # 2. Title validation (YouTube limit is 100 characters)
    stripped_title = title.strip()
    if not stripped_title:
        raise ValueError("Video title cannot be empty.")
    if len(stripped_title) > 100:
        raise ValueError(
            f"Video title exceeds YouTube limit of 100 characters: {len(stripped_title)} chars."
        )

    # 3. Description validation (YouTube limit is 5000 characters)
    if len(description) > 5000:
        raise ValueError(
            f"Video description exceeds YouTube limit of 5000 characters: {len(description)} chars."
        )

    # 4. Tags validation (YouTube limit is 500 characters total comma-separated)
    if tags:
        tags_str = ",".join(tags)
        if len(tags_str) > 500:
            raise ValueError(
                f"Video tags exceed YouTube total character limit of 500: {len(tags_str)} chars."
            )

    # 5. Subtitles validation (optional)
    if subtitles_path is not None:
        sub_path = Path(subtitles_path)
        if not sub_path.exists():
            raise ValueError(f"Subtitles file not found: {sub_path}")
        if not sub_path.is_file():
            raise ValueError(f"Subtitles path is not a file: {sub_path}")
        if sub_path.stat().st_size == 0:
            raise ValueError(f"Subtitles file is empty (0 bytes): {sub_path}")

    # 6. Privacy status validation
    valid_statuses = ("private", "unlisted", "public")
    if privacy_status.lower() not in valid_statuses:
        raise ValueError(
            f"Invalid privacy_status: {privacy_status!r}. Must be one of {valid_statuses}."
        )

    # 7. Scheduled publish_at validation
    if publish_at is not None:
        try:
            pub_clean = publish_at.replace("Z", "+00:00")
            pub_dt = datetime.fromisoformat(pub_clean)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            now_utc = datetime.now(timezone.utc)
            if pub_dt <= now_utc:
                raise ValueError(
                    f"Scheduled publish_at time must be in the future: {publish_at} <= {now_utc.isoformat()}"
                )
        except (ValueError, TypeError) as e:
            if "must be in the future" in str(e):
                raise
            raise ValueError(
                f"Invalid publish_at timestamp format: {publish_at!r}. Must be valid ISO 8601 UTC."
            ) from e


def get_authenticated_service(credentials: Any | None = None) -> Resource:
    """Build and return an authenticated YouTube Data API v3 service resource.

    Never prints or logs secret credentials or tokens.
    """
    if credentials is not None:
        logger.info("Using provided credentials for YouTube service.")
        return build("youtube", "v3", credentials=credentials)

    settings = get_settings()

    # 1. Environment / Settings OAuth credentials
    if settings.youtube_refresh_token and settings.youtube_client_id and settings.youtube_client_secret:
        logger.info("Initializing YouTube credentials from environment settings.")
        creds = Credentials(
            token=None,
            refresh_token=settings.youtube_refresh_token,
            client_id=settings.youtube_client_id,
            client_secret=settings.youtube_client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=YOUTUBE_SCOPES,
        )
        return build("youtube", "v3", credentials=creds)

    # 2. Local token file (from YOUTUBE_TOKEN_FILE env var or settings, falling back to token.json)
    token_file_path = Path(
        os.environ.get("YOUTUBE_TOKEN_FILE")
        or getattr(settings, "youtube_token_file", "token.json")
    )
    if token_file_path.exists():
        logger.info("Initializing YouTube credentials from token file: %s", token_file_path)
        creds = Credentials.from_authorized_user_file(str(token_file_path), YOUTUBE_SCOPES)
        return build("youtube", "v3", credentials=creds)

    # 3. Local client secret file (from YOUTUBE_CLIENT_SECRET_FILE env var or settings, falling back to client_secret.json)
    secret_file_path = Path(
        os.environ.get("YOUTUBE_CLIENT_SECRET_FILE")
        or getattr(settings, "youtube_client_secret_file", "client_secret.json")
    )
    if secret_file_path.exists():
        logger.info("Running OAuth installed app flow with client secret file: %s", secret_file_path)
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(secret_file_path), YOUTUBE_SCOPES)
        creds = flow.run_local_server(port=0)
        # Save token for subsequent runs
        token_file_path.write_text(creds.to_json(), encoding="utf-8")
        return build("youtube", "v3", credentials=creds)

    raise RuntimeError(
        "No valid YouTube credentials found. Configure YOUTUBE_REFRESH_TOKEN, "
        "YOUTUBE_CLIENT_ID, and YOUTUBE_CLIENT_SECRET in .env, or provide client_secret.json."
    )


def _resumable_upload(insert_request: Any) -> dict:
    """Execute a resumable media upload with exponential backoff on transient errors."""
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info("Upload progress: %d%%", progress)
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"Retriable HTTP error {e.resp.status}: {e}"
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"Retriable network exception: {e}"

        if error:
            retry += 1
            if retry > MAX_RETRIES:
                raise RuntimeError(f"Maximum upload retries ({MAX_RETRIES}) exceeded: {error}")
            sleep_sec = (2 ** retry) + (random.randint(0, 1000) / 1000)
            logger.warning(
                "Upload transient error encountered (%s). Retrying in %.2fs (attempt %d/%d)...",
                error,
                sleep_sec,
                retry,
                MAX_RETRIES,
            )
            time.sleep(sleep_sec)
            error = None

    return response


def upload_subtitles(
    youtube: Resource,
    video_id: str,
    subtitles_path: Path | str,
    language: str = "en",
    name: str = "English",
) -> bool:
    """Upload an SRT caption file to a YouTube video after updating video default languages.

    1. Calls videos().list(part="snippet", id=video_id) to read existing metadata.
    2. Calls videos().update(part="snippet") to set snippet.defaultLanguage and
       snippet.defaultAudioLanguage to language, keeping title, description, tags, categoryId unchanged.
    3. Calls captions().insert(part="snippet") with videoId, language, name, isDraft=False.
    4. Calls captions().list(part="snippet", videoId=video_id) and logs track language and status.

    Returns True on success, False on error.
    """
    sub_path = Path(subtitles_path)
    if not sub_path.exists() or sub_path.stat().st_size == 0:
        logger.warning("Subtitles file %s does not exist or is empty. Skipping.", sub_path)
        return False

    try:
        # Step 1: Read existing snippet with videos().list and update default languages
        list_resp = youtube.videos().list(
            part="snippet",
            id=video_id,
        ).execute()

        items = list_resp.get("items", [])
        if items:
            snippet = items[0].get("snippet", {})
            snippet["defaultLanguage"] = language
            snippet["defaultAudioLanguage"] = language
            youtube.videos().update(
                part="snippet",
                body={
                    "id": video_id,
                    "snippet": snippet,
                },
            ).execute()
            logger.info(
                "Updated video %s defaultLanguage and defaultAudioLanguage to %r.",
                video_id,
                language,
            )
        else:
            logger.warning("Video %s snippet not found during language update.", video_id)

        # Step 2: In captions().insert send snippet with videoId, language, name, isDraft=False
        logger.info("Uploading subtitles (%s) for video %s...", sub_path.name, video_id)
        caption_body = {
            "snippet": {
                "videoId": video_id,
                "language": language,
                "name": name,
                "isDraft": False,
            }
        }
        media = MediaFileUpload(
            str(sub_path),
            mimetype="application/x-subrip",
            resumable=True,
        )

        request = youtube.captions().insert(
            part="snippet",
            body=caption_body,
            media_body=media,
        )
        _resumable_upload(request)
        logger.info("Successfully uploaded captions for video %s.", video_id)

        # Step 3: Call captions().list(part="snippet", videoId=video_id) and log track language and status
        cap_list_resp = youtube.captions().list(
            part="snippet",
            videoId=video_id,
        ).execute()

        for track in cap_list_resp.get("items", []):
            snip = track.get("snippet", {})
            t_lang = snip.get("language")
            t_status = snip.get("status")
            t_name = snip.get("name")
            logger.info(
                "Caption track verified: videoId=%s language=%s name=%s status=%s",
                video_id,
                t_lang,
                t_name,
                t_status,
            )

        return True
    except Exception as e:
        logger.error("Failed to upload captions for video %s: %s", video_id, e)
        return False


def upload_video(
    video_path: Path | str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    subtitles_path: Path | str | None = None,
    privacy_status: str = "private",
    publish_at: str | None = None,
    category_id: str = "28",
    made_for_kids: bool = False,
    language: str = "en",
    dry_run: bool = False,
    credentials: Any | None = None,
) -> UploadResult:
    """Upload a video and optional subtitles to YouTube.

    Default privacy is PRIVATE. Default language is 'en'.
    If publish_at is set, privacy_status is overridden to 'private' and publishAt is sent in status.
    If dry_run is True, validates all inputs and returns without contacting the API.
    """
    if tags is None:
        tags = []

    if publish_at:
        privacy_status = "private"

    # 1. Validate inputs unconditionally
    validate_upload_inputs(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        subtitles_path=subtitles_path,
        privacy_status=privacy_status,
        publish_at=publish_at,
    )

    # 2. Dry-run early exit
    if dry_run:
        logger.info("[DRY-RUN] Inputs validated successfully. Skipping API upload.")
        logger.info(
            "[DRY-RUN] Video: %s | Title: %s | Privacy: %s | Language: %s | PublishAt: %s",
            Path(video_path).name,
            title,
            privacy_status,
            language,
            publish_at,
        )
        fake_id = "dry_run_sample_id_123"
        return UploadResult(
            success=True,
            video_id=fake_id,
            url=f"https://youtu.be/{fake_id}",
            privacy_status=privacy_status,
            dry_run=True,
            caption_uploaded=bool(subtitles_path),
        )

    # 3. Authenticate and initialize client
    youtube = get_authenticated_service(credentials=credentials)

    # 4. Prepare upload metadata
    status_body: dict[str, Any] = {
        "privacyStatus": privacy_status.lower(),
        "selfDeclaredMadeForKids": made_for_kids,
    }
    if publish_at:
        pub_clean = publish_at.replace("Z", "+00:00")
        pub_dt = datetime.fromisoformat(pub_clean)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        status_body["publishAt"] = pub_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    body = {
        "snippet": {
            "title": title.strip(),
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": status_body,
    }

    # Resumable chunk size: 4MB
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=1024 * 1024 * 4,
        resumable=True,
    )

    logger.info(
        "Starting resumable upload for '%s' (privacy: %s, language: %s)...",
        title,
        privacy_status,
        language,
    )

    try:
        insert_request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = _resumable_upload(insert_request)
        video_id = response.get("id")
        video_url = f"https://youtu.be/{video_id}"
        logger.info("Video successfully uploaded! ID: %s (URL: %s)", video_id, video_url)

        # 5. Upload subtitles if provided
        caption_ok = False
        if subtitles_path is not None and video_id:
            caption_name = "English" if language == "en" else language.upper()
            caption_ok = upload_subtitles(
                youtube,
                video_id,
                subtitles_path,
                language=language,
                name=caption_name,
            )

        return UploadResult(
            success=True,
            video_id=video_id,
            url=video_url,
            privacy_status=privacy_status,
            dry_run=False,
            caption_uploaded=caption_ok,
        )

    except Exception as e:
        logger.error("Failed to upload video to YouTube: %s", e)
        return UploadResult(
            success=False,
            error=str(e),
            privacy_status=privacy_status,
            dry_run=False,
        )


# Alias
upload_to_youtube = upload_video


def main() -> None:
    """CLI entrypoint for YouTube upload."""
    parser = argparse.ArgumentParser(
        description="YouTube Data API v3 Video Uploader with Subtitles and Resumable Uploads",
    )
    parser.add_argument(
        "--video",
        type=Path,
        required=True,
        help="Path to the MP4 video file to upload",
    )
    parser.add_argument(
        "--subtitles",
        type=Path,
        default=None,
        help="Path to the SRT subtitle file to upload",
    )
    parser.add_argument(
        "--title",
        type=str,
        required=True,
        help="Title of the video (max 100 characters)",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Description of the video (max 5000 characters)",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        default=[],
        help="Space-separated list of tags",
    )
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default="private",
        help="Privacy status (default: private)",
    )
    parser.add_argument(
        "--publish-at",
        type=str,
        default=None,
        help="ISO 8601 UTC timestamp for scheduled publishing (e.g. 2026-10-01T12:00:00Z)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="Language code for video and subtitles (default: en)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs without calling YouTube API",
    )

    args = parser.parse_args()

    result = upload_video(
        video_path=args.video,
        title=args.title,
        description=args.description,
        tags=args.tags,
        subtitles_path=args.subtitles,
        privacy_status=args.privacy,
        publish_at=args.publish_at,
        language=args.language,
        dry_run=args.dry_run,
    )

    if result.success:
        print(f"SUCCESS: video_id={result.video_id} url={result.url} privacy={result.privacy_status}")
        sys.exit(0)
    else:
        print(f"ERROR: {result.error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
