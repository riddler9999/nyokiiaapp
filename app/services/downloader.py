import asyncio
import httpx
import uuid
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings


async def download_audio(url: str) -> Path:
    """Download audio from URL. Supports direct links and yt-dlp sources."""
    settings.ensure_dirs()
    job_id = uuid.uuid4().hex[:8]

    parsed = urlparse(url)

    # Direct audio file link
    if any(parsed.path.endswith(ext) for ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac")):
        ext = Path(parsed.path).suffix
        out_path = settings.audio_dir / f"{job_id}_raw{ext}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=300) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(out_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(8192):
                        f.write(chunk)
        return out_path

    # Use yt-dlp for other URLs (YouTube, SoundCloud, etc.)
    out_template = str(settings.audio_dir / f"{job_id}_raw.%(ext)s")
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--output", out_template,
        "--no-playlist",
        url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("yt-dlp download timed out after 10 minutes")
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()}")

    # Find the downloaded file
    for f in settings.audio_dir.glob(f"{job_id}_raw.*"):
        return f

    raise FileNotFoundError("Downloaded audio file not found")
