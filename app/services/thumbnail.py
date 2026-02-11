import asyncio
import uuid
from pathlib import Path

import httpx

from app.config import settings

# Default prompt template for Dhamma thumbnails
DEFAULT_PROMPT_TEMPLATE = (
    "A stunning YouTube thumbnail for a Burmese Buddhist Dhamma talk titled \"{title}\". "
    "Feature the golden Shwedagon Pagoda at sunset with warm golden light rays, "
    "a serene Buddha statue in meditation pose, Myanmar Buddhist temple architecture, "
    "soft lotus flowers, and a peaceful spiritual atmosphere. "
    "Cinematic lighting, 16:9 aspect ratio, photorealistic, "
    "warm gold and maroon color palette, no text overlays."
)


async def generate_thumbnail(
    title: str,
    custom_prompt: str = "",
) -> Path:
    """Generate a thumbnail image using OpenAI DALL-E.

    Args:
        title: The Dhamma talk title (used in default prompt).
        custom_prompt: Optional custom prompt. If empty, uses the default
                       Buddhist-themed template with the title inserted.

    Returns:
        Path to the downloaded thumbnail image.
    """
    settings.ensure_dirs()
    api_key = settings.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    # Build the prompt
    if custom_prompt.strip():
        prompt = custom_prompt
    else:
        prompt = DEFAULT_PROMPT_TEMPLATE.format(title=title)

    job_id = uuid.uuid4().hex[:8]
    out_path = settings.thumbs_dir / f"{job_id}_thumbnail.png"

    # Call OpenAI Images API (DALL-E 3)
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1792x1024",
                "quality": "hd",
                "style": "vivid",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    image_url = data["data"][0]["url"]

    # Download the generated image
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        out_path.write_bytes(img_resp.content)

    return out_path
