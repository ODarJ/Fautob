#!/usr/bin/env python3
"""ObetyPl 60-second scenic video generator: Groq plans scenes, Pexels supplies footage."""
import json, os, random, re, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "Assets"
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "").strip()
INPUT_SCENERY = os.getenv("INPUT_SCENERY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PEXELS_URL = "https://api.pexels.com/videos/search"
DURATION, WIDTH, HEIGHT, FPS = 60, 1920, 1080, 30

MUSIC = {
    "silent descent": "01 — Silent Descent.mp3",
    "beautiful dream": "02 — Beautiful Dream.mp3",
    "classical vibes 2": "03 — Classical vibes 2.mp3",
    "emotional": "04 — Emotional.mp3",
    "dramatic piano background": "05 — Dramatic Piano Background.mp3",
}


def fail(message):
    print("ERROR:", message, file=sys.stderr)
    raise SystemExit(1)


def run(args):
    print("+", " ".join(map(str, args)))
    subprocess.run(list(map(str, args)), check=True)


def call_groq(prompt, retries=4):
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": "You plan cinematic nature videos. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }
    last_error = "Unknown error"
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=(20, 90))
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = f"Groq HTTP {response.status_code}: {response.text[:300]}"
                if attempt < retries:
                    delay = min(attempt * 6, 24)
                    print(f"Groq temporarily unavailable; retrying in {delay}s...")
                    time.sleep(delay)
                    continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Groq response is not a JSON object")
            return result
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(min(attempt * 5, 20))
    fail(f"Groq scene planning failed after {retries} attempts: {last_error}")


def fallback_plan():
    idea = INPUT_SCENERY or random.choice([
        "misty green mountains at sunrise", "quiet tropical beach at golden hour",
        "peaceful forest after rain", "lake reflecting distant mountains",
        "rolling green hills beneath dramatic clouds", "waterfall in a lush forest",
    ])
    return {
        "title": idea.title(), "mood": "peaceful, cinematic, reflective",
        "music_track": random.choice(list(MUSIC)),
        "scenes": [
            {"description": f"Wide establishing view of {idea}, soft natural light", "query": idea, "seconds": 15},
            {"description": f"Atmospheric nature view of {idea}, gentle movement", "query": f"{idea} cinematic nature", "seconds": 15},
            {"description": f"Detailed scenic landscape related to {idea}", "query": f"{idea} scenic landscape", "seconds": 15},
            {"description": f"Wide closing landscape of {idea}, warm soft light", "query": f"{idea} sunset nature", "seconds": 15},
        ],
    }


def plan_scenes():
    scenery = INPUT_SCENERY or "Choose a beautiful natural landscape."
    prompt = f"""
Plan a 60-second 16:9 cinematic scenic nature video for a page named ObetyPl.
Scenery request: {scenery}
Return JSON with:
"title": short title (max 7 words),
"mood": short mood description,
"music_track": exactly one of {list(MUSIC.keys())},
"scenes": exactly 4 objects, each containing "description", "query" (short Pexels video search query), "seconds": 15.
Use realistic natural landscapes, no people, no text or logos in footage, coherent peaceful cinematic mood.
Return JSON only, no markdown.
"""
    try:
        data = call_groq(prompt)
        scenes = data.get("scenes")
        if not isinstance(scenes, list) or len(scenes) != 4:
            raise ValueError("Expected four scenes")
        clean = []
        for s in scenes:
            if not isinstance(s, dict) or not str(s.get("query", "")).strip():
                raise ValueError("A scene has no search query")
            clean.append({
                "description": str(s.get("description", s["query"])).strip()[:500],
                "query": str(s["query"]).strip()[:180],
                "seconds": 15,
            })
        track = str(data.get("music_track", "")).strip().lower()
        if track not in MUSIC:
            track = random.choice(list(MUSIC))
        return {
            "title": str(data.get("title", "ObetyPl Scenic Moments")).strip()[:100],
            "mood": str(data.get("mood", "peaceful cinematic")).strip()[:200],
            "music_track": track,
            "scenes": clean,
        }
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Invalid AI plan ({exc}); using a basic fallback plan.")
        return fallback_plan()


def pexels_video_url(query):
    response = requests.get(
        PEXELS_URL,
        headers={"Authorization": PEXELS_KEY},
        params={"query": query, "orientation": "landscape", "size": "large", "per_page": 12},
        timeout=45,
    )
    response.raise_for_status()
    videos = response.json().get("videos", [])
    options = []
    for video in videos:
        for vf in video.get("video_files", []):
            link = vf.get("link")
            w, h = int(vf.get("width") or 0), int(vf.get("height") or 0)
            if link:
                options.append((w * h if w >= 1280 and h >= 720 else 0, link))
    if not options:
        return None
    options.sort(key=lambda x: x[0], reverse=True)
    return random.choice(options[:min(5, len(options))])[1]


def download_clip(query, destination):
    for term in dict.fromkeys([query, f"{query} landscape nature", "beautiful nature landscape cinematic"]):
        try:
            url = pexels_video_url(term)
            if not url:
                print("No Pexels results for:", term)
                continue
            with requests.get(url, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                with open(destination, "wb") as f:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
            if destination.stat().st_size > 100_000:
                return destination
            destination.unlink(missing_ok=True)
        except requests.RequestException as exc:
            print(f"Pexels error for {term!r}: {exc}")
    return None


def render_scene(source, destination, seconds=15):
    frames = int(seconds * FPS)
    video_filter = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan=z='min(zoom+0.00035,1.035)':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"trim=duration={seconds},setpts=PTS-STARTPTS,setsar=1"
    )
    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", source, "-t", str(seconds),
        "-vf", video_filter, "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-movflags", "+faststart", destination,
    ])


def find_music(track):
    expected = ASSETS / MUSIC.get(track, "")
    if expected.is_file():
        return expected
    wanted = re.sub(r"[^a-z0-9]", "", track.lower())
    if ASSETS.is_dir():
        audio = [p for p in ASSETS.iterdir() if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}]
        for p in audio:
            stem = re.sub(r"[^a-z0-9]", "", p.stem.lower())
            if wanted and (wanted in stem or stem in wanted):
                return p
        if audio:
            return random.choice(audio)
    return None


def make_final_video(clips, music, output):
    concat = WORK / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for clip in clips:
            f.write("file '" + str(clip.resolve()).replace("'", "'\\''") + "'\n")
    joined = WORK / "joined.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", joined])

    font = next((p for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ] if Path(p).is_file()), None)
    if font:
        vf = f"drawtext=fontfile='{font}':text='ObetyPl':fontcolor=white@0.62:fontsize=30:shadowcolor=black@0.45:shadowx=2:shadowy=2:x=w-tw-48:y=h-th-38"
    else:
        vf = "drawbox=x=w-205:y=h-75:w=170:h=42:color=black@0.20:t=fill"

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", joined]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music,
                "-filter_complex",
                f"[0:v]{vf}[v];[1:a]atrim=duration={DURATION},asetpts=PTS-STARTPTS,volume=0.24,afade=t=in:st=0:d=2,afade=t=out:st={DURATION-4}:d=4[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        print("WARNING: No music found in Assets/; exporting without audio.")
        cmd += ["-vf", vf, "-map", "0:v:0", "-an"]
    cmd += ["-t", str(DURATION), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS)]
    if music:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-movflags", "+faststart", output]
    run(cmd)


def main():
    if not GROQ_KEY:
        fail("GROQ_API_KEY is missing. Add it in GitHub repository Settings > Secrets and variables > Actions.")
    if not PEXELS_KEY:
        fail("PEXELS_API_KEY is missing. Add it in GitHub repository Settings > Secrets and variables > Actions.")
    if not shutil.which("ffmpeg"):
        fail("FFmpeg is not installed or is not in PATH.")

    WORK.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    print("Asking Groq to plan the video...")
    plan = plan_scenes()
    plan["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    plan["model"] = GROQ_MODEL
    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", plan["title"]).strip("_") or "Scenic_Moments"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output = OUTPUT / f"ObetyPl_{timestamp}_{safe_title[:45]}.mp4"
    (OUTPUT / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    clips = []
    for i, scene in enumerate(plan["scenes"], 1):
        source, rendered = WORK / f"source_{i}.mp4", WORK / f"scene_{i}.mp4"
        print(f"\nScene {i}/4: {scene['description']}")
        if not download_clip(scene["query"], source):
            fail(f"Could not download Pexels footage for scene {i}. Check PEXELS_API_KEY and rerun.")
        render_scene(source, rendered, 15)
        clips.append(rendered)

    music = find_music(plan["music_track"])
    print("Music:", music.name if music else "none")
    make_final_video(clips, music, output)
    print("\nSUCCESS:", output)
    print(f"Size: {output.stat().st_size / (1024 * 1024):.1f} MB")
    print("Plan:", OUTPUT / "plan.json")


if __name__ == "__main__":
    main()
