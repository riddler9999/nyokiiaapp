import asyncio
import uuid
from pathlib import Path

from app.config import settings


async def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("ffprobe timed out")
    return float(stdout.decode().strip())


async def compile_video(
    audio_path: Path,
    stock_videos: list[Path],
    title: str = "",
) -> Path:
    """Compile stock videos with audio into a single Dhamma video.

    Strategy: loop and concatenate stock clips to match audio duration,
    add a title overlay, and mux with the enhanced audio.
    """
    settings.ensure_dirs()
    job_id = uuid.uuid4().hex[:8]
    audio_duration = await get_audio_duration(audio_path)

    # Step 1: Create concat list - repeat videos to fill audio duration
    concat_list_path = settings.video_dir / f"{job_id}_concat.txt"
    intermediate_path = settings.video_dir / f"{job_id}_visual.mp4"
    output_path = settings.output_dir / f"{job_id}_dhamma.mp4"

    # Build concat entries — repeat stock clips to exceed audio duration
    entries = []
    total_est = 0.0
    idx = 0
    while total_est < audio_duration + 10:
        video = stock_videos[idx % len(stock_videos)]
        entries.append(f"file '{video}'")
        total_est += 15  # estimate ~15s per clip
        idx += 1

    concat_list_path.write_text("\n".join(entries))

    # Step 2: Concatenate and normalize video clips to 1080p
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-r", "30",
        "-an",
        "-t", str(audio_duration),
        str(intermediate_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *concat_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Video concat timed out after 30 minutes")
    if proc.returncode != 0:
        raise RuntimeError(f"Video concat failed: {stderr.decode()}")

    # Step 3: Mux video + audio, add title overlay if provided
    title_filter = ""
    if title:
        # Escape special characters for FFmpeg drawtext
        safe_title = title.replace("'", "\\'").replace(":", "\\:")
        title_filter = (
            f",drawtext=text='{safe_title}'"
            f":fontsize=42:fontcolor=white:borderw=3:bordercolor=black"
            f":x=(w-text_w)/2:y=50"
            f":enable='between(t,0,8)'"
            f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )

    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(intermediate_path),
        "-i", str(audio_path),
        "-vf", f"null{title_filter}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *mux_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=1800)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("Video mux timed out after 30 minutes")
    if proc.returncode != 0:
        raise RuntimeError(f"Video mux failed: {stderr.decode()}")

    # Cleanup intermediate files
    concat_list_path.unlink(missing_ok=True)
    intermediate_path.unlink(missing_ok=True)

    return output_path
