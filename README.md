# ObetyPl — Intelligent Daily Scenic Video Pipeline

Autonomous AI system that plans, generates, and quality-checks ~180-second vertical (9:16) cinematic nature videos for the ObetyPl Facebook Page.

**Does not publish to Facebook.** Output is for manual review and posting.

## Pipeline overview

1. **Creative Director (Groq)** — Generates multiple candidate concepts, scores them, produces a structured plan (JSON Schema validated).
2. **Pexels** — Downloads real video footage (never still photos) matched to each planned scene.
3. **Music** — FreeSound API (`/apiv2/search/`, preview + CC0/CC-BY only) with fallback to the five local Assets/ tracks.
4. **FFmpeg** — Renders 1080×1920 @ 30 fps, H.264 + AAC, ObetyPl watermark, audio fades.
5. **Quality gate** — Automated checks; only “ready” videos are marked successful.
6. **History** — `data/content_history.json` persisted via git commit after successful runs.

## Required GitHub Secrets

| Secret | Required | Purpose |
|--------|----------|---------|
| `GROQ_API_KEY` | Yes | Creative Director planning |
| `PEXELS_API_KEY` | Yes | Video footage |
| `FREESOUND_API_KEY` | Recommended | FreeSound music search & previews |

## Local music fallback (Assets/)

Five tracks (do not delete):

- `01 — Silent Descent.mp3`
- `02 — Beautiful Dream.mp3`
- `03 — Classical vibes 2.mp3`
- `04 — Emotional.mp3`
- `05 — Dramatic Piano Background.mp3`

Licenses for local files are **not** auto-verified.

## FreeSound notes

- Endpoint: `https://freesound.org/apiv2/search/` (current supported endpoint).
- Token auth (`FREESOUND_API_KEY`) for search + previews.
- Original-file download requires OAuth2 → **not implemented**. Previews only.
- Only CC0 / plain CC-BY accepted. NC, ND, SA rejected.
- API key never written into logs or artifacts.

## Output artifacts

- `output/ObetyPl_*.mp4`
- `output/plan.json`
- `output/caption.txt`
- `output/music_report.json`
- `output/attribution.txt`
- `output/quality_report.json`
- `data/content_history.json`
- `data/music_manifest.json`

## Run tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Architecture boundaries (future Facebook phases)

- Content planning → `src/creative_director.py`
- Video generation → `src/pexels.py` + `src/renderer.py`
- Content history → `src/history.py`
- Quality review → `src/quality.py`
- Publishing adapter → (future, official Meta Graph API only)

No browser automation or unofficial Facebook access.
