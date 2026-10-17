"""Configuration and constants for ObetyPl pipeline."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "Assets"
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
DATA = ROOT / "data"
HISTORY_PATH = DATA / "content_history.json"
MUSIC_MANIFEST_PATH = DATA / "music_manifest.json"

# Video targets
DURATION = 180
WIDTH = 1080
HEIGHT = 1920
FPS = 30
SCENE_SECONDS = 15
NUM_SCENES = 12

# API endpoints
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PEXELS_URL = "https://api.pexels.com/videos/search"
FREESOUND_SEARCH_URL = "https://freesound.org/apiv2/search/"
FREESOUND_SOUND_URL = "https://freesound.org/apiv2/sounds/{id}/"

# Environment
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "").strip()
FREESOUND_KEY = os.getenv("FREESOUND_API_KEY", "").strip()
INPUT_SCENERY = os.getenv("INPUT_SCENERY", "").strip()

# Local music fallback (exact filenames after normalization)
LOCAL_MUSIC = {
    "silent descent": "01 — Silent Descent.mp3",
    "beautiful dream": "02 — Beautiful Dream.mp3",
    "classical vibes 2": "03 — Classical vibes 2.mp3",
    "emotional": "04 — Emotional.mp3",
    "dramatic piano background": "05 — Dramatic Piano Background.mp3",
}

# Acceptable Creative Commons licenses for commercial use (prefer these)
COMMERCIAL_OK_LICENSES = {
    "Creative Commons 0",
    "CC0",
    "Creative Commons Attribution",
    "Attribution",
    "CC BY",
    "CC-BY",
    "Creative Commons Attribution 3.0",
    "Creative Commons Attribution 4.0",
    "http://creativecommons.org/publicdomain/zero/1.0/",
    "http://creativecommons.org/licenses/by/3.0/",
    "http://creativecommons.org/licenses/by/4.0/",
    "https://creativecommons.org/publicdomain/zero/1.0/",
    "https://creativecommons.org/licenses/by/3.0/",
    "https://creativecommons.org/licenses/by/4.0/",
}

# Reject non-commercial
NON_COMMERCIAL_MARKERS = ("nc", "noncommercial", "non-commercial", "non commercial")

# History limits
HISTORY_MAX_ENTRIES = 200
RECENT_CONCEPT_WINDOW = 30  # days to avoid near-duplicates

# Scoring weights for candidate concepts
SCORE_WEIGHTS = {
    "relevance": 0.25,
    "novelty": 0.25,
    "visual_potential": 0.20,
    "music_fit": 0.10,
    "production_reliability": 0.15,
    "historical_performance": 0.05,
}

# Quality thresholds
MIN_VIDEO_BYTES = 500_000
MIN_CLIP_BYTES = 100_000
MAX_DURATION_SLACK = 5.0  # seconds
