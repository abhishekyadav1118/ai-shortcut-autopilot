# The AI Shortcut — YouTube Autopilot

> Fully automated daily YouTube pipeline: RSS/HN topic selection → LLM script → Edge-TTS narration → text-card render → FFmpeg H.264/AAC MP4 → QA gate → YouTube upload.

---

## Table of Contents

1. [What Was Built](#what-was-built)
2. [Windows Setup](#windows-setup)
3. [Environment Variables (.env)](#environment-variables-env)
4. [GitHub Secrets](#github-secrets)
5. [OAuth Login (auth command)](#oauth-login-auth-command)
6. [Running Locally](#running-locally)
7. [Publish Modes](#publish-modes)
8. [Troubleshooting](#troubleshooting)
9. [How to Re-enable Schedules](#how-to-re-enable-schedules)
10. [How to Rotate Keys](#how-to-rotate-keys)
11. [First Two Weeks — Daily Checklist (Review Mode)](#first-two-weeks--daily-checklist-review-mode)

---

## What Was Built

| Component | File(s) | Status |
|-----------|---------|--------|
| Topic collection (RSS + HN) | `autopilot/topics/sources.py` | ✅ |
| LLM script generation + fact-check | `autopilot/script/generate.py`, `autopilot/llm/` | ✅ |
| Edge-TTS narration + pronunciation lexicon | `autopilot/tts/edge.py` | ✅ |
| Text-card renderer (1920×1080 Pillow) | `autopilot/render/cards.py` | ✅ |
| FFmpeg assembly (concat→loudnorm→faststart) | `autopilot/render/assemble.py` | ✅ |
| ffprobe QA gate | `autopilot/render/qa.py` | ✅ |
| SRT subtitles | `autopilot/render/subtitles.py` | ✅ |
| Thumbnail generator (2 variants, <2 MB) | `autopilot/publish/thumbnail.py` | ✅ |
| Metadata builder (title, chapters, sources, AI disclosure) | `autopilot/publish/metadata.py` | ✅ |
| YouTube resumable upload + quota fallback | `autopilot/upload/youtube.py` | ✅ |
| OAuth InstalledAppFlow (`auth` command) | `autopilot/cli.py` | ✅ |
| Deduplication + state recording | `autopilot/state.py` | ✅ |
| Daily GitHub Actions workflow | `.github/workflows/daily.yml` | ✅ |
| CI workflow (ruff + pytest offline) | `.github/workflows/ci.yml` | ✅ |

---

## Windows Setup

### Prerequisites

```powershell
# 1. Python 3.11+
python --version   # must be 3.11+

# 2. FFmpeg (via winget — adds to PATH automatically)
winget install Gyan.FFmpeg
# Then open a NEW terminal to pick up PATH

# 3. Clone and install the project
cd "C:\Users\ASUS\OneDrive\Documents\Desktop\ai automation"
pip install -e ".[dev]"
```

### Verify everything is working

```powershell
python -m autopilot doctor
```

You should see all green `[OK]` lines for Python, FFmpeg, config files, and optionally API keys.

---

## Environment Variables (.env)

Copy `.env.example` to `.env` and fill in the values:

```env
# Required — get a free key from https://aistudio.google.com
LLM_API_KEY=AIzaSy...

# Optional — for stock footage; get free key at https://www.pexels.com/api/
PEXELS_API_KEY=

# YouTube OAuth (populated automatically after running 'autopilot auth')
# For GitHub Actions, these are set as repository secrets instead.
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=

# Optional — failure notifications via Telegram bot
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

> ⚠️ **Never commit `.env` to git.** It is already in `.gitignore`.

---

## GitHub Secrets

Go to **GitHub → your repo → Settings → Secrets and variables → Actions → New repository secret**.

Add these secrets exactly as named:

| Secret Name | Where to find the value |
|-------------|------------------------|
| `LLM_API_KEY` | [Google AI Studio](https://aistudio.google.com) → Get API key |
| `PEXELS_API_KEY` | [Pexels API](https://www.pexels.com/api/) → Your API key |
| `YOUTUBE_CLIENT_ID` | `client_secret.json` → `client_id` field |
| `YOUTUBE_CLIENT_SECRET` | `client_secret.json` → `client_secret` field |
| `YOUTUBE_REFRESH_TOKEN` | `token.json` → `refresh_token` field (after running `autopilot auth`) |
| `TELEGRAM_BOT_TOKEN` | Optional — from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Optional — your Telegram user/group ID |

---

## OAuth Login (auth command)

> **Do this once locally before setting GitHub Secrets.**

### Step 1 — Get client_secret.json

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project (or use existing one)
3. Enable **YouTube Data API v3** (`APIs & Services → Library`)
4. Create credentials: `APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID`
5. Application type: **Desktop app**
6. Click **Download JSON** → rename to `client_secret.json` → place in project root

### Step 2 — Run the auth command

```powershell
python -m autopilot auth
```

**What you will see in the browser:**
- Google sign-in page opens automatically at `accounts.google.com`
- Sign in with the Google account that **owns your YouTube channel**
- A permissions screen appears: `"The AI Shortcut Autopilot wants to access your account"`
- Click **Allow**
- Browser redirects to `http://localhost:PORT/?code=...` — this is normal and expected
- The terminal prints: `[OK] Login complete. Token saved to: .../token.json`

### Step 3 — Extract refresh_token for GitHub

Open `token.json` in a text editor. Copy the `refresh_token` value (the long string after `"refresh_token":`). Add it as `YOUTUBE_REFRESH_TOKEN` in GitHub Secrets.

> 🔄 Refresh tokens last ~6 months. Set a calendar reminder to rotate.

---

## Running Locally

```powershell
# Full pipeline in review mode (private upload, no publishAt)
python -m autopilot run --mode review

# Auto mode (private + publishAt = today 10:00 AM New York)
python -m autopilot run --mode auto

# Package mode (no upload, saves assets to out/pipeline_out/)
python -m autopilot run --mode package

# Dry run — full pipeline except real API calls
python -m autopilot run --mode review --dry-run

# Force a specific topic URL
python -m autopilot run --topic-url "https://techcrunch.com/2026/09/23/..."

# Render from a local fixture (no LLM call)
python -m autopilot run --fixture scratch/live_script.json --mode package
```

---

## Publish Modes

| Mode | Privacy | publishAt | Upload? | Use case |
|------|---------|-----------|---------|----------|
| `review` | private | none | ✅ yes | **Default for first 2 weeks** — you review before making public |
| `auto` | private | 10:00 AM NY | ✅ yes | Fully automated scheduling after trust is established |
| `package` | — | — | ❌ no | Save MP4+metadata locally, upload manually |

**Fallback behaviour:** If upload fails with quota/403/unverified-project errors, the pipeline automatically falls back to `package` mode and saves all assets locally. Nothing is lost.

---

## Troubleshooting

### FFmpeg not found

```powershell
winget install Gyan.FFmpeg
# Close and reopen terminal
where.exe ffmpeg   # should print the path
```

### `LLM_API_KEY is not set`

Add your Gemini key to `.env`: `LLM_API_KEY=AIzaSy...`

### OAuth: `redirect_uri_mismatch`

In Google Cloud Console, edit your OAuth client and add `http://localhost` to **Authorized redirect URIs**.

### `quotaExceeded` on upload

The free YouTube Data API quota is 10,000 units/day. An upload costs ~1,600 units. If you hit quota:
- Wait until midnight Pacific for quota reset
- Pipeline falls back to `package` mode automatically — assets are safe

### `unverified project` / upload locked to private

New OAuth clients require Google verification to upload public. Until verified:
- Upload works but videos stay private regardless of `publishAt`
- This is fine for `review` mode
- Submit for OAuth verification at `APIs & Services → OAuth consent screen`

### GitHub Actions: `git push` fails

Make sure the workflow has `permissions: contents: write` and your default branch protection doesn't require PRs.

### `token.json` expired

Re-run `python -m autopilot auth` locally, copy the new `refresh_token` to GitHub Secrets.

---

## How to Re-enable Schedules

The daily cron in `.github/workflows/daily.yml` is enabled by default.

To **pause** the schedule temporarily, comment out the `schedule:` block:

```yaml
# on:
#   schedule:
#     - cron: "0 7 * * *"
#     - cron: "0 9 * * *"
  workflow_dispatch:
```

To **re-enable**, uncomment those lines and push.

> Note: GitHub automatically disables schedules on repos with no activity for 60 days. Re-enable by pushing any commit or manually running the workflow.

---

## How to Rotate Keys

### LLM API Key
1. Generate a new key at Google AI Studio
2. Update `LLM_API_KEY` in `.env` and GitHub Secrets

### YouTube OAuth (refresh_token)
1. Run `python -m autopilot auth` locally
2. Copy new `refresh_token` from `token.json`
3. Update `YOUTUBE_REFRESH_TOKEN` in GitHub Secrets
4. Delete old `token.json` from git if it was ever committed

### Pexels API Key
1. Generate at pexels.com/api
2. Update `PEXELS_API_KEY` in `.env` and GitHub Secrets

---

## First Two Weeks — Daily Checklist (Review Mode)

Run in `review` mode for the first 14 days before switching to `auto`. This gives you human oversight of every video before it goes public.

### Each Day

- [ ] Check GitHub Actions run succeeded (green ✅)
- [ ] Go to [YouTube Studio → Videos](https://studio.youtube.com) → find today's private video
- [ ] Watch the full video (or at least scrub through all scenes)
- [ ] Verify Quality Bar:
  - [ ] **Title**: 40–70 chars, curiosity-driven, no clickbait lies or ALL CAPS.
  - [ ] **Description**: 2–3 line hook, overview paragraph, 00:00 chapter timestamps, sources, AI voice disclosure, CTA, and 3–5 relevant hashtags at the end.
  - [ ] **Tags**: 10–15 relevant keyword tags mixing broad & specific terms.
  - [ ] **Thumbnails**: Bold text (max 4 words), strong contrast, evaluate Variant A vs Variant B.
  - [ ] **Video & Audio**: No factual errors/hallucinations, clear narration, no silence gaps >2s, smooth scene transitions.
- [ ] If satisfied: change Privacy from **Private** → **Public** in YouTube Studio
- [ ] If issues found: note them in a log, delete the video, fix the bug

### Week 1 Focus (Days 1–7)

- [ ] Verify script quality — are the titles clickworthy? Are facts correct?
- [ ] Check LUFS levels — audio should feel natural, not too loud or quiet
- [ ] Confirm chapters timestamps match actual scene transitions
- [ ] Tune pronunciation lexicon if any acronyms sound wrong (`config/pronunciation.yaml`)

### Week 2 Focus (Days 8–14)

- [ ] Check thumbnail A vs B — A/B test in YouTube Studio analytics after making public
- [ ] Confirm state deduplication works (no double-uploads on same day)
- [ ] Verify backup cron (09:00 UTC) exits cleanly on days primary ran
- [ ] Review `state/published.json` — correct video_ids recorded?
- [ ] Set up Telegram notifications if you want failure alerts

### Switching to Auto Mode

After 14 consecutive successful review-mode videos with no issues:

1. Edit `.github/workflows/daily.yml`, change default from `review` to `auto`:
   ```yaml
   default: "auto"
   ```
2. Or add `MODE=auto` to GitHub Actions environment variables
3. Push the change
4. The next scheduled run will automatically publish at 10:00 AM New York

> 💡 **Tip:** Even in auto mode, videos upload as **private** with a `publishAt` timestamp. YouTube automatically makes them public at the scheduled time. You still have time to cancel by deleting the video before that timestamp.

---

## Running Tests

```powershell
# Lint
python -m ruff check .

# Unit tests (offline, no API keys needed)
python -m pytest tests/unit/ -v

# Doctor (environment check)
python -m autopilot doctor
```

Expected: **101 passed**, **0 failed**, **ruff: All checks passed!**
