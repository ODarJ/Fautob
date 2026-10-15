"""Pexels video footage client: search, download, validate."""
from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any

import requests

from src.config import MIN_CLIP_BYTES, PEXELS_KEY, PEXELS_URL

logger = logging.getLogger(__name__)


def search_video_url(query: str, used_ids: set[int] | None = None) -> tuple[str | None, int | None, dict[str, Any]]:
    """Return (download_url, video_id, metadata) preferring portrait large clips."""
    used_ids = used_ids or set()
    if not PEXELS_KEY:
        logger.error("PEXELS_API_KEY missing")
        return None, None, {}

    headers = {"Authorization": PEXELS_KEY}
    videos: list[dict] = []

    for params in (
        {"query": query, "orientation": "portrait", "size": "large", "per_page": 15},
        {"query": query, "size": "large", "per_page": 12},
    ):
        try:
            resp = requests.get(PEXELS_URL, headers=headers, params=params, timeout=45)
            if resp.status_code == 429:
                logger.warning("Pexels rate limit for query=%r", query)
                break
            resp.raise_for_status()
            batch = resp.json().get("videos") or []
            seen = {v.get("id") for v in videos}
            for v in batch:
                if v.get("id") not in seen:
                    videos.append(v)
            if len(videos) >= 8:
                break
        except requests.RequestException as exc:
            logger.warning("Pexels search error: %s", exc)

    options: list[tuple[int, int, str, int, dict]] = []
    for video in videos:
        vid = video.get("id")
        if vid is None or vid in used_ids:
            continue
        for vf in video.get("video_files") or []:
            link = vf.get("link")
            w = int(vf.get("width") or 0)
            h = int(vf.get("height") or 0)
            if not link or w < 480 or h < 640:
                continue
            is_portrait = 1 if h >= w else 0
            area = w * h
            meta = {
                "id": vid,
                "width": w,
                "height": h,
                "url": video.get("url"),
                "user": (video.get("user") or {}).get("name"),
                "duration": video.get("duration"),
            }
            options.append((is_portrait, area, link, vid, meta))

    if not options:
        return None, None, {}
    options.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = options[: min(6, len(options))]
    choice = random.choice(top)
    return choice[2], choice[3], choice[4]


def download_clip(
    query: str,
    destination: Path,
    used_ids: set[int] | None = None,
    max_attempts: int = 4,
) -> dict[str, Any] | None:
    """Download a real Pexels video. Returns metadata dict or None."""
    used_ids = used_ids if used_ids is not None else set()
    terms = list(
        dict.fromkeys(
            [
                query,
                f"{query} landscape nature",
                f"{query} nature vertical",
                "beautiful nature landscape cinematic",
            ]
        )
    )
    for term in terms[:max_attempts]:
        try:
            url, vid_id, meta = search_video_url(term, used_ids=used_ids)
            if not url:
                logger.info("No usable Pexels results for: %s", term)
                continue
            with requests.get(url, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                with open(destination, "wb") as f:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
            size = destination.stat().st_size
            if size > MIN_CLIP_BYTES:
                if vid_id is not None:
                    used_ids.add(vid_id)
                meta["local_path"] = str(destination)
                meta["bytes"] = size
                meta["search_term"] = term
                meta["source_url"] = url
                logger.info("Downloaded clip id=%s size=%d for query=%r", vid_id, size, term)
                return meta
            destination.unlink(missing_ok=True)
            logger.warning("Clip too small (%d bytes); discarded", size)
        except requests.RequestException as exc:
            logger.warning("Pexels download error for %r: %s", term, exc)
            destination.unlink(missing_ok=True)
    return None
