"""AI Creative Director: single-request multi-candidate planning, local scoring."""
from __future__ import annotations

import json
import logging
import random
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from jsonschema import validate, ValidationError

from src.config import (
    GROQ_KEY,
    GROQ_MODEL,
    GROQ_URL,
    INPUT_SCENERY,
    LOCAL_MUSIC,
    NUM_SCENES,
    SCENE_SECONDS,
    SCORE_WEIGHTS,
    DURATION,
)
from src.history import is_duplicate_concept, recent_concepts, rejected_reasons_summary

logger = logging.getLogger(__name__)

# Schema: exactly NUM_SCENES scenes for the full duration
PLAN_SCHEMA = {
    "type": "object",
    "required": [
        "content_id",
        "creation_date",
        "concept",
        "title",
        "audience",
        "objective",
        "emotional_tone",
        "opening_hook",
        "story_progression",
        "scenes",
        "music_mood",
        "target_duration",
        "caption",
        "hashtags",
        "copyright_checks",
        "quality_criteria",
        "selection_reason",
    ],
    "properties": {
        "content_id": {"type": "string"},
        "creation_date": {"type": "string"},
        "concept": {"type": "string"},
        "title": {"type": "string"},
        "audience": {"type": "string"},
        "objective": {"type": "string"},
        "emotional_tone": {"type": "string"},
        "opening_hook": {"type": "string"},
        "story_progression": {"type": "string"},
        "scenes": {
            "type": "array",
            "minItems": NUM_SCENES,
            "maxItems": NUM_SCENES,
            "items": {
                "type": "object",
                "required": ["description", "query", "seconds"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "query": {"type": "string"},
                    "seconds": {"type": "number"},
                    "transition": {"type": "string"},
                    "media_type": {"type": "string"},
                    "mood": {"type": "string"},
                    "narrative_role": {"type": "string"},
                },
            },
        },
        "music_mood": {"type": "string"},
        "natural_sfx": {"type": "string"},
        "transition_suggestions": {"type": "string"},
        "target_duration": {"type": "number"},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "copyright_checks": {"type": "string"},
        "quality_criteria": {"type": "array", "items": {"type": "string"}},
        "selection_reason": {"type": "string"},
        "music_track_hint": {"type": "string"},
    },
}

# Track outbound planning API calls for the one-request guarantee
_planning_api_calls = 0


def get_planning_api_call_count() -> int:
    return _planning_api_calls


def reset_planning_api_call_count() -> None:
    global _planning_api_calls
    _planning_api_calls = 0


def _call_groq_once(prompt: str, system: str, temperature: float = 0.75) -> dict:
    """
    Make exactly one HTTP request to Groq. No automatic retries.
    Raises on any failure so the caller can fall back locally.
    """
    global _planning_api_calls
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY missing")
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    _planning_api_calls += 1
    logger.info("Planning API request #%d (single-request policy)", _planning_api_calls)
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=(20, 120))
    if resp.status_code in (429, 500, 502, 503, 504):
        raise RuntimeError(f"Groq HTTP {resp.status_code}")
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Groq response is not a JSON object")
    return data


def _fallback_plan() -> dict[str, Any]:
    """Deterministic 12-scene, 180-second fallback (no AI)."""
    idea = INPUT_SCENERY or random.choice(
        [
            "misty green mountains at sunrise",
            "quiet tropical beach at golden hour",
            "peaceful forest after rain",
            "lake reflecting distant mountains",
            "rolling green hills beneath dramatic clouds",
            "waterfall in a lush forest",
            "snow-capped peaks under soft light",
            "serene desert dunes at dusk",
        ]
    )
    content_id = f"obetypl-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    track = random.choice(list(LOCAL_MUSIC.keys()))

    # 12 coherent scenes (~15s each)
    scene_templates = [
        (f"Immediate visual hook: soft light revealing {idea}", idea),
        (f"Wide establishing view of {idea}, natural movement", f"{idea} landscape wide"),
        (f"Closer atmospheric detail within {idea}", f"{idea} nature detail"),
        (f"Gentle natural movement in {idea}", f"{idea} cinematic motion"),
        (f"Different perspective of {idea}", f"{idea} scenic view"),
        (f"Immersive texture and light of {idea}", f"{idea} soft light nature"),
        (f"Rich visual moment in {idea}", f"{idea} beautiful landscape"),
        (f"Central scenic highlight of {idea}", f"{idea} dramatic nature"),
        (f"Shifted composition of {idea}", f"{idea} vertical nature"),
        (f"Calm immersive moment in {idea}", f"{idea} peaceful scenery"),
        (f"Quiet transition toward resolution of {idea}", f"{idea} serene landscape"),
        (f"Memorable closing image of {idea}", f"{idea} sunset nature calm"),
    ]
    scenes = []
    for i, (desc, query) in enumerate(scene_templates):
        scenes.append(
            {
                "title": desc[:80],
                "description": desc,
                "query": query[:180],
                "seconds": SCENE_SECONDS,
                "transition": "soft cross-dissolve" if i < 11 else "gentle fade out",
                "media_type": "video",
                "mood": "peaceful cinematic",
                "narrative_role": f"beat {i+1}",
            }
        )

    caption = (
        f"A quiet journey through nature. {idea.title()}. "
        "Take three minutes of stillness with ObetyPl."
    )
    return {
        "content_id": content_id,
        "creation_date": datetime.now(timezone.utc).date().isoformat(),
        "concept": idea,
        "title": idea.title()[:60],
        "audience": "People seeking calm, nature lovers, mindfulness audience",
        "objective": "Evoke peace and connection with nature over three minutes",
        "emotional_tone": "peaceful, cinematic, reflective",
        "opening_hook": f"Immediate soft light revealing {idea}",
        "story_progression": (
            "Hook → establish → detail → atmosphere → perspective → movement → "
            "richness → highlight → shift → calm → resolve → close"
        ),
        "scenes": scenes,
        "music_mood": "calm ambient or soft piano",
        "natural_sfx": "light wind, distant birds if available",
        "transition_suggestions": "soft cross-dissolves throughout",
        "target_duration": DURATION,
        "caption": caption,
        "hashtags": ["#Nature", "#Scenic", "#Peaceful", "#ObetyPl", "#Mindfulness"],
        "copyright_checks": "Pexels video + local music or FreeSound CC0/BY; no stock claims of real events",
        "quality_criteria": [
            "Twelve coherent nature scenes",
            "Vertical 9:16 framing",
            "No people or text in footage",
            "Audio levels safe",
            "Watermark present",
            "Approximately 180 seconds",
        ],
        "selection_reason": "Deterministic fallback plan (AI unavailable or invalid response)",
        "music_track_hint": track,
        "source": "fallback",
    }


def _clean_scenes(scenes_raw: list, *, allow_pad: bool = False) -> list[dict]:
    """Extract usable scenes. Optionally pad only for deterministic fallback."""
    clean_scenes = []
    for s in (scenes_raw or [])[:NUM_SCENES]:
        if not isinstance(s, dict):
            continue
        q = str(s.get("query") or s.get("description") or "").strip()
        if not q:
            continue
        media = str(s.get("media_type") or s.get("media") or "video").strip().lower()
        if media not in ("video", "photo"):
            media = "video"
        clean_scenes.append(
            {
                "title": str(s.get("title") or s.get("description") or q).strip()[:120],
                "description": str(s.get("description") or q).strip()[:500],
                "query": q[:180],
                "seconds": float(s.get("seconds") or SCENE_SECONDS),
                "transition": str(s.get("transition") or "soft").strip()[:80],
                "media_type": media,
                "mood": str(s.get("mood") or s.get("atmosphere") or "").strip()[:80],
                "narrative_role": str(s.get("narrative_role") or s.get("role") or "").strip()[:120],
            }
        )
    if allow_pad:
        while len(clean_scenes) < NUM_SCENES:
            base = clean_scenes[-1]["query"] if clean_scenes else "beautiful nature landscape"
            clean_scenes.append(
                {
                    "title": f"Scenic continuation",
                    "description": f"Additional scenic view related to {base}",
                    "query": f"{base} nature cinematic",
                    "seconds": SCENE_SECONDS,
                    "transition": "soft",
                    "media_type": "video",
                    "mood": "peaceful",
                    "narrative_role": "continuation",
                }
            )
    return clean_scenes[:NUM_SCENES]


def _normalize_plan(raw: dict[str, Any], *, allow_pad: bool = False) -> dict[str, Any]:
    """Clean plan. Do not invent scenes for AI output unless allow_pad=True (fallback only)."""
    content_id = str(raw.get("content_id") or f"obetypl-{uuid.uuid4().hex[:12]}")
    clean_scenes = _clean_scenes(raw.get("scenes") or [], allow_pad=allow_pad)

    hashtags = raw.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split() if h.strip()]
    hashtags = [str(h).strip() for h in hashtags if str(h).strip()][:12]
    if not any("obetypl" in h.lower() for h in hashtags):
        hashtags.append("#ObetyPl")

    plan = {
        "content_id": content_id,
        "creation_date": str(
            raw.get("creation_date") or datetime.now(timezone.utc).date().isoformat()
        ),
        "concept": str(raw.get("concept") or raw.get("title") or "scenic nature").strip()[:200],
        "title": str(raw.get("title") or "ObetyPl Scenic Moments").strip()[:100],
        "audience": str(raw.get("audience") or "Nature and mindfulness audience").strip()[:200],
        "objective": str(
            raw.get("objective") or "Evoke calm and connection with nature"
        ).strip()[:300],
        "emotional_tone": str(raw.get("emotional_tone") or "peaceful cinematic").strip()[:150],
        "opening_hook": str(raw.get("opening_hook") or "").strip()[:300],
        "story_progression": str(raw.get("story_progression") or "").strip()[:500],
        "scenes": clean_scenes,
        "music_mood": str(raw.get("music_mood") or "calm ambient").strip()[:120],
        "natural_sfx": str(raw.get("natural_sfx") or "").strip()[:200],
        "transition_suggestions": str(
            raw.get("transition_suggestions") or "soft cross-dissolves"
        ).strip()[:200],
        "target_duration": float(raw.get("target_duration") or DURATION),
        "caption": str(raw.get("caption") or "").strip()[:500],
        "hashtags": hashtags,
        "copyright_checks": str(
            raw.get("copyright_checks") or "Verify Pexels + audio licenses"
        ).strip()[:400],
        "quality_criteria": [str(c) for c in (raw.get("quality_criteria") or [])][:12],
        "selection_reason": str(
            raw.get("selection_reason") or "Selected by Creative Director"
        ).strip()[:400],
        "music_track_hint": str(raw.get("music_track_hint") or "").strip().lower()[:80],
        "source": str(raw.get("source") or "groq"),
    }
    if not plan["caption"]:
        plan["caption"] = (
            f"{plan['title']}. A quiet moment in nature. "
            f"{' '.join(plan['hashtags'][:5])}"
        )
    return plan


def _token_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta | tb), 1)


def _score_candidate(cand: dict[str, Any], recent: list[dict]) -> float:
    """Deterministic local scoring — no AI, no network."""
    scores: dict[str, float] = {}
    concept = cand.get("concept", "").lower()
    title = cand.get("title", "").lower()
    scenes = [s.get("description", "") for s in cand.get("scenes", [])]
    queries = [s.get("query", "") for s in cand.get("scenes", [])]

    nature_words = (
        "nature", "mountain", "forest", "lake", "ocean", "beach", "sky", "cloud",
        "tree", "river", "waterfall", "sunset", "sunrise", "landscape", "scenic",
        "mist", "valley", "coast", "wave", "meadow",
    )
    rel = sum(1 for w in nature_words if w in concept or w in title) / 6.0
    scores["relevance"] = min(1.0, 0.4 + rel)

    # Novelty
    dup = is_duplicate_concept(concept, title, scenes)
    scores["novelty"] = 0.1 if dup else 0.9
    for e in recent[-12:]:
        prev_c = e.get("concept", "")
        if _token_overlap(concept, prev_c) > 0.45:
            scores["novelty"] = max(0.15, scores["novelty"] - 0.25)
        prev_scenes = " ".join(str(s) for s in e.get("scene_descriptions", []))
        if _token_overlap(" ".join(scenes), prev_scenes) > 0.4:
            scores["novelty"] = max(0.15, scores["novelty"] - 0.15)

    # Visual / narrative potential
    prog = cand.get("story_progression", "").lower()
    hook = cand.get("opening_hook", "").lower()
    scores["visual_potential"] = 0.55
    if any(x in prog for x in ("hook", "establish", "detail", "close", "atmosphere", "resolve")):
        scores["visual_potential"] = 0.85
    if len(cand.get("scenes", [])) >= NUM_SCENES:
        scores["visual_potential"] = min(1.0, scores["visual_potential"] + 0.1)
    if hook and any(w in hook for w in ("mist", "light", "wave", "reveal", "sun", "waterfall")):
        scores["visual_potential"] = min(1.0, scores["visual_potential"] + 0.05)

    # Scene diversity (unique queries)
    unique_q = len({q.lower().strip() for q in queries if q.strip()})
    diversity = unique_q / max(len(queries), 1)
    scores["visual_potential"] = min(1.0, scores["visual_potential"] * (0.7 + 0.3 * diversity))

    mood = cand.get("music_mood", "").lower()
    scores["music_fit"] = 0.8 if mood else 0.4

    good_q = sum(1 for q in queries if 2 <= len(q.split()) <= 8)
    scores["production_reliability"] = 0.4 + 0.6 * (good_q / max(1, len(queries)))

    scores["historical_performance"] = 0.5  # unknown — no real metrics

    total = sum(SCORE_WEIGHTS[k] * scores.get(k, 0.5) for k in SCORE_WEIGHTS)
    return round(total, 4)


def generate_plan(num_candidates: int = 2) -> dict[str, Any]:
    """
    Single AI request → three candidates → local validate/score/select.
    On any AI failure: pure local fallback (zero extra API calls).
    """
    reset_planning_api_call_count()
    recent = recent_concepts()
    recent_summaries = [
        f"- {e.get('date') or e.get('creation_date')}: {e.get('title')} / {e.get('concept')}"
        for e in recent[-15:]
    ]
    reject_notes = rejected_reasons_summary()
    scenery = INPUT_SCENERY or "Choose a beautiful natural landscape suitable for vertical video."

    system = (
        "You are the Creative Director for ObetyPl, a Facebook Page of cinematic vertical "
        "nature videos. Audience seeks calm, beauty, and mindfulness. "
        "Never invent specific real-world events or claim footage is of a named place. "
        "Return valid JSON only. Keep responses concise."
    )

    prompt = f"""
Plan a {DURATION}-second vertical 9:16 cinematic nature video for ObetyPl.

Scenery guidance: {scenery}

Recent content (avoid near-duplicates from last ~30 days):
{chr(10).join(recent_summaries) if recent_summaries else "(none yet)"}

Recent rejection reasons to avoid:
{chr(10).join(reject_notes) if reject_notes else "(none)"}

Return JSON with key "candidates": array of exactly {num_candidates} distinct complete plans (each must have all {NUM_SCENES} scenes).
Each candidate needs:
- concept, title (max 7 words), audience, objective, emotional_tone
- opening_hook (must be an immediate compelling visual in the first seconds — mist, light, waves, etc.; no slow empty intro)
- story_progression (brief arc)
- scenes: exactly {NUM_SCENES} objects, each with title, description, query (realistic Pexels VIDEO search), seconds ({SCENE_SECONDS}), media_type ("video"), mood, transition, narrative_role
- music_mood, transition_suggestions, target_duration ({DURATION})
- caption (natural English, max ~300 chars, no engagement bait)
- hashtags (array, include #ObetyPl)
- copyright_checks, quality_criteria, selection_reason
- music_track_hint (optional; one of {list(LOCAL_MUSIC.keys())})

Twelve-scene arc (adapt to the landscape; do not force elements that do not belong):
1 Immediate visual hook
2 Establish wider landscape
3 Natural detail
4 Atmosphere
5 Related different perspective
6 Natural movement
7 Visual richness
8 Central scenic highlight
9 Composition / camera shift
10 Calm immersive moment
11 Emotional resolution
12 Memorable closing image

Rules:
- Real nature only; no people, text, logos, cities, urban scenes.
- Queries must be realistic Pexels video searches (not photos).
- Vary themes across the three candidates.
- Caption must match scenes; no false location claims.
- Prefer coherent progression over random landscapes.
Return JSON only. Be concise.
"""

    try:
        data = _call_groq_once(prompt, system, temperature=0.75)
        candidates_raw = data.get("candidates") or data.get("plans") or [data]
        if not isinstance(candidates_raw, list):
            candidates_raw = [candidates_raw]

        scored: list[tuple[float, dict]] = []
        for c in candidates_raw:
            if not isinstance(c, dict):
                continue
            # Strict: do not pad incomplete AI plans
            norm = _normalize_plan(c, allow_pad=False)
            if len(norm.get("scenes") or []) != NUM_SCENES:
                logger.warning(
                    "Candidate rejected: %d scenes (need %d)",
                    len(norm.get("scenes") or []),
                    NUM_SCENES,
                )
                continue
            try:
                validate(instance=norm, schema=PLAN_SCHEMA)
            except ValidationError as ve:
                logger.warning("Candidate failed schema: %s", ve.message)
                continue
            score = _score_candidate(norm, recent)
            if is_duplicate_concept(
                norm["concept"], norm["title"], [s["description"] for s in norm["scenes"]]
            ):
                score = max(0.05, score * 0.4)
                logger.info("Near-duplicate candidate penalized: %s", norm["title"])
            scored.append((score, norm))

        if not scored:
            logger.warning("No valid scored candidates; using fallback")
            plan = _fallback_plan()
        else:
            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, plan = scored[0]
            plan["candidate_score"] = best_score
            plan["num_candidates_considered"] = len(scored)
            logger.info(
                "Selected plan '%s' score=%.3f among %d (API calls=%d)",
                plan["title"],
                best_score,
                len(scored),
                get_planning_api_call_count(),
            )

        plan = _normalize_plan(plan, allow_pad=False)
        if len(plan.get("scenes") or []) != NUM_SCENES:
            raise ValueError("selected plan scene count mismatch")
        validate(instance=plan, schema=PLAN_SCHEMA)
        plan["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        plan["model"] = GROQ_MODEL
        plan["planning_api_calls"] = get_planning_api_call_count()
        return plan

    except Exception as exc:
        logger.warning(
            "Creative Director AI path failed (%s); using fallback (API calls=%d)",
            exc,
            get_planning_api_call_count(),
        )
        plan = _fallback_plan()
        plan["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        plan["model"] = "fallback"
        plan["planning_api_calls"] = get_planning_api_call_count()
        return plan
