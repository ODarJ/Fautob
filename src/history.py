"""Persistent content history for variety and learning."""
from __future__ import annotations

import json
import logging
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from src.config import HISTORY_PATH, HISTORY_MAX_ENTRIES, RECENT_CONCEPT_WINDOW, DATA

logger = logging.getLogger(__name__)


def _ensure_data_dir() -> None:
    DATA.mkdir(parents=True, exist_ok=True)


def load_history() -> list[dict[str, Any]]:
    """Load content history. Returns empty list if missing or corrupt."""
    _ensure_data_dir()
    if not HISTORY_PATH.is_file():
        return []
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "entries" in data:
            return data["entries"]
        logger.warning("History file has unexpected shape; starting fresh")
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load history: %s", exc)
        return []


def save_history(entries: list[dict[str, Any]]) -> None:
    """Atomically write history (keep most recent N)."""
    _ensure_data_dir()
    trimmed = entries[-HISTORY_MAX_ENTRIES:]
    payload = {
        "version": 1,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "entries": trimmed,
    }
    # Atomic write via temp file in same directory
    fd, tmp_path = tempfile.mkstemp(dir=DATA, suffix=".tmp", prefix="history_")
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        Path(tmp_path).replace(HISTORY_PATH)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def recent_concepts(days: int = RECENT_CONCEPT_WINDOW) -> list[dict[str, Any]]:
    """Return entries from the last N days."""
    entries = load_history()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = []
    for e in entries:
        try:
            ts = e.get("created_at_utc") or e.get("date") or ""
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= cutoff:
                recent.append(e)
        except (ValueError, TypeError):
            continue
    return recent


def is_duplicate_concept(concept: str, title: str, scenes: list[str]) -> bool:
    """Heuristic check against recent history."""
    recent = recent_concepts()
    concept_l = concept.lower().strip()
    title_l = title.lower().strip()
    scene_sigs = {s.lower().strip()[:80] for s in scenes}
    for e in recent:
        if e.get("status") not in (None, "success", "ready"):
            continue
        if e.get("concept", "").lower().strip() == concept_l:
            return True
        if e.get("title", "").lower().strip() == title_l:
            return True
        prev_scenes = {str(s).lower().strip()[:80] for s in e.get("scene_descriptions", [])}
        if scene_sigs and prev_scenes and len(scene_sigs & prev_scenes) >= 3:
            return True
    return False


def record_entry(entry: dict[str, Any]) -> None:
    """Append a validated entry and persist."""
    entries = load_history()
    entry = dict(entry)
    entry.setdefault("recorded_at_utc", datetime.now(timezone.utc).isoformat())
    entries.append(entry)
    save_history(entries)
    logger.info("Recorded history entry: %s (%s)", entry.get("content_id"), entry.get("status"))


def rejected_reasons_summary() -> list[str]:
    """Collect recent rejection reasons for the planner prompt."""
    entries = load_history()
    reasons = []
    for e in entries[-30:]:
        if e.get("status") in ("rejected", "failed"):
            r = e.get("rejection_reason") or e.get("fail_reason")
            if r:
                reasons.append(str(r)[:200])
    return reasons[-10:]
