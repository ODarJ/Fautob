#!/usr/bin/env python3
"""ObetyPl intelligent daily video pipeline for Facebook Reels.

Creative Director (Groq) → Pexels footage → FreeSound / local music → FFmpeg render → QA reports.
Does NOT publish to Facebook.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config import (
    ASSETS,
    DURATION,
    GROQ_KEY,
    HEIGHT,
    OUTPUT,
    PEXELS_KEY,
    WIDTH,
    WORK,
)
from src.creative_director import generate_plan
from src.history import record_entry
from src.music import ensure_music_manifest, select_music
from src.pexels import download_clip
from src.quality import run_quality_checks
from src.renderer import make_final_video, render_scene

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("obetypl")


def fail(message: str) -> None:
    logger.error(message)
    raise SystemExit(1)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if not GROQ_KEY:
        fail(
            "GROQ_API_KEY is missing. Add it in GitHub repository "
            "Settings > Secrets and variables > Actions."
        )
    if not PEXELS_KEY:
        fail(
            "PEXELS_API_KEY is missing. Add it in GitHub repository "
            "Settings > Secrets and variables > Actions."
        )
    if not shutil.which("ffmpeg"):
        fail("FFmpeg is not installed or is not in PATH.")

    WORK.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ensure_music_manifest()

    # Clean previous intermediate files
    for old in WORK.glob("*"):
        if old.is_file():
            old.unlink(missing_ok=True)

    logger.info("Creative Director planning video...")
    plan = generate_plan(num_candidates=3)
    plan["resolution"] = f"{WIDTH}x{HEIGHT}"
    plan["aspect_ratio"] = "9:16"
    plan["duration_seconds"] = DURATION

    content_id = plan["content_id"]
    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", plan["title"]).strip("_") or "Scenic_Moments"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = OUTPUT / f"ObetyPl_{timestamp}_{safe_title[:45]}.mp4"

    write_json(OUTPUT / "plan.json", plan)

    # Footage
    used_ids: set[int] = set()
    clips: list[Path] = []
    clip_metas: list[dict] = []
    for i, scene in enumerate(plan["scenes"], 1):
        source = WORK / f"source_{i}.mp4"
        rendered = WORK / f"scene_{i}.mp4"
        logger.info("Scene %d/%d: %s", i, len(plan["scenes"]), scene["description"])
        logger.info("  Search: %s", scene["query"])
        meta = download_clip(scene["query"], source, used_ids=used_ids)
        if not meta:
            fail(
                f"Could not download Pexels footage for scene {i}. "
                "Check PEXELS_API_KEY and query."
            )
        render_scene(source, rendered, float(scene.get("seconds") or 15))
        clips.append(rendered)
        clip_metas.append(meta)

    # Music
    logger.info("Selecting music (FreeSound → local fallback)...")
    music_report = select_music(
        plan.get("music_mood") or "calm ambient",
        WORK,
        track_hint=plan.get("music_track_hint") or "",
    )
    write_json(OUTPUT / "music_report.json", music_report)

    music_path = Path(music_report["local_path"]) if music_report.get("local_path") else None
    logger.info("Music source: %s (%s)", music_report.get("source"), music_path)

    # Render
    make_final_video(clips, music_path, output)

    # Quality
    qa = run_quality_checks(plan, output, music_report, clip_metas)
    write_json(OUTPUT / "quality_report.json", qa)

    # Caption
    caption_body = plan.get("caption") or ""
    hashtags = " ".join(plan.get("hashtags") or [])
    full_caption = f"{caption_body}\n\n{hashtags}".strip()
    write_text(OUTPUT / "caption.txt", full_caption)

    # Attribution
    attr_lines = [
        "ObetyPl video attribution",
        f"Content ID: {content_id}",
        f"Title: {plan.get('title')}",
        "",
        "Video footage: Pexels (see plan.json for search terms and clip metadata)",
    ]
    for m in clip_metas:
        attr_lines.append(
            f"  - Pexels id={m.get('id')} user={m.get('user')} url={m.get('url')}"
        )
    attr_lines.append("")
    attr_lines.append("Audio:")
    if music_report.get("source") == "freesound":
        attr_lines.append(
            f"  FreeSound id={music_report.get('sound_id')} "
            f"title={music_report.get('title')} by {music_report.get('creator')}"
        )
        attr_lines.append(f"  License: {music_report.get('license')}")
        attr_lines.append(f"  URL: {music_report.get('source_url')}")
        if music_report.get("attribution_required"):
            attr_lines.append("  Attribution required under the license.")
    elif music_report.get("source") == "local_assets":
        attr_lines.append(f"  Local file: {music_report.get('title')}")
        attr_lines.append(f"  License: {music_report.get('license')}")
        attr_lines.append("  WARNING: Local asset license not auto-verified.")
    else:
        attr_lines.append("  No audio selected.")
    write_text(OUTPUT / "attribution.txt", "\n".join(attr_lines))

    # History (only record success if ready)
    history_entry = {
        "content_id": content_id,
        "created_at_utc": plan.get("generated_at_utc"),
        "date": plan.get("creation_date"),
        "concept": plan.get("concept"),
        "title": plan.get("title"),
        "main_theme": plan.get("emotional_tone"),
        "scene_descriptions": [s.get("description") for s in plan.get("scenes", [])],
        "search_terms": [s.get("query") for s in plan.get("scenes", [])],
        "music_source": music_report.get("source"),
        "music_title": music_report.get("title"),
        "music_license": music_report.get("license"),
        "caption": plan.get("caption"),
        "hashtags": plan.get("hashtags"),
        "status": "ready" if qa.get("ready") else "failed_qa",
        "quality_overall": qa.get("overall"),
        "output_file": output.name,
        "selection_reason": plan.get("selection_reason"),
    }
    if not qa.get("ready"):
        history_entry["fail_reason"] = "Quality checks failed"
    try:
        record_entry(history_entry)
    except Exception as exc:
        logger.warning("History update failed (non-fatal): %s", exc)

    if not qa.get("ready"):
        fail(f"Quality checks failed (overall={qa.get('overall')}). See output/quality_report.json")

    logger.info("SUCCESS: %s", output)
    logger.info("Size: %.1f MB", output.stat().st_size / (1024 * 1024))
    logger.info("Plan: %s", OUTPUT / "plan.json")
    logger.info("Caption: %s", OUTPUT / "caption.txt")
    logger.info("Music report: %s", OUTPUT / "music_report.json")
    logger.info("Quality: %s", OUTPUT / "quality_report.json")


if __name__ == "__main__":
    main()
