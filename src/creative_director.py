"""AI Creative Director: multi-candidate planning, scoring, schema validation."""
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
)
from src.history import is_duplicate_concept, recent_concepts, rejected_reasons_summary

logger = logging.getLogger(__name__)

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
            "minItems": 3,
            "maxItems": 5,
            "items": {
                "type": "object",
                "required": ["description", "query", "seconds"],
                "properties": {
                    "description": {"type": "string"},
                    "query": {"type": "string"},
                    "seconds": {"type": "number"},
                    "transition": {"type": "string"},
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


def _call_groq(prompt: str, system: str, retries: int = 4, temperature: float = 0.75) -> dict:
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
    last_error = "Unknown"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=(20, 90))
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = f"HTTP {resp.status_code}"
                if attempt < retries:
                    time.sleep(min(attempt * 6, 24))
                    continue
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("Not a JSON object")
            return data
        except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(attempt * 5, 20))
    raise RuntimeError(f"Groq failed after {retries} attempts: {last_error}")


def _fallback_plan() -> dict[str, Any]:
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
    scenes = [
        {
            "description": f"Vertical establishing view of {idea}, soft natural light",
            "query": idea,
            "seconds": SCENE_SECONDS,
            "transition": "gentle fade",
        },
        {
            "description": f"Atmospheric vertical nature view of {idea}, gentle movement",
            "query": f"{idea} cinematic nature",
            "seconds": SCENE_SECONDS,
            "transition": "cross dissolve",
        },
        {
            "description": f"Detailed scenic landscape related to {idea}",
            "query": f"{idea} scenic landscape",
            "seconds": SCENE_SECONDS,
            "transition": "soft cut",
        },
        {
            "description": f"Vertical closing landscape of {idea}, warm soft light",
            "query": f"{idea} sunset nature",
            "seconds": SCENE_SECONDS,
            "transition": "fade out",
        },
    ]
    caption = (
        f"Find stillness in nature. {idea.title()}. "
        "Take a quiet moment with ObetyPl."
    )
    return {
        "content_id": content_id,
        "creation_date": datetime.now(timezone.utc).date().isoformat(),
        "concept": idea,
        "title": idea.title()[:60],
        "audience": "People seeking calm, nature lovers, mindfulness audience",
        "objective": "Evoke peace and connection with nature",
        "emotional_tone": "peaceful, cinematic, reflective",
        "opening_hook": f"Soft light revealing {idea}",
        "story_progression": "Establish place → deepen atmosphere → intimate detail → gentle close",
        "scenes": scenes,
        "music_mood": "calm ambient or soft piano",
        "natural_sfx": "light wind, distant birds if available",
        "transition_suggestions": "soft cross-dissolves, no hard cuts",
        "target_duration": 60,
        "caption": caption,
        "hashtags": ["#Nature", "#Scenic", "#Peaceful", "#ObetyPl", "#Mindfulness"],
        "copyright_checks": "Pexels video + local music or FreeSound CC0/BY; no stock claims of real events",
        "quality_criteria": [
            "Four coherent nature scenes",
            "Vertical 9:16 framing",
            "No people or text in footage",
            "Audio levels safe",
            "Watermark present",
        ],
        "selection_reason": "Deterministic fallback plan (AI unavailable or invalid response)",
        "music_track_hint": track,
        "source": "fallback",
    }


def _normalize_plan(raw: dict[str, Any]) -> dict[str, Any]:
    """Clean and fill a plan dict so it satisfies the schema."""
    content_id = str(raw.get("content_id") or f"obetypl-{uuid.uuid4().hex[:12]}")
    scenes_raw = raw.get("scenes") or []
    clean_scenes = []
    for s in scenes_raw[:NUM_SCENES]:
        if not isinstance(s, dict):
            continue
        q = str(s.get("query") or s.get("description") or "").strip()
        if not q:
            continue
        clean_scenes.append(
            {
                "description": str(s.get("description") or q).strip()[:500],
                "query": q[:180],
                "seconds": float(s.get("seconds") or SCENE_SECONDS),
                "transition": str(s.get("transition") or "soft").strip()[:80],
            }
        )
    while len(clean_scenes) < NUM_SCENES:
        base = clean_scenes[-1]["query"] if clean_scenes else "beautiful nature landscape"
        clean_scenes.append(
            {
                "description": f"Additional scenic view related to {base}",
                "query": f"{base} nature cinematic",
                "seconds": SCENE_SECONDS,
                "transition": "soft",
            }
        )
    clean_scenes = clean_scenes[:NUM_SCENES]

    hashtags = raw.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split() if h.strip()]
    hashtags = [str(h).strip() for h in hashtags if str(h).strip()][:12]
    if not any("obetypl" in h.lower() for h in hashtags):
        hashtags.append("#ObetyPl")

    plan = {
        "content_id": content_id,
        "creation_date": str(raw.get("creation_date") or datetime.now(timezone.utc).date().isoformat()),
        "concept": str(raw.get("concept") or raw.get("title") or "scenic nature").strip()[:200],
        "title": str(raw.get("title") or "ObetyPl Scenic Moments").strip()[:100],
        "audience": str(raw.get("audience") or "Nature and mindfulness audience").strip()[:200],
        "objective": str(raw.get("objective") or "Evoke calm and connection with nature").strip()[:300],
        "emotional_tone": str(raw.get("emotional_tone") or "peaceful cinematic").strip()[:150],
        "opening_hook": str(raw.get("opening_hook") or "").strip()[:300],
        "story_progression": str(raw.get("story_progression") or "").strip()[:400],
        "scenes": clean_scenes,
        "music_mood": str(raw.get("music_mood") or "calm ambient").strip()[:120],
        "natural_sfx": str(raw.get("natural_sfx") or "").strip()[:200],
        "transition_suggestions": str(raw.get("transition_suggestions") or "soft cross-dissolves").strip()[:200],
        "target_duration": float(raw.get("target_duration") or 60),
        "caption": str(raw.get("caption") or "").strip()[:500],
        "hashtags": hashtags,
        "copyright_checks": str(raw.get("copyright_checks") or "Verify Pexels + audio licenses").strip()[:400],
        "quality_criteria": [str(c) for c in (raw.get("quality_criteria") or [])][:10],
        "selection_reason": str(raw.get("selection_reason") or "Selected by Creative Director").strip()[:400],
        "music_track_hint": str(raw.get("music_track_hint") or "").strip().lower()[:80],
        "source": str(raw.get("source") or "groq"),
    }
    if not plan["caption"]:
        plan["caption"] = (
            f"{plan['title']}. A quiet moment in nature. "
            f"{' '.join(plan['hashtags'][:5])}"
        )
    return plan


def _score_candidate(cand: dict[str, Any], recent: list[dict]) -> float:
    """Deterministic scoring of a candidate plan."""
    scores = {}
    concept = cand.get("concept", "").lower()
    title = cand.get("title", "").lower()
    scenes = [s.get("description", "") for s in cand.get("scenes", [])]

    # Relevance to ObetyPl (nature, calm, scenic)
    nature_words = ("nature", "mountain", "forest", "lake", "ocean", "beach", "sky", "cloud", "tree", "river", "waterfall", "sunset", "sunrise", "landscape", "scenic")
    rel = sum(1 for w in nature_words if w in concept or w in title) / 5.0
    scores["relevance"] = min(1.0, 0.4 + rel)

    # Novelty vs recent
    dup = is_duplicate_concept(concept, title, scenes)
    scores["novelty"] = 0.15 if dup else 0.9
    # slight penalty for very similar themes
    for e in recent[-8:]:
        if any(w in e.get("concept", "").lower() for w in concept.split()[:3] if len(w) > 4):
            scores["novelty"] = max(0.2, scores["novelty"] - 0.2)

    # Visual storytelling potential (has progression language)
    prog = cand.get("story_progression", "").lower()
    scores["visual_potential"] = 0.7
    if any(x in prog for x in ("establish", "detail", "close", "atmosphere", "progression")):
        scores["visual_potential"] = 0.9
    if len(cand.get("scenes", [])) >= 4:
        scores["visual_potential"] = min(1.0, scores["visual_potential"] + 0.05)

    # Music fit (has mood)
    mood = cand.get("music_mood", "").lower()
    scores["music_fit"] = 0.8 if mood else 0.4

    # Production reliability (queries look searchable)
    queries = [s.get("query", "") for s in cand.get("scenes", [])]
    good_q = sum(1 for q in queries if 3 <= len(q.split()) <= 8)
    scores["production_reliability"] = 0.5 + 0.5 * (good_q / max(1, len(queries)))

    # Historical (placeholder; no metrics yet)
    scores["historical_performance"] = 0.5

    total = sum(SCORE_WEIGHTS[k] * scores.get(k, 0.5) for k in SCORE_WEIGHTS)
    return round(total, 4)


def generate_plan(num_candidates: int = 3) -> dict[str, Any]:
    """Generate multiple candidates via Groq, score, pick best, validate schema."""
    recent = recent_concepts()
    recent_summaries = [
        f"- {e.get('date') or e.get('creation_date')}: {e.get('title')} / {e.get('concept')}"
        for e in recent[-12:]
    ]
    reject_notes = rejected_reasons_summary()
    scenery = INPUT_SCENERY or "Choose a beautiful natural landscape suitable for vertical Reels."

    system = (
        "You are the Creative Director for ObetyPl, a Facebook Page that publishes "
        "cinematic vertical nature and scenic videos. Audience seeks calm, beauty, and mindfulness. "
        "Never invent specific real-world events or claim footage is of a particular named place "
        "unless the query is generic. Return valid JSON only."
    )

    prompt = f"""
Plan a ~60-second vertical 9:16 cinematic scenic nature video for ObetyPl.

Scenery guidance: {scenery}

Recent content (avoid near-duplicates):
{chr(10).join(recent_summaries) if recent_summaries else "(none yet)"}

Recent rejection reasons to avoid:
{chr(10).join(reject_notes) if reject_notes else "(none)"}

Produce JSON with a top-level key "candidates" that is an array of {num_candidates} distinct candidate plans.
Each candidate must contain:
- concept (short)
- title (max 7 words)
- audience
- objective
- emotional_tone
- opening_hook
- story_progression
- scenes: array of exactly 4 objects with description, query (Pexels video search terms, portrait-friendly nature), seconds (15)
- music_mood (e.g. calm piano, ambient pads, soft strings)
- natural_sfx (optional)
- transition_suggestions
- target_duration (60)
- caption (natural English, no engagement bait, max ~300 chars)
- hashtags (array, include #ObetyPl)
- copyright_checks (short note)
- quality_criteria (array of strings)
- selection_reason (why this concept fits ObetyPl today)
- music_track_hint (optional; one of {list(LOCAL_MUSIC.keys())} if suggesting local fallback)

Rules:
- Real nature / landscape only; no people, text, logos, cities, or urban scenes.
- Queries must be realistic Pexels video searches (not photos).
- Vary themes across candidates (e.g. mountain, water, forest, sky, seasonal).
- Caption must match the scenes and mood; no false claims.
- Prefer coherent visual progression.
Return JSON only.
"""

    try:
        data = _call_groq(prompt, system, temperature=0.8)
        candidates_raw = data.get("candidates") or data.get("plans") or [data]
        if not isinstance(candidates_raw, list):
            candidates_raw = [candidates_raw]

        scored: list[tuple[float, dict]] = []
        for c in candidates_raw:
            if not isinstance(c, dict):
                continue
            norm = _normalize_plan(c)
            try:
                validate(instance=norm, schema=PLAN_SCHEMA)
            except ValidationError as ve:
                logger.warning("Candidate failed schema: %s", ve.message)
                continue
            if is_duplicate_concept(norm["concept"], norm["title"], [s["description"] for s in norm["scenes"]]):
                logger.info("Skipping near-duplicate candidate: %s", norm["title"])
                continue
            score = _score_candidate(norm, recent)
            scored.append((score, norm))

        if not scored:
            logger.warning("No valid scored candidates; using fallback")
            plan = _fallback_plan()
        else:
            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, plan = scored[0]
            plan["candidate_score"] = best_score
            plan["num_candidates_considered"] = len(scored)
            logger.info("Selected plan '%s' with score %.3f among %d", plan["title"], best_score, len(scored))

        # Final schema validation + fill
        plan = _normalize_plan(plan)
        validate(instance=plan, schema=PLAN_SCHEMA)
        plan["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        plan["model"] = GROQ_MODEL
        return plan

    except Exception as exc:
        logger.warning("Creative Director AI path failed (%s); using fallback plan", exc)
        plan = _fallback_plan()
        plan["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
        plan["model"] = "fallback"
        return plan
