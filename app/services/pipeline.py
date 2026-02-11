import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from app.config import settings
from app.services.downloader import download_audio
from app.services.enhancer import enhance_audio
from app.services.pexels import search_and_download_stock
from app.services.compiler import compile_video
from app.services.thumbnail import generate_thumbnail
from app.services.telegram_pub import publish_to_telegram
from app.services.youtube_pub import publish_to_youtube


@dataclass
class JobStatus:
    id: str
    status: str = "pending"
    step: str = ""
    progress: int = 0
    error: str = ""
    output_path: str = ""
    thumbnail_path: str = ""
    telegram_result: str = ""
    youtube_url: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# In-memory job store
jobs: dict[str, JobStatus] = {}


async def run_pipeline(
    job_id: str,
    audio_url: str,
    title: str,
    description: str = "",
    publish_telegram: bool = True,
    publish_youtube: bool = True,
    stock_clip_count: int = 5,
    generate_thumb: bool = True,
    thumbnail_prompt: str = "",
):
    """Run the full Dhamma audio-to-video pipeline."""
    job = jobs[job_id]

    try:
        # Step 1: Download audio
        job.step = "downloading"
        job.status = "running"
        job.progress = 10
        raw_audio = await download_audio(audio_url)

        # Step 2: Enhance audio
        job.step = "enhancing"
        job.progress = 25
        enhanced_audio = await enhance_audio(raw_audio)

        # Step 3: Search & download stock videos
        job.step = "fetching_stock"
        job.progress = 40
        stock_videos = await search_and_download_stock(count=stock_clip_count)

        # Step 4: Generate thumbnail
        thumbnail_path = None
        if generate_thumb and settings.openai_api_key:
            job.step = "generating_thumbnail"
            job.progress = 50
            try:
                thumbnail_path = await generate_thumbnail(title, thumbnail_prompt)
                job.thumbnail_path = str(thumbnail_path)
            except Exception as e:
                job.thumbnail_path = f"Error: {e}"

        # Step 5: Compile video
        job.step = "compiling"
        job.progress = 65
        output_video = await compile_video(enhanced_audio, stock_videos, title)
        job.output_path = str(output_video)

        # Step 6: Publish
        job.step = "publishing"
        job.progress = 80

        publish_tasks = []
        if publish_telegram:
            publish_tasks.append(
                publish_to_telegram(output_video, title, description, thumbnail_path)
            )
        if publish_youtube:
            publish_tasks.append(
                publish_to_youtube(output_video, title, description, thumbnail_path=thumbnail_path)
            )

        if publish_tasks:
            results = await asyncio.gather(*publish_tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    if i == 0 and publish_telegram:
                        job.telegram_result = f"Error: {result}"
                    else:
                        job.youtube_url = f"Error: {result}"
                else:
                    if i == 0 and publish_telegram:
                        job.telegram_result = str(result)
                    else:
                        job.youtube_url = str(result)

        # Step 7: Cleanup temp files
        job.step = "cleanup"
        job.progress = 95
        raw_audio.unlink(missing_ok=True)
        for sv in stock_videos:
            sv.unlink(missing_ok=True)

        job.step = "done"
        job.status = "completed"
        job.progress = 100

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
