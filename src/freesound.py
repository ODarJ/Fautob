"""FreeSound API client: search, conservative license validation, download previews (no OAuth2)."""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import requests

from src.config import (
    COMMERCIAL_OK_LICENSES,
    FREESOUND_KEY,
    FREESOUND_SEARCH_URL,
    NON_COMMERCIAL_MARKERS,
)

logger = logging.getLogger(__name__)

# Licenses that are explicitly accepted for synchronization / potential commercial use
# CC0 and plain CC-BY (no NC, no ND, no SA preferred for simplicity)
ACCEPTED_LICENSE_PATTERNS = (
    "creativecommons.org/publicdomain/zero",
    "creativecommons.org/licenses/by/3.0",
    "creativecommons.org/licenses/by/4.0",
    "creativecommons.org/licenses/by/2.0",
    "creativecommons.org/licenses/by/2.5",
)

# Explicitly reject these markers
REJECT_MARKERS = (
    "nc",
    "noncommercial",
    "non-commercial",
    "non commercial",
    "nd",
    "noderiv",
    "no-deriv",
    "no derivatives",
    "sa",
    "sharealike",
    "share-alike",
    "share alike",
)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Token {FREESOUND_KEY}"} if FREESOUND_KEY else {}


def _redact(url: str) -> str:
    """Strip token query params from URLs for logs."""
    if "token=" in url.lower():
        return re.sub(r"([?&]token=)[^&]+", r"\1***", url, flags=re.I)
    return url


def is_license_commercial_ok(license_str: str) -> bool:
    """
    Conservative license check for Facebook video synchronization
    (and possible future monetization).

    - Prefer CC0.
    - Accept plain CC-BY only when attribution can be fulfilled.
    - Reject NC, ND, SA, and any unclear / missing license.
    - Never invent metadata.
    """
    if not license_str or not str(license_str).strip():
        return False
    low = str(license_str).lower().strip()

    # Reject known restricted markers first
    for marker in REJECT_MARKERS:
        if marker in low:
            return False

    # Accept only known-safe patterns
    for pat in ACCEPTED_LICENSE_PATTERNS:
        if pat in low:
            return True

    # Also accept human-readable forms that map to the above
    if low in ("cc0", "creative commons 0", "public domain"):
        return True
    if low in (
        "creative commons attribution",
        "attribution",
        "cc by",
        "cc-by",
        "creative commons attribution 3.0",
        "creative commons attribution 4.0",
    ):
        return True

    # Everything else (including SA, ND, unknown) is ineligible
    return False


def search_sounds(
    query: str,
    *,
    min_duration: float = 30.0,
    max_duration: float = 300.0,
    page_size: int = 15,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """Search FreeSound using the current /apiv2/search/ endpoint."""
    if not FREESOUND_KEY:
        logger.warning("FREESOUND_API_KEY not set; skipping FreeSound search")
        return []

    filter_q = f"duration:[{min_duration} TO {max_duration}]"
    params = {
        "query": query,
        "filter": filter_q,
        "sort": "rating_desc",
        "fields": "id,name,username,license,duration,previews,tags,url,type,filesize",
        "page_size": page_size,
        "page": 1,
    }

    last_error = "unknown"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                FREESOUND_SEARCH_URL,
                headers=_headers(),
                params=params,
                timeout=30,
            )
            if resp.status_code == 401:
                logger.error("FreeSound authentication failed (check FREESOUND_API_KEY)")
                return []
            if resp.status_code == 429:
                logger.warning("FreeSound rate limit (attempt %d)", attempt)
                if attempt < retries:
                    time.sleep(min(attempt * 4, 15))
                    continue
                return []
            if resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}"
                if attempt < retries:
                    time.sleep(min(attempt * 3, 12))
                    continue
                return []
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if not isinstance(results, list):
                logger.warning("FreeSound returned unexpected results shape")
                return []
            logger.info("FreeSound returned %d results for query=%r", len(results), query)
            return results
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_error = str(exc)
            logger.warning("FreeSound search error (attempt %d): %s", attempt, last_error)
            if attempt < retries:
                time.sleep(min(attempt * 3, 12))
    logger.warning("FreeSound search failed after %d attempts: %s", retries, last_error)
    return []


def rank_candidates(results: list[dict[str, Any]], mood: str) -> list[dict[str, Any]]:
    """Filter and rank by license, duration, presence of preview, mood tags."""
    mood_tokens = set(re.findall(r"[a-z]+", mood.lower()))
    ranked = []
    for s in results:
        license_str = str(s.get("license") or "")
        if not is_license_commercial_ok(license_str):
            continue
        previews = s.get("previews") or {}
        if not isinstance(previews, dict):
            continue
        preview_url = (
            previews.get("preview-hq-mp3")
            or previews.get("preview-lq-mp3")
            or previews.get("preview-hq-ogg")
        )
        if not preview_url:
            continue
        duration = float(s.get("duration") or 0)
        if duration < 20:
            continue  # too short for background music
        tags = {str(t).lower() for t in (s.get("tags") or [])}
        name_l = str(s.get("name") or "").lower()
        overlap = len(mood_tokens & (tags | set(name_l.split())))
        score = (
            overlap * 2.0
            + min(duration / 60.0, 3.0)
            + (1.0 if "music" in tags or "soundtrack" in tags or "ambient" in tags else 0)
        )
        ranked.append(
            {
                **s,
                "_preview_url": preview_url,
                "_score": score,
                "_license_ok": True,
            }
        )
    ranked.sort(key=lambda x: x["_score"], reverse=True)
    return ranked


def download_preview(preview_url: str, destination: Path) -> bool:
    """Download a preview (no OAuth2 required). Never logs secrets."""
    try:
        with requests.get(
            preview_url, headers=_headers(), stream=True, timeout=(15, 90)
        ) as resp:
            resp.raise_for_status()
            with open(destination, "wb") as f:
                for chunk in resp.iter_content(256 * 1024):
                    if chunk:
                        f.write(chunk)
        size = destination.stat().st_size
        if size < 20_000:
            destination.unlink(missing_ok=True)
            logger.warning("Preview too small (%d bytes)", size)
            return False
        logger.info(
            "Downloaded FreeSound preview to %s (%d bytes)", destination.name, size
        )
        return True
    except requests.RequestException as exc:
        logger.warning("Preview download failed: %s", exc)
        destination.unlink(missing_ok=True)
        return False


def build_attribution(report: dict[str, Any]) -> str:
    """Generate human-readable attribution text when required."""
    if report.get("source") != "freesound":
        return ""
    title = report.get("title") or "Unknown"
    creator = report.get("creator") or "Unknown"
    url = report.get("source_url") or ""
    license_name = report.get("license") or "Unknown"
    lines = [
        f'"{title}" by {creator}',
        f"Source: {url}" if url else "",
        f"License: {license_name}",
    ]
    if report.get("attribution_required"):
        lines.append("Attribution is required under the license terms.")
    return "\n".join(line for line in lines if line)


def select_and_download(
    music_mood: str,
    destination: Path,
    extra_queries: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Full FreeSound selection flow.
    Returns report dict with source info or None if nothing suitable.
    Uses previews only (OAuth2 for original files is not configured).
    """
    queries = [
        f"{music_mood} music",
        f"{music_mood} ambient background",
        "calm ambient music",
        "soft piano atmospheric",
    ]
    if extra_queries:
        queries = list(extra_queries) + queries

    seen_ids: set[int] = set()
    for q in queries:
        results = search_sounds(q)
        ranked = rank_candidates(results, music_mood)
        for cand in ranked:
            sid = cand.get("id")
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            preview = cand["_preview_url"]
            if download_preview(preview, destination):
                license_str = str(cand.get("license") or "")
                attribution_required = "by" in license_str.lower() and "zero" not in license_str.lower()
                report = {
                    "source": "freesound",
                    "sound_id": sid,
                    "title": cand.get("name"),
                    "creator": cand.get("username"),
                    "source_url": cand.get("url"),
                    "license": license_str,
                    "license_ok": True,
                    "attribution_required": attribution_required,
                    "duration": cand.get("duration"),
                    "preview_used": True,
                    "local_path": str(destination),
                    "selection_reason": (
                        f"Matched mood '{music_mood}' via query '{q}', "
                        f"score={cand['_score']:.1f}"
                    ),
                    "oauth2_used": False,
                    "attribution_text": "",
                }
                report["attribution_text"] = build_attribution(report)
                return report
    return None
