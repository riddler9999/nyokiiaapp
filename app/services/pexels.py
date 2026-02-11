import asyncio
import httpx
import random
from pathlib import Path

from app.config import settings

SEARCH_QUERIES = [
    "Shwedagon pagoda Myanmar",
    "Bagan temples Myanmar",
    "Buddhist temple Myanmar",
    "Buddha statue golden",
    "Myanmar pagoda sunset",
    "Buddhist monastery Myanmar",
    "Mandalay temple",
    "Buddhist meditation temple",
    "Golden pagoda Buddhism",
    "Myanmar Buddhist ceremony",
]

PEXELS_VIDEO_API = "https://api.pexels.com/videos/search"


async def search_and_download_stock(count: int = 5) -> list[Path]:
    """Search Pexels for Myanmar Buddhist videography and download clips."""
    settings.ensure_dirs()
    api_key = settings.pexels_api_key
    if not api_key:
        raise ValueError("PEXELS_API_KEY not configured")

    downloaded: list[Path] = []
    queries = random.sample(SEARCH_QUERIES, min(count, len(SEARCH_QUERIES)))

    async with httpx.AsyncClient(timeout=120) as client:
        for i, query in enumerate(queries):
            if len(downloaded) >= count:
                break

            resp = await client.get(
                PEXELS_VIDEO_API,
                headers={"Authorization": api_key},
                params={
                    "query": query,
                    "per_page": 5,
                    "size": "large",
                    "orientation": "landscape",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            videos = data.get("videos", [])
            if not videos:
                continue

            video = random.choice(videos)
            # Pick HD or Full HD file
            video_files = video.get("video_files", [])
            hd_files = [
                f for f in video_files
                if f.get("height", 0) >= 720 and f.get("quality") in ("hd", "sd")
            ]
            if not hd_files:
                hd_files = video_files

            if not hd_files:
                continue

            # Prefer 1080p
            chosen = sorted(hd_files, key=lambda f: abs(f.get("height", 0) - 1080))[0]
            video_url = chosen["link"]

            out_path = settings.stock_dir / f"stock_{i:02d}.mp4"
            async with client.stream("GET", video_url) as vresp:
                vresp.raise_for_status()
                with open(out_path, "wb") as f:
                    async for chunk in vresp.aiter_bytes(8192):
                        f.write(chunk)

            downloaded.append(out_path)

            # Small delay to respect rate limits
            await asyncio.sleep(0.5)

    if not downloaded:
        raise RuntimeError("No stock videos found from Pexels")

    return downloaded
