from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    pexels_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    fal_key: str = ""
    media_dir: str = "/media/dhamma"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def media_path(self) -> Path:
        return Path(self.media_dir)

    @property
    def audio_dir(self) -> Path:
        return self.media_path / "audio"

    @property
    def video_dir(self) -> Path:
        return self.media_path / "video"

    @property
    def stock_dir(self) -> Path:
        return self.media_path / "stock"

    @property
    def output_dir(self) -> Path:
        return self.media_path / "output"

    @property
    def thumbs_dir(self) -> Path:
        return self.media_path / "thumbnails"

    def ensure_dirs(self):
        for d in [self.audio_dir, self.video_dir, self.stock_dir, self.output_dir, self.thumbs_dir]:
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
