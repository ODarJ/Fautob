"""Music selection: FreeSound primary, local Assets fallback (no AI calls)."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.config import ASSETS, LOCAL_MUSIC, MUSIC_MANIFEST_PATH, DATA
from src import freesound

logger = logging.getLogger(__name__)


def ensure_music_manifest() -> dict[str, Any]:
    """Create or load local music manifest. Does not fabricate licenses."""
    DATA.mkdir(parents=True, exist_ok=True)
    if MUSIC_MANIFEST_PATH.is_file():
        try:
            return json.loads(MUSIC_MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    entries = []
    for key, filename in LOCAL_MUSIC.items():
        path = ASSETS / filename
        entries.append(
            {
                "key": key,
                "filename": filename,
                "path": str(path),
                "exists": path.is_file(),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
                "license": "unknown — verify before commercial use",
                "attribution": "unknown",
                "source": "local Assets/",
                "notes": (
                    "Original repository asset; license not verified by automated system. "
                    "Do not assume commercial Facebook use is permitted."
                ),
            }
        )
    manifest = {
        "version": 1,
        "description": (
            "Local music fallback files. Licenses are NOT assumed commercial-safe."
        ),
        "files": entries,
    }
    MUSIC_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def list_local_tracks() -> list[Path]:
    """Return actual existing audio files from Assets/."""
    ensure_music_manifest()
    tracks: list[Path] = []
    for filename in LOCAL_MUSIC.values():
        p = ASSETS / filename
        if p.is_file():
            tracks.append(p)
    if ASSETS.is_dir():
        for p in sorted(ASSETS.iterdir()):
            if (
                p.is_file()
                and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}
                and p not in tracks
            ):
                tracks.append(p)
    return tracks


def _normalize_key(s: str) -> str:
    """Normalize for matching despite em-dash / mojibake filename variants."""
    s = s.replace("\u2014", " ").replace("\u2013", " ")
    s = s.replace("—", " ").replace("–", " ").replace("-", " ").replace("_", " ")
    s = s.replace("ΓÇö", " ").replace("â€”", " ").replace("â€“", " ")
    return re.sub(r"[^a-z0-9]", "", s.lower())



def _deterministic_pick(mood: str, available_keys: list[str]) -> str:
    """Documented deterministic selection — no AI."""
    mood_l = mood.lower()
    rules = [
        (("dramatic", "epic", "intense", "powerful"), "dramatic piano background"),
        (("emotional", "sad", "melancholy", "touching"), "emotional"),
        (("classical", "elegant", "refined"), "classical vibes 2"),
        (("dream", "soft", "gentle", "beautiful"), "beautiful dream"),
        (("calm", "peaceful", "silent", "quiet", "ambient"), "silent descent"),
    ]
    for keywords, key in rules:
        if any(k in mood_l for k in keywords) and key in available_keys:
            return key
    idx = sum(ord(c) for c in mood_l) % len(available_keys)
    return available_keys[idx]


def select_music(
    music_mood: str, work_dir: Path, track_hint: str = ""
) -> dict[str, Any]:
    """
    Primary: FreeSound (preview + commercial-OK license).
    Fallback: one of the five local Assets/ tracks via deterministic rules.
    Never calls the planning AI.
    """
    report: dict[str, Any] = {
        "source": None,
        "sound_id": None,
        "title": None,
        "creator": None,
        "source_url": None,
        "license": None,
        "license_ok": False,
        "attribution_required": False,
        "attribution_text": "",
        "selection_reason": "",
        "local_path": None,
        "preview_used": False,
        "oauth2_used": False,
        "warnings": [],
    }

    dest = work_dir / "selected_music.mp3"

    fs_result = freesound.select_and_download(music_mood, dest)
    if fs_result:
        report.update(fs_result)
        return report

    report["warnings"].append(
        "FreeSound unavailable, no suitable licensed sound, or download failed"
    )

    local_tracks = list_local_tracks()
    if not local_tracks:
        report["warnings"].append("No local music files found in Assets/")
        report["selection_reason"] = "No usable audio source"
        return report

    available_keys = list(LOCAL_MUSIC.keys())
    chosen_key = None

    if track_hint and track_hint in LOCAL_MUSIC:
        path = ASSETS / LOCAL_MUSIC[track_hint]
        if path.is_file():
            chosen_key = track_hint

    if not chosen_key:
        chosen_key = _deterministic_pick(music_mood, available_keys)

    filename = LOCAL_MUSIC.get(chosen_key, local_tracks[0].name)
    path = ASSETS / filename
    if not path.is_file():
        target_norm = _normalize_key(filename)
        for p in local_tracks:
            if _normalize_key(p.name) == target_norm or target_norm in _normalize_key(p.name):
                path = p
                break
        else:
            path = local_tracks[0]

    report.update(
        {
            "source": "local_assets",
            "title": path.stem,
            "creator": "repository Assets",
            "source_url": None,
            "license": "unknown — verify before commercial use",
            "license_ok": False,
            "attribution_required": True,
            "local_path": str(path),
            "preview_used": False,
            "oauth2_used": False,
            "selection_reason": (
                f"FreeSound failed; selected local track '{path.name}' "
                f"for mood '{music_mood}' (key={chosen_key})"
            ),
            "attribution_text": (
                f"Local track: {path.name}\n"
                "License: unknown — verify before commercial Facebook use."
            ),
        }
    )
    report["warnings"].append(
        "Local music license is not automatically verified. "
        "Review before commercial Facebook use."
    )
    logger.info("Using local music fallback: %s", path.name)
    return report
