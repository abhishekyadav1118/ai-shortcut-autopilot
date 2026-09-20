# AI Tools YouTube Autopilot (`ai-tools-yt-autopilot`)

A fully automated, source-grounded daily YouTube video generation and publishing pipeline for **AI tools tutorials and explainers** targeting US English-speaking audiences.

```
[Sources: RSS + Hacker News + Evergreen List]
        -> 1. Collect candidates
        -> 2. Rank & pick topic (LLM) (skip topics already in state)
        -> 3. Fetch source text (trafilatura)
        -> 4. Generate script JSON (LLM, grounded in sources)
        -> 5. Fact-check pass (LLM) + validation gates (regenerate max 2x)
        -> 6. TTS per scene (edge-tts voice + timings)
        -> 7. Visuals per scene (Pexels stock HD / Pillow text cards)
        -> 8. Subtitles (ASS) + background music mix + -14 LUFS loudness normalize
        -> 9. Render video (FFmpeg) + high-contrast thumbnail (Pillow)
        -> 10. Final QA (ffprobe duration, audio, black/silence checks)
        -> 11. Upload (YouTube API v3) or Package mode
        -> 12. Save state, Telegram notify, upload run artifacts
```

---

## 🛠️ Requirements & Tools

| Component | Tool / Library | Notes |
|---|---|---|
| **Runtime** | Python 3.11+ | Typed, Pydantic v2, PyYAML, HTTPX, Tenacity |
| **System** | FFmpeg & FFprobe | For video composition, audio ducking, loudness normalization |
| **Topic Feeds** | RSS + Hacker News API | Configurable feeds in `config/feeds.yaml` |
| **Source Text** | `trafilatura` | Web content scraping and extraction for grounding |
| **LLM** | Google Gemini (default) or Anthropic | Grounded scriptwriting and fact-checking pass |
| **TTS** | `edge-tts` (default, free) | Scene-by-scene audio with natural US English voice |
| **Stock Video** | Pexels Videos API | Free stock footage with photographer credits in `credits.json` |
| **Graphics** | Pillow (PIL) | 1080p dynamic text cards and 1280x720 high-contrast thumbnails |
| **Publishing** | YouTube Data API v3 | OAuth 2.0 Desktop App flow with scheduled `publishAt` |
| **CI/CD** | GitHub Actions | Daily cron triggers with concurrency guards & state commits |

---

## 🚀 Quickstart & Setup

### 1. Install Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

| Secret Variable | Purpose | Where to get it |
|---|---|---|
| `LLM_API_KEY` | LLM scriptwriting and ranking | Google AI Studio (Gemini free tier) or Anthropic Console |
| `PEXELS_API_KEY` | Stock video retrieval | [pexels.com/api](https://www.pexels.com/api/) (Free) |
| `YOUTUBE_CLIENT_ID` | YouTube API OAuth | Google Cloud Console -> APIs & Services -> Credentials (Desktop App) |
| `YOUTUBE_CLIENT_SECRET` | YouTube API OAuth | Google Cloud Console -> APIs & Services -> Credentials |
| `YOUTUBE_REFRESH_TOKEN` | YouTube runtime token | Generated via `python -m autopilot auth` |
| `TELEGRAM_BOT_TOKEN` | (Optional) Run alerts | Telegram [@BotFather](https://t.me/botfather) |
| `TELEGRAM_CHAT_ID` | (Optional) Alert chat | Your Telegram user/channel ID |

### 3. Run System Diagnostic (Doctor)
Check your local setup, binaries, assets, and credentials:
```bash
python -m autopilot doctor
```

---

## 💻 CLI Commands

```bash
# Run system diagnostics
python -m autopilot doctor

# One-time YouTube OAuth authorization flow
python -m autopilot auth

# Run daily pipeline in Review mode (private upload for manual review)
python -m autopilot run --mode review

# Run in Auto mode (scheduled public release at 10:00 AM New York time)
python -m autopilot run --mode auto

# Run in Package mode (generates all files in out/YYYY-MM-DD/ without uploading)
python -m autopilot run --mode package

# Dry-run testing (skips external API side effects and uploads)
python -m autopilot run --dry-run

# Test offline video rendering from a script fixture (zero API cost)
python -m autopilot render-fixture tests/fixtures/sample_script.json
```

---

## 🛡️ Compliance & Quality Policy

1. **Original Value**: Every video includes structured pros, cons, target audience analysis, and clear takeaways—not just rewritten news.
2. **Fact-Checking**: All factual claims (numbers, features, prices) are verified against official source documents. Unsupported claims are removed.
3. **Disclosures**: YouTube description notes AI voice synthesis and lists source URLs. Synthetic media flags are declared where applicable.
4. **Licensing**: Uses royalty-free background music (`assets/music/LICENSES.md`) and Pexels/Pixabay footage credited in `credits.json`.
5. **No Financial Advice**: Strict validation gate blocks get-rich/urgency hype or financial promises.
