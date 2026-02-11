import json
import asyncio
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings

TOKEN_FILE = Path("/media/dhamma/youtube_token.json")


def get_youtube_service():
    """Build YouTube API service from stored credentials."""
    if not TOKEN_FILE.exists():
        raise ValueError(
            "YouTube not authorized. Visit /api/youtube/auth to authorize."
        )

    creds_data = json.loads(TOKEN_FILE.read_text())
    creds = Credentials(
        token=creds_data["token"],
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.youtube_client_id,
        client_secret=settings.youtube_client_secret,
    )
    return build("youtube", "v3", credentials=creds)


async def publish_to_youtube(
    video_path: Path,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    thumbnail_path: Path | None = None,
) -> str:
    """Upload video to YouTube with optional custom thumbnail."""
    if tags is None:
        tags = [
            "Dhamma", "Buddhism", "Myanmar", "Burmese",
            "တရားတော်", "ဗုဒ္ဓ", "Theravada", "Meditation",
        ]

    body = {
        "snippet": {
            "title": title,
            "description": description or f"🙏 {title}\n\nDhamma Audio → Video\nMyanmar Buddhist Teaching",
            "tags": tags,
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "my",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,
    )

    def _upload():
        youtube = get_youtube_service()
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )
        response = None
        while response is None:
            _, response = request.next_chunk()

        video_id = response["id"]

        # Set custom thumbnail if available
        if thumbnail_path and thumbnail_path.exists():
            thumb_media = MediaFileUpload(
                str(thumbnail_path), mimetype="image/png"
            )
            youtube.thumbnails().set(
                videoId=video_id, media_body=thumb_media
            ).execute()

        return response

    response = await asyncio.to_thread(_upload)
    video_id = response["id"]
    return f"https://www.youtube.com/watch?v={video_id}"
