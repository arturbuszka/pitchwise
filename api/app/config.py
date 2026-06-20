from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage / DB
    storage_dir: Path = Path("./storage")
    database_url: str = "sqlite+aiosqlite:///./storage/app.db"

    # Kolejka
    redis_url: str = "redis://localhost:6379"
    analysis_inline: bool = False  # True = analiza w request, bez Redis/workera (dev/MVP)

    # LLM (provider-agnostic: OpenAI-compatible chat API)
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Vision
    yolo_model_path: str = ""
    frame_stride: int = 5
    clip_pre_seconds: float = 6.0
    clip_post_seconds: float = 4.0

    # CORS
    web_origin: str = "http://localhost:3000"
    web_origin_alt: str = "http://localhost:3001"

    # --- ścieżki pochodne ---
    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def clips_dir(self) -> Path:
        return self.storage_dir / "clips"

    def ensure_dirs(self) -> None:
        for d in (self.storage_dir, self.uploads_dir, self.clips_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
