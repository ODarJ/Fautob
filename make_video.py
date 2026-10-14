import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "Assets"
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
WORK.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "").strip()
SCENERY_INPUT = os.getenv("INPUT_SCENERY", "").strip()
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
VIDEO_SECONDS = 60
WIDTH, HEIGHT, FPS = 1920, 1080, 30

TRACKS = [
    {"id": "01", "name": "Silent Descent", "artist": "Eugenio Mininni", "file": "01 — Silent Descent.mp3"},
    {"id": "02", "name": "Beautiful Dream", "artist": "Diego Nava", "file": "02 — Beautiful Dream.mp3"},
    {"id": "03", "name": "Classical vibes 2", "artist": "Grigoriy Nuzhny", "file": "03 — Classical vibes 2.mp3"},
    {"id": "04", "name": "Emotional", "artist": "The_Mountain", "file": "04 — Emotional.mp3"},
    {"id": "05", "name": "Dramatic Piano Background", "artist": "OpenMindAudio", "file": "05 — Dramatic Piano Background.mp3"},
]

def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)

def call_gemini(prompt, image_bytes=None):
    if not GEMINI_KEY:
        fail("GEMINI_API_KEY secret is missing.")
    # Use the current stable model by default. A secret named GEMINI_MODEL can override it.
    parts = [{"text": prompt}]
    if image_bytes:
        import base64
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                      "data": base64.b64encode(image_bytes).decode("ascii")}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.5,
                             "maxOutputTokens": 1800}
    }
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers={"x-goog-api-key": GEMINI_KEY},
                                    json=payload, timeout=90)
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = f"Gemini HTTP {response.status_code}: {response.text[:500]}"
                time.sleep(2 ** attempt * 2)
                continue
            response.raise_for_status()
            data = response.json()
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
            return json.loads(text)
        except Exception as exc:
            last_error = str(exc)
            if attempt < 2:
                time.sleep(2 ** attempt)
    fail(f"Gemini request failed after retries. {last_error}")

def plan_scenes():
    scenery = SCENERY_INPUT or "Choose a fresh, beautiful landscape idea for today. Avoid repeating the same type every day."
    prompt = f"""
You are the creative director for ObetyPl, a scenic landscape video brand.
Make a plan for a 60-second 16:9 landscape video with no captions or subtitles.
Visual mood: cinematic, peaceful, wistful, beautiful, emotionally moving, realistic.
User's optional idea: {scenery}
Return ONLY JSON:
{{
  "title": "short internal title",
  "mood": "short mood description",
  "scenes": [
    {{"query":"short Pexels search phrase, 2-5 words", "description":"what the scenery should look like"}},
    {{"query":"short Pexels search phrase, 2-5 words", "description":"what the scenery should look like"}},
    {{"query":"short Pexels search phrase, 2-5 words", "description":"what the scenery should look like"}},
    {{"query":"short Pexels search phrase, 2-5 words", "description":"what the scenery should look like"}}
  ],
  "track_id": "01",
  "track_name": "exact track name from the list",
  "artist": "exact artist from the list",
  "music_reason": "brief reason based on the names only"
}}
Choose exactly one track from this list by name only (you cannot listen to the MP3s):
{json.dumps(TRACKS, ensure_ascii=False)}
track_id must be one of 01, 02, 03, 04, 05. Keep queries suitable for Pexels stock footage.
"""
    data = call_gemini(prompt)
    if not isinstance(data.get("scenes"), list) or len(data["scenes"]) < 2:
        fail("Gemini did not return at least two scenes.")
    valid = {t["id"]: t for t in TRACKS}
    tid = str(data.get("track_id", ""))
    if tid not in valid:
        # Repair once rather than accidentally selecting a non-library track.
        data["track_id"] = "01"
        data["track_name"] = valid["01"]["name"]
        data["artist"] = valid["01"]["artist"]
        data["music_reason"] = "Fallback selection because Gemini returned an invalid track ID."
    else:
        data["track_name"] = valid[tid]["name"]
        data["artist"] = valid[tid]["artist"]
    return data

def pexels_search(query):
    if not PEXELS_KEY:
        fail("PEXELS_API_KEY secret is missing.")
    url = "https://api.pexels.com/videos/search"
    response = requests.get(url, headers={"Authorization": PEXELS_KEY},
                            params={"query": query, "orientation": "landscape",
                                    "size": "large", "per_page": 12}, timeout=45)
    response.raise_for_status()
    videos = response.json().get("videos", [])
    # Keep clips with a landscape file of reasonable resolution.
    candidates = []
    for video in videos:
        choices = []
        for vf in video.get("video_files", []):
            link = vf.get("link")
            w, h = vf.get("width") or 0, vf.get("height") or 0
            if link and w >= 1280 and h >= 600 and w > h:
                choices.append((w * h, link))
        if choices:
            candidates.append((video, max(choices)[1]))
    if not candidates:
        return None
    video, link = random.choice(candidates[:min(8, len(candidates))])
    return {"url": link, "id": video.get("id"), "creator": video.get("user", {}).get("name", "Unknown"),
            "page": video.get("url", ""), "query": query}

def download(url, path):
    with requests.get(url, stream=True, timeout=(20, 180)) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    if path.stat().st_size < 100_000:
        fail(f"Downloaded file looks too small: {path}")
    return path

def run(cmd):
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run([str(x) for x in cmd], check=True)

def render_clip(source, target, seconds):
    # Crop-to-fill landscape 1080p, subtle saturation/contrast, slow zoom, no embedded audio.
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        "setsar=1,eq=saturation=1.06:contrast=1.03:brightness=0.005,"
        f"fps={FPS},trim=duration={seconds},setpts=PTS-STARTPTS,"
        f"zoompan=z='min(zoom+0.00018,1.035)':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS}"
    )
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", source, "-t", str(seconds),
         "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", target])

def main():
    if not GEMINI_KEY or not PEXELS_KEY:
        fail("Add both GEMINI_API_KEY and PEXELS_API_KEY in GitHub Settings > Secrets and variables > Actions.")
    plan = plan_scenes()
    print("AI scene plan:", json.dumps(plan, ensure_ascii=False, indent=2))

    # Try each scene query. If a query yields no clips, use a broader fallback.
    selected = []
    for i, scene in enumerate(plan["scenes"][:4], start=1):
        query = str(scene.get("query", "")).strip() or "beautiful nature landscape"
        found = None
        for q in [query, "cinematic nature landscape", "beautiful ocean mountains"]:
            try:
                found = pexels_search(q)
            except requests.RequestException as exc:
                print(f"Pexels search warning for {q!r}: {exc}")
            if found:
                break
        if not found:
            print(f"WARNING: No footage found for scene {i}; skipping it.")
            continue
        raw = WORK / f"clip_{i}_raw.mp4"
        try:
            download(found["url"], raw)
            selected.append({"path": raw, "meta": found, "description": scene.get("description", "")})
            print(f"Downloaded scene {i}: query={found['query']}, Pexels video ID={found['id']}")
        except Exception as exc:
            print(f"WARNING: Could not download scene {i}: {exc}")

    if not selected:
        fail("Could not download any Pexels clips. Check PEXELS_API_KEY and try again.")

    # Split 60 seconds equally across clips; concatenate matching H.264 files.
    per_clip = VIDEO_SECONDS / len(selected)
    rendered = []
    for i, item in enumerate(selected, start=1):
        target = WORK / f"clip_{i:02d}.mp4"
        render_clip(item["path"], target, per_clip)
        rendered.append(target)

    concat_file = WORK / "concat.txt"
    concat_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in rendered), encoding="utf-8")
    silent_video = WORK / "silent.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
         "-t", str(VIDEO_SECONDS), "-c", "copy", silent_video])

    track = next(t for t in TRACKS if t["id"] == str(plan["track_id"]))
    music = ASSETS / track["file"]
    if not music.exists():
        # Allow a fallback for common Unicode dash variants or renamed files.
        matches = list(ASSETS.glob(f"*{track['name']}*.mp3"))
        if not matches:
            fail(f"Selected music file not found: {music}. Check exact MP3 names in Assets/.")
        music = matches[0]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    final_path = OUTPUT / f"ObetyPl_{stamp}.mp4"
    # Brand watermark is text, bottom-right. Music fades in/out and is trimmed to 60s.
    # No Facebook posting is performed.
    vf = (
        "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:"
        "text='ObetyPl':fontcolor=white@0.92:fontsize=38:"
        "box=1:boxcolor=black@0.22:boxborderw=14:"
        "x=w-tw-54:y=h-th-46"
    )
    run(["ffmpeg", "-y", "-i", silent_video, "-stream_loop", "-1", "-i", music,
         "-t", str(VIDEO_SECONDS), "-vf", vf,
         "-af", "volume=0.72,afade=t=in:st=0:d=2,afade=t=out:st=55:d=5",
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", final_path])

    plan["selected_track_file"] = music.name
    plan["pexels_clips"] = [
        {"id": x["meta"]["id"], "creator": x["meta"]["creator"],
         "source_page": x["meta"]["page"], "query": x["meta"]["query"],
         "description": x["description"]}
        for x in selected
    ]
    plan["duration_seconds"] = VIDEO_SECONDS
    plan["resolution"] = f"{WIDTH}x{HEIGHT}"
    plan["output"] = str(final_path.relative_to(ROOT))
    plan["facebook_posted"] = False
    (OUTPUT / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nSUCCESS")
    print(f"Video: {final_path}")
    print(f"Music: {track['name']} — {track['artist']} (selected from names only)")
    print("Facebook posting: OFF — the video is only uploaded as a GitHub Actions artifact.")
    print("Please review the Pexels source links and music licenses before publishing.")

if __name__ == "__main__":
    main()
