"""FFmpeg video rendering and audio mixing."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from src.config import DURATION, FPS, HEIGHT, WIDTH

logger = logging.getLogger(__name__)


def run_ffmpeg(args: list) -> None:
    logger.info("+ %s", " ".join(map(str, args)))
    subprocess.run(list(map(str, args)), check=True)


def render_scene(source: Path, destination: Path, seconds: float = 15.0) -> None:
    """Scale + center-crop to 1080x1920, preserve motion, no Ken-Burns."""
    video_filter = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"trim=duration={seconds},setpts=PTS-STARTPTS,setsar=1,fps={FPS}"
    )
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-stream_loop",
            "-1",
            "-i",
            source,
            "-t",
            str(seconds),
            "-vf",
            video_filter,
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-movflags",
            "+faststart",
            destination,
        ]
    )


def make_final_video(clips: list[Path], music_path: Path | None, output: Path) -> None:
    work = clips[0].parent
    concat = work / "concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for clip in clips:
            f.write("file '" + str(clip.resolve()).replace("'", "'\\''") + "'\n")

    joined = work / "joined.mp4"
    run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat,
            "-c",
            "copy",
            joined,
        ]
    )

    font = next(
        (
            p
            for p in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]
            if Path(p).is_file()
        ),
        None,
    )
    if font:
        vf = (
            f"drawtext=fontfile='{font}':text='ObetyPl':"
            f"fontcolor=white@0.55:fontsize=28:"
            f"shadowcolor=black@0.40:shadowx=2:shadowy=2:"
            f"x=w-tw-40:y=h-th-56"
        )
    else:
        vf = "drawbox=x=w-180:y=h-90:w=150:h=40:color=black@0.25:t=fill"

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", joined]
    if music_path and music_path.is_file():
        cmd += [
            "-stream_loop",
            "-1",
            "-i",
            music_path,
            "-filter_complex",
            (
                f"[0:v]{vf}[v];"
                f"[1:a]atrim=duration={DURATION},asetpts=PTS-STARTPTS,"
                f"volume=0.45,afade=t=in:st=0:d=3,afade=t=out:st={DURATION - 6}:d=6[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
        ]
    else:
        logger.warning("No music; exporting without audio")
        cmd += ["-vf", vf, "-map", "0:v:0", "-an"]

    cmd += [
        "-t",
        str(DURATION),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(FPS),
    ]
    if music_path and music_path.is_file():
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-movflags", "+faststart", output]
    run_ffmpeg(cmd)
