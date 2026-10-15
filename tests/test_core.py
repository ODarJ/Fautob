"""Unit tests for ObetyPl pipeline (mocked external APIs)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from jsonschema import validate

from src.config import LOCAL_MUSIC, FREESOUND_SEARCH_URL
from src.creative_director import _fallback_plan, _normalize_plan, PLAN_SCHEMA
from src.freesound import (
    is_license_commercial_ok,
    rank_candidates,
    search_sounds,
    build_attribution,
    _redact,
)
from src.history import load_history, save_history, is_duplicate_concept, record_entry
from src.music import ensure_music_manifest, list_local_tracks, select_music, _deterministic_pick


def test_fallback_plan_schema():
    plan = _fallback_plan()
    norm = _normalize_plan(plan)
    validate(instance=norm, schema=PLAN_SCHEMA)
    assert len(norm["scenes"]) == 4
    assert norm["content_id"]
    assert norm["caption"]


def test_normalize_fills_missing():
    raw = {"title": "Test Hills", "scenes": [{"query": "green hills"}]}
    norm = _normalize_plan(raw)
    assert len(norm["scenes"]) == 4
    assert "#ObetyPl" in " ".join(norm["hashtags"])


def test_freesound_endpoint_is_current():
    """Must use the supported /apiv2/search/ endpoint, not deprecated /search/text/."""
    assert FREESOUND_SEARCH_URL.rstrip("/").endswith("/apiv2/search")
    assert "/search/text" not in FREESOUND_SEARCH_URL


def test_license_commercial_ok_strict():
    # Accepted
    assert is_license_commercial_ok("http://creativecommons.org/publicdomain/zero/1.0/")
    assert is_license_commercial_ok("https://creativecommons.org/licenses/by/4.0/")
    assert is_license_commercial_ok("Creative Commons Attribution")
    assert is_license_commercial_ok("CC0")
    # Rejected
    assert not is_license_commercial_ok("Creative Commons Attribution-NonCommercial")
    assert not is_license_commercial_ok("https://creativecommons.org/licenses/by-nc/4.0/")
    assert not is_license_commercial_ok("https://creativecommons.org/licenses/by-nd/4.0/")
    assert not is_license_commercial_ok("https://creativecommons.org/licenses/by-sa/4.0/")
    assert not is_license_commercial_ok("")
    assert not is_license_commercial_ok("Some Unknown License")


def test_rank_candidates_filters_restricted():
    results = [
        {
            "id": 1,
            "name": "Calm Piano",
            "license": "http://creativecommons.org/publicdomain/zero/1.0/",
            "duration": 90,
            "previews": {"preview-hq-mp3": "http://example.com/a.mp3"},
            "tags": ["piano", "calm"],
        },
        {
            "id": 2,
            "name": "NC Track",
            "license": "Attribution NonCommercial",
            "duration": 90,
            "previews": {"preview-hq-mp3": "http://example.com/b.mp3"},
            "tags": ["piano"],
        },
        {
            "id": 3,
            "name": "ND Track",
            "license": "https://creativecommons.org/licenses/by-nd/4.0/",
            "duration": 90,
            "previews": {"preview-hq-mp3": "http://example.com/c.mp3"},
            "tags": ["piano"],
        },
        {
            "id": 4,
            "name": "No Preview",
            "license": "http://creativecommons.org/publicdomain/zero/1.0/",
            "duration": 90,
            "previews": {},
            "tags": ["piano"],
        },
    ]
    ranked = rank_candidates(results, "calm piano")
    assert len(ranked) == 1
    assert ranked[0]["id"] == 1


def test_search_sounds_missing_key(monkeypatch):
    monkeypatch.setattr("src.freesound.FREESOUND_KEY", "")
    assert search_sounds("piano") == []


def test_search_sounds_rate_limit(monkeypatch):
    monkeypatch.setattr("src.freesound.FREESOUND_KEY", "fake-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("src.freesound.requests.get", return_value=mock_resp):
        assert search_sounds("piano", retries=1) == []


def test_search_sounds_success(monkeypatch):
    monkeypatch.setattr("src.freesound.FREESOUND_KEY", "fake-key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "id": 99,
                "name": "Test",
                "license": "http://creativecommons.org/publicdomain/zero/1.0/",
                "duration": 60,
                "previews": {"preview-hq-mp3": "http://ex.com/p.mp3"},
                "tags": ["ambient"],
            }
        ]
    }
    with patch("src.freesound.requests.get", return_value=mock_resp) as m:
        results = search_sounds("ambient", retries=1)
        assert len(results) == 1
        assert results[0]["id"] == 99
        # Ensure we called the current endpoint
        called_url = m.call_args[0][0]
        assert "/apiv2/search/" in called_url
        assert "/search/text" not in called_url


def test_attribution_generation():
    report = {
        "source": "freesound",
        "title": "Calm Waves",
        "creator": "soundartist",
        "source_url": "https://freesound.org/s/123/",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "attribution_required": True,
    }
    text = build_attribution(report)
    assert "Calm Waves" in text
    assert "soundartist" in text
    assert "Attribution is required" in text


def test_history_roundtrip(tmp_path, monkeypatch):
    hist = tmp_path / "content_history.json"
    monkeypatch.setattr("src.history.HISTORY_PATH", hist)
    monkeypatch.setattr("src.history.DATA", tmp_path)
    assert load_history() == []
    record_entry({"content_id": "t1", "status": "ready", "concept": "lake", "title": "Lake"})
    data = load_history()
    assert len(data) == 1
    assert data[0]["content_id"] == "t1"


def test_duplicate_detection(tmp_path, monkeypatch):
    hist = tmp_path / "content_history.json"
    monkeypatch.setattr("src.history.HISTORY_PATH", hist)
    monkeypatch.setattr("src.history.DATA", tmp_path)
    from datetime import datetime, timezone

    entry = {
        "content_id": "x",
        "status": "ready",
        "concept": "misty mountains",
        "title": "Misty Mountains",
        "scene_descriptions": ["a", "b", "c", "d"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    record_entry(entry)
    assert is_duplicate_concept("misty mountains", "Misty Mountains", ["a", "b", "c", "d"])
    assert not is_duplicate_concept("desert dunes", "Desert Dunes", ["x", "y", "z", "w"])


def test_music_manifest_and_local():
    tracks = list_local_tracks()
    # All five known tracks should exist
    names = {p.name for p in tracks}
    for expected in LOCAL_MUSIC.values():
        assert expected in names, f"Missing expected track: {expected}"
    man = ensure_music_manifest()
    assert "files" in man
    assert len(man["files"]) == 5


def test_select_music_fallback_no_freesound(tmp_path):
    with patch("src.music.freesound.select_and_download", return_value=None):
        report = select_music("calm ambient", tmp_path)
    assert report["source"] == "local_assets"
    assert report["local_path"]
    assert report["license_ok"] is False
    assert Path(report["local_path"]).is_file()


def test_deterministic_pick_matches_mood():
    keys = list(LOCAL_MUSIC.keys())
    assert _deterministic_pick("dramatic intense", keys) == "dramatic piano background"
    assert _deterministic_pick("emotional sad", keys) == "emotional"
    assert _deterministic_pick("peaceful calm quiet", keys) == "silent descent"


def test_unicode_music_filenames():
    """All five files must be findable with their real Unicode names."""
    tracks = list_local_tracks()
    assert len(tracks) >= 5
    for p in tracks:
        assert p.is_file()
        assert "—" in p.name or p.suffix.lower() == ".mp3"


def test_secret_redaction():
    url = "https://freesound.org/apiv2/search/?query=piano&token=SECRET123"
    assert "SECRET123" not in _redact(url)
    assert "***" in _redact(url)
