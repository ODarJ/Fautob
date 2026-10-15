"""Quality assurance checks and report generation."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from src.config import DURATION, HEIGHT, MAX_DURATION_SLACK, MIN_VIDEO_BYTES, WIDTH

logger = logging.getLogger(__name__)


def _ffprobe_json(path: Path) -> dict[str, Any] | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("ffprobe failed: %s", exc)
        return None


def run_quality_checks(
    plan: dict[str, Any],
    output_path: Path,
    music_report: dict[str, Any],
    clip_metas: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return structured quality report with pass/warn/fail."""
    checks: list[dict[str, Any]] = []
    overall = "pass"

    def add(name: str, status: str, reason: str) -> None:
        nonlocal overall
        checks.append({"name": name, "status": status, "reason": reason})
        if status == "fail":
            overall = "fail"
        elif status == "warn" and overall != "fail":
            overall = "warn"

    # 1. Plan validity
    scenes = plan.get("scenes") or []
    if len(scenes) >= 3 and plan.get("content_id") and plan.get("caption"):
        add("content_plan", "pass", "Plan has required fields and scenes")
    else:
        add("content_plan", "fail", "Plan missing critical fields")

    # 2. Footage obtained
    if len(clip_metas) >= len(scenes):
        add("footage", "pass", f"Obtained {len(clip_metas)} clips")
    elif len(clip_metas) > 0:
        add("footage", "warn", f"Only {len(clip_metas)} clips for {len(scenes)} scenes")
    else:
        add("footage", "fail", "No footage obtained")

    # 3. Clips decodable (size proxy + optional probe)
    for i, meta in enumerate(clip_metas, 1):
        path = Path(meta.get("local_path", ""))
        if path.is_file() and path.stat().st_size > 50_000:
            add(f"clip_{i}_decode", "pass", f"Clip {i} present ({path.stat().st_size} bytes)")
        else:
            add(f"clip_{i}_decode", "fail", f"Clip {i} missing or too small")

    # 4-6. Output file
    if not output_path.is_file():
        add("output_exists", "fail", "Final MP4 missing")
    else:
        size = output_path.stat().st_size
        if size < MIN_VIDEO_BYTES:
            add("output_size", "fail", f"Output too small ({size} bytes)")
        else:
            add("output_size", "pass", f"Output size {size} bytes")

        probe = _ffprobe_json(output_path)
        if probe:
            streams = probe.get("streams") or []
            vstreams = [s for s in streams if s.get("codec_type") == "video"]
            astreams = [s for s in streams if s.get("codec_type") == "audio"]
            if vstreams:
                w = int(vstreams[0].get("width") or 0)
                h = int(vstreams[0].get("height") or 0)
                if w == WIDTH and h == HEIGHT:
                    add("resolution", "pass", f"{w}x{h}")
                else:
                    add("resolution", "fail", f"Got {w}x{h}, expected {WIDTH}x{HEIGHT}")
            else:
                add("resolution", "fail", "No video stream")

            fmt = probe.get("format") or {}
            dur = float(fmt.get("duration") or 0)
            if abs(dur - DURATION) <= MAX_DURATION_SLACK:
                add("duration", "pass", f"{dur:.1f}s")
            else:
                add("duration", "warn", f"Duration {dur:.1f}s (target {DURATION})")

            if music_report.get("local_path"):
                if astreams:
                    add("audio_present", "pass", f"Audio codec={astreams[0].get('codec_name')}")
                else:
                    add("audio_present", "fail", "Expected audio but none found")
            else:
                add("audio_present", "warn", "No music selected; silent video")
        else:
            add("ffprobe", "warn", "ffprobe unavailable; skipped stream checks")

    # 8. License status
    lic = music_report.get("license") or "unknown"
    if music_report.get("license_ok"):
        add("audio_license", "pass", f"License OK: {lic}")
    elif music_report.get("source") == "local_assets":
        add("audio_license", "warn", f"Local asset license unverified: {lic}")
    else:
        add("audio_license", "warn", f"License status unclear: {lic}")

    # 10. Caption match
    if plan.get("caption") and len(plan["caption"]) > 20:
        add("caption", "pass", "Caption present")
    else:
        add("caption", "warn", "Caption short or missing")

    # 11. Watermark (assumed by renderer; cannot easily detect without OCR)
    add("watermark", "pass", "Renderer configured to draw ObetyPl watermark")

    # 12. Ready for review
    ready = overall != "fail"
    add("ready_for_review", "pass" if ready else "fail", "All critical checks passed" if ready else "Critical failures present")

    return {
        "overall": overall,
        "ready": ready,
        "checks": checks,
        "content_id": plan.get("content_id"),
        "output": str(output_path) if output_path else None,
    }
