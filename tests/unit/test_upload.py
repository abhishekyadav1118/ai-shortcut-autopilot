"""Unit tests for autopilot.upload.youtube module with mocked YouTube Data API v3."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autopilot.upload.youtube import (
    get_authenticated_service,
    upload_subtitles,
    upload_video,
    validate_upload_inputs,
)


@pytest.fixture
def dummy_video(tmp_path: Path) -> Path:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"\x00" * 1024)
    return video


@pytest.fixture
def dummy_subtitles(tmp_path: Path) -> Path:
    sub = tmp_path / "subtitles.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello world\n", encoding="utf-8")
    return sub


# ── 1. Input Validation Tests ──────────────────────────────────────────────────


def test_validate_upload_inputs_success(dummy_video: Path, dummy_subtitles: Path):
    """Valid inputs pass without raising any exception."""
    validate_upload_inputs(
        video_path=dummy_video,
        title="10 Best AI Agents in 2026",
        description="A complete guide to AI agents.",
        tags=["ai", "agents", "tech"],
        subtitles_path=dummy_subtitles,
        privacy_status="private",
    )


def test_validate_upload_inputs_missing_video(tmp_path: Path):
    """Missing video file raises ValueError."""
    non_existent = tmp_path / "missing.mp4"
    with pytest.raises(ValueError, match="Video file not found"):
        validate_upload_inputs(
            video_path=non_existent,
            title="Valid Title",
            description="Valid Description",
        )


def test_validate_upload_inputs_empty_video(tmp_path: Path):
    """0-byte video file raises ValueError."""
    empty_vid = tmp_path / "empty.mp4"
    empty_vid.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        validate_upload_inputs(
            video_path=empty_vid,
            title="Valid Title",
            description="Valid Description",
        )


def test_validate_upload_inputs_empty_title(dummy_video: Path):
    """Empty or whitespace-only title raises ValueError."""
    with pytest.raises(ValueError, match="title cannot be empty"):
        validate_upload_inputs(
            video_path=dummy_video,
            title="   ",
            description="Valid Description",
        )


def test_validate_upload_inputs_title_too_long(dummy_video: Path):
    """Title exceeding 100 characters raises ValueError."""
    long_title = "A" * 101
    with pytest.raises(ValueError, match="exceeds YouTube limit of 100"):
        validate_upload_inputs(
            video_path=dummy_video,
            title=long_title,
            description="Valid Description",
        )


def test_validate_upload_inputs_description_too_long(dummy_video: Path):
    """Description exceeding 5000 characters raises ValueError."""
    long_desc = "A" * 5001
    with pytest.raises(ValueError, match="exceeds YouTube limit of 5000"):
        validate_upload_inputs(
            video_path=dummy_video,
            title="Valid Title",
            description=long_desc,
        )


def test_validate_upload_inputs_tags_too_long(dummy_video: Path):
    """Tags totaling > 500 characters comma-separated raise ValueError."""
    long_tags = ["tag" + str(i) * 10 for i in range(50)]
    with pytest.raises(ValueError, match="exceed YouTube total character limit of 500"):
        validate_upload_inputs(
            video_path=dummy_video,
            title="Valid Title",
            description="Valid Description",
            tags=long_tags,
        )


def test_validate_upload_inputs_missing_subtitles(dummy_video: Path, tmp_path: Path):
    """Specified subtitles file that does not exist raises ValueError."""
    missing_sub = tmp_path / "missing.srt"
    with pytest.raises(ValueError, match="Subtitles file not found"):
        validate_upload_inputs(
            video_path=dummy_video,
            title="Valid Title",
            description="Valid Description",
            subtitles_path=missing_sub,
        )


def test_validate_upload_inputs_empty_subtitles(dummy_video: Path, tmp_path: Path):
    """Specified subtitles file that is 0 bytes raises ValueError."""
    empty_sub = tmp_path / "empty.srt"
    empty_sub.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Subtitles file is empty"):
        validate_upload_inputs(
            video_path=dummy_video,
            title="Valid Title",
            description="Valid Description",
            subtitles_path=empty_sub,
        )


def test_validate_upload_inputs_invalid_privacy(dummy_video: Path):
    """Invalid privacy status raises ValueError."""
    with pytest.raises(ValueError, match="Invalid privacy_status"):
        validate_upload_inputs(
            video_path=dummy_video,
            title="Valid Title",
            description="Valid Description",
            privacy_status="confidential",
        )


# ── 2. Dry-Run Tests ──────────────────────────────────────────────────────────


def test_upload_video_dry_run_does_not_call_api(dummy_video: Path, dummy_subtitles: Path):
    """Dry run validates inputs and exits without calling get_authenticated_service or YouTube API."""
    with patch("autopilot.upload.youtube.get_authenticated_service") as mock_auth:
        result = upload_video(
            video_path=dummy_video,
            title="Dry Run AI Agent Video",
            description="Testing dry run mode.",
            tags=["ai", "test"],
            subtitles_path=dummy_subtitles,
            privacy_status="private",
            language="en",
            dry_run=True,
        )

        # Ensure API service was NEVER initialized
        mock_auth.assert_not_called()

        assert result.success is True
        assert result.dry_run is True
        assert result.privacy_status == "private"
        assert result.video_id is not None
        assert result.url is not None
        assert result.caption_uploaded is True


# ── 3. Mocked API Upload Tests ────────────────────────────────────────────────


def test_upload_video_mocked_success(dummy_video: Path):
    """Mocked YouTube API upload returns expected video ID and sets default languages."""
    fake_service = MagicMock()
    fake_request = MagicMock()
    fake_service.videos().insert.return_value = fake_request

    fake_response = {"id": "yt_vid_999", "snippet": {"title": "Test Title"}}

    with (
        patch("autopilot.upload.youtube.get_authenticated_service", return_value=fake_service),
        patch("autopilot.upload.youtube._resumable_upload", return_value=fake_response) as mock_resumable,
    ):
        result = upload_video(
            video_path=dummy_video,
            title="Test Title",
            description="Test Description",
            tags=["tag1", "tag2"],
            privacy_status="private",
            language="en",
            dry_run=False,
        )

        assert result.success is True
        assert result.video_id == "yt_vid_999"
        assert result.url == "https://youtu.be/yt_vid_999"
        assert result.privacy_status == "private"
        assert result.dry_run is False

        # Verify insert parameters
        fake_service.videos().insert.assert_called_once()
        call_kwargs = fake_service.videos().insert.call_args.kwargs
        assert call_kwargs["part"] == "snippet,status"
        assert call_kwargs["body"]["snippet"]["title"] == "Test Title"
        assert call_kwargs["body"]["snippet"]["defaultLanguage"] == "en"
        assert call_kwargs["body"]["snippet"]["defaultAudioLanguage"] == "en"
        assert call_kwargs["body"]["status"]["privacyStatus"] == "private"
        mock_resumable.assert_called_once_with(fake_request)


def test_upload_subtitles_language_handling_and_verification(dummy_subtitles: Path):
    """upload_subtitles calls videos().list -> videos().update -> captions().insert -> captions().list."""
    fake_service = MagicMock()

    # 1. Mock videos().list() response
    list_mock = MagicMock()
    list_mock.execute.return_value = {
        "items": [
            {
                "id": "yt_vid_abc",
                "snippet": {
                    "title": "Existing Title",
                    "description": "Existing Description",
                    "tags": ["existing_tag"],
                    "categoryId": "28",
                },
            }
        ]
    }
    fake_service.videos().list.return_value = list_mock

    # 2. Mock videos().update() response
    update_mock = MagicMock()
    fake_service.videos().update.return_value = update_mock

    # 3. Mock captions().insert() request
    cap_insert_req = MagicMock()
    fake_service.captions().insert.return_value = cap_insert_req

    # 4. Mock captions().list() response
    cap_list_mock = MagicMock()
    cap_list_mock.execute.return_value = {
        "items": [
            {
                "snippet": {
                    "language": "en",
                    "name": "English",
                    "status": "serving",
                }
            }
        ]
    }
    fake_service.captions().list.return_value = cap_list_mock

    with patch("autopilot.upload.youtube._resumable_upload", return_value={"id": "cap_123"}):
        success = upload_subtitles(
            youtube=fake_service,
            video_id="yt_vid_abc",
            subtitles_path=dummy_subtitles,
            language="en",
            name="English",
        )

        assert success is True

        # Verify Step 1: videos().list called with part='snippet', id='yt_vid_abc'
        fake_service.videos().list.assert_called_once_with(
            part="snippet",
            id="yt_vid_abc",
        )

        # Verify Step 1 (cont): videos().update called with updated defaultLanguage & defaultAudioLanguage while keeping existing metadata
        fake_service.videos().update.assert_called_once()
        update_kwargs = fake_service.videos().update.call_args.kwargs
        assert update_kwargs["part"] == "snippet"
        assert update_kwargs["body"]["id"] == "yt_vid_abc"
        updated_snip = update_kwargs["body"]["snippet"]
        assert updated_snip["title"] == "Existing Title"
        assert updated_snip["description"] == "Existing Description"
        assert updated_snip["tags"] == ["existing_tag"]
        assert updated_snip["categoryId"] == "28"
        assert updated_snip["defaultLanguage"] == "en"
        assert updated_snip["defaultAudioLanguage"] == "en"

        # Verify Step 2: captions().insert called with videoId, language='en', name='English', isDraft=False
        fake_service.captions().insert.assert_called_once()
        cap_kwargs = fake_service.captions().insert.call_args.kwargs
        assert cap_kwargs["part"] == "snippet"
        cap_snip = cap_kwargs["body"]["snippet"]
        assert cap_snip["videoId"] == "yt_vid_abc"
        assert cap_snip["language"] == "en"
        assert cap_snip["name"] == "English"
        assert cap_snip["isDraft"] is False

        # Verify Step 3: captions().list called with part='snippet', videoId='yt_vid_abc'
        fake_service.captions().list.assert_called_once_with(
            part="snippet",
            videoId="yt_vid_abc",
        )


def test_upload_video_custom_language(dummy_video: Path, dummy_subtitles: Path):
    """Custom language parameter is passed to video insert and upload_subtitles."""
    fake_service = MagicMock()
    fake_response = {"id": "yt_lang_456"}

    with (
        patch("autopilot.upload.youtube.get_authenticated_service", return_value=fake_service),
        patch("autopilot.upload.youtube._resumable_upload", return_value=fake_response),
        patch("autopilot.upload.youtube.upload_subtitles", return_value=True) as mock_sub_upload,
    ):
        result = upload_video(
            video_path=dummy_video,
            title="Spanish Video",
            description="Spanish Description",
            subtitles_path=dummy_subtitles,
            language="es",
        )

        assert result.success is True
        assert result.caption_uploaded is True

        # Verify defaultLanguage and defaultAudioLanguage set to 'es'
        insert_kwargs = fake_service.videos().insert.call_args.kwargs
        assert insert_kwargs["body"]["snippet"]["defaultLanguage"] == "es"
        assert insert_kwargs["body"]["snippet"]["defaultAudioLanguage"] == "es"

        # Verify upload_subtitles was called with language='es' and name='ES'
        mock_sub_upload.assert_called_once_with(
            fake_service,
            "yt_lang_456",
            dummy_subtitles,
            language="es",
            name="ES",
        )


def test_upload_video_handles_api_exception(dummy_video: Path):
    """When API upload raises an exception, upload_video returns UploadResult with success=False."""
    fake_service = MagicMock()
    fake_service.videos().insert.side_effect = RuntimeError("Simulated API quota exceeded")

    with patch("autopilot.upload.youtube.get_authenticated_service", return_value=fake_service):
        result = upload_video(
            video_path=dummy_video,
            title="Failing Video",
            description="Description",
            privacy_status="private",
        )

        assert result.success is False
        assert result.video_id is None
        assert "Simulated API quota exceeded" in str(result.error)


# ── 4. Credentials & Auth Tests ───────────────────────────────────────────────


def test_get_authenticated_service_from_settings():
    """Builds service using settings refresh token and client secrets without printing secrets."""
    mock_settings = MagicMock()
    mock_settings.youtube_refresh_token = "mock-refresh-token"
    mock_settings.youtube_client_id = "mock-client-id"
    mock_settings.youtube_client_secret = "mock-client-secret"

    with (
        patch("autopilot.upload.youtube.get_settings", return_value=mock_settings),
        patch("autopilot.upload.youtube.build") as mock_build,
        patch("autopilot.upload.youtube.Credentials") as mock_creds,
    ):
        get_authenticated_service()
        mock_creds.assert_called_once_with(
            token=None,
            refresh_token="mock-refresh-token",
            client_id="mock-client-id",
            client_secret="mock-client-secret",
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"],
        )
        mock_build.assert_called_once_with("youtube", "v3", credentials=mock_creds.return_value)


def test_get_authenticated_service_missing_credentials_raises():
    """Raises RuntimeError when no credentials, token.json, or client_secret.json exist."""
    mock_settings = MagicMock()
    mock_settings.youtube_refresh_token = ""
    mock_settings.youtube_client_id = ""
    mock_settings.youtube_client_secret = ""

    with (
        patch("autopilot.upload.youtube.get_settings", return_value=mock_settings),
        patch("autopilot.upload.youtube.Path.exists", return_value=False),
        pytest.raises(RuntimeError, match="No valid YouTube credentials found"),
    ):
        get_authenticated_service()


def test_get_authenticated_service_from_env_token_file(monkeypatch, tmp_path):
    """Loads credentials from YOUTUBE_TOKEN_FILE if specified in env."""
    mock_settings = MagicMock()
    mock_settings.youtube_refresh_token = ""
    token_file = tmp_path / "custom_token.json"
    token_file.write_text('{"token": "abc"}', encoding="utf-8")
    monkeypatch.setenv("YOUTUBE_TOKEN_FILE", str(token_file))

    with (
        patch("autopilot.upload.youtube.get_settings", return_value=mock_settings),
        patch("google.oauth2.credentials.Credentials.from_authorized_user_file") as mock_from_file,
        patch("autopilot.upload.youtube.build") as mock_build,
    ):
        get_authenticated_service()
        mock_from_file.assert_called_once_with(
            str(token_file),
            ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"],
        )
        mock_build.assert_called_once()

