import asyncio
from pathlib import Path

from app.config import settings


async def enhance_audio(input_path: Path) -> Path:
    """Enhance Dhamma audio: normalize loudness, reduce noise, output studio WAV."""
    settings.ensure_dirs()
    stem = input_path.stem.replace("_raw", "")
    output_path = settings.audio_dir / f"{stem}_enhanced.wav"

    # FFmpeg filter chain:
    # 1. highpass: remove low rumble below 80Hz
    # 2. lowpass: cut harsh highs above 14kHz (speech focus)
    # 3. afftdn: adaptive noise reduction
    # 4. acompressor: gentle compression for consistent volume
    # 5. loudnorm: EBU R128 loudness normalization to -16 LUFS
    # 6. aresample: resample to 48kHz studio quality
    filters = (
        "highpass=f=80,"
        "lowpass=f=14000,"
        "afftdn=nf=-25:nr=10:nt=w,"
        "acompressor=threshold=-20dB:ratio=3:attack=5:release=50,"
        "loudnorm=I=-16:TP=-1.5:LRA=11,"
        "aresample=48000"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-af", filters,
        "-ar", "48000",
        "-sample_fmt", "s24",
        "-c:a", "pcm_s24le",
        str(output_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Audio enhancement failed: {stderr.decode()}")

    return output_path
