import asyncio
from pathlib import Path

from telegram import Bot
from telegram.constants import ParseMode

from app.config import settings


async def publish_to_telegram(
    video_path: Path,
    title: str,
    description: str = "",
) -> str:
    """Upload video to Telegram channel/chat."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required")

    bot = Bot(token=token)

    caption = f"🙏 *{title}*"
    if description:
        caption += f"\n\n{description}"
    caption += "\n\n🎙 Dhamma Audio → Video"

    file_size = video_path.stat().st_size

    # Telegram limit: 50MB for bots
    if file_size > 50 * 1024 * 1024:
        # Send as document for larger files
        async with bot:
            msg = await bot.send_document(
                chat_id=chat_id,
                document=open(video_path, "rb"),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                read_timeout=300,
                write_timeout=300,
            )
    else:
        async with bot:
            msg = await bot.send_video(
                chat_id=chat_id,
                video=open(video_path, "rb"),
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                supports_streaming=True,
                read_timeout=300,
                write_timeout=300,
            )

    return f"Telegram message sent: {msg.message_id}"
