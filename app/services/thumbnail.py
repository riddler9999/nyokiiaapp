import uuid
from pathlib import Path

import httpx

from app.config import settings

FAL_RUN_URL = "https://fal.run"

# System prompt for the LLM to generate image prompts
PROMPT_SYSTEM = (
    "You are an expert at writing image generation prompts for Buddhist-themed YouTube thumbnails. "
    "Given a Dhamma talk title, generate a single detailed image prompt. "
    "Focus on Myanmar Buddhist imagery: Shwedagon Pagoda, Bagan temples, golden pagodas, "
    "Buddha statues, lotus flowers, monks, warm golden light, serene atmosphere. "
    "Output ONLY the image prompt, nothing else. Keep it under 200 words. "
    "The image should be cinematic, photorealistic, 16:9 landscape, warm gold and maroon palette."
)


async def _generate_image_prompt(title: str) -> str:
    """Use fal.ai OpenRouter (Gemini) to generate an optimized image prompt from the title."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{FAL_RUN_URL}/openrouter/router/openai/v1/chat/completions",
            headers={
                "Authorization": f"Key {settings.fal_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash",
                "messages": [
                    {"role": "system", "content": PROMPT_SYSTEM},
                    {"role": "user", "content": f"Generate a thumbnail image prompt for this Dhamma talk: {title}"},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"].strip()


async def _generate_image(prompt: str) -> str:
    """Use fal.ai nano-banana-pro to generate a thumbnail image. Returns the image URL."""
    async with httpx.AsyncClient(timeout=120) as client:
        # Submit to queue
        resp = await client.post(
            f"{FAL_RUN_URL}/fal-ai/nano-banana-pro",
            headers={
                "Authorization": f"Key {settings.fal_key}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "aspect_ratio": "16:9",
                "num_images": 1,
                "output_format": "png",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return data["images"][0]["url"]


async def generate_thumbnail(
    title: str,
    custom_prompt: str = "",
) -> Path:
    """Generate a thumbnail image using fal.ai.

    Flow:
        1. If no custom prompt, use OpenRouter (Gemini) to generate one from the title
        2. Use nano-banana-pro to generate the image
        3. Download and save the image

    Args:
        title: The Dhamma talk title.
        custom_prompt: Optional custom image prompt. If empty, auto-generates via LLM.

    Returns:
        Path to the downloaded thumbnail image.
    """
    settings.ensure_dirs()
    if not settings.fal_key:
        raise ValueError("FAL_KEY not configured")

    # Step 1: Get or generate the image prompt
    if custom_prompt.strip():
        image_prompt = custom_prompt
    else:
        image_prompt = await _generate_image_prompt(title)

    # Step 2: Generate image with nano-banana-pro
    image_url = await _generate_image(image_prompt)

    # Step 3: Download the generated image
    job_id = uuid.uuid4().hex[:8]
    out_path = settings.thumbs_dir / f"{job_id}_thumbnail.png"

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        out_path.write_bytes(img_resp.content)

    return out_path
