from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage / DB
    storage_dir: Path = Path("./storage")
    # Postgres (the Python worker and the .NET API share the same database). .NET owns the schema.
    database_url: str = (
        "postgresql+asyncpg://pitchwise:pitchwise@localhost:5432/pitchwise"
    )

    # Queue
    redis_url: str = "redis://localhost:6379"
    analysis_inline: bool = False  # True = analyze inside the request, no Redis/worker (dev/MVP)

    # LLM (provider-agnostic: OpenAI-compatible chat API)
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # Vision
    yolo_model_path: str = ""
    # Which frames to analyze. A smaller stride = a denser ball track (better event
    # detection on fast motion/close-ups) but slower analysis. 3 is a compromise; raise
    # it (e.g. 5) for long recordings where time matters.
    frame_stride: int = 3
    generate_clips: bool = False  # per-event clip extraction — disabled for now (set GENERATE_CLIPS=1 to enable)
    clip_pre_seconds: float = 6.0
    clip_post_seconds: float = 4.0

    # CORS
    web_origin: str = "http://localhost:3000"
    web_origin_alt: str = "http://localhost:3001"

    # --- derived paths ---
    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def clips_dir(self) -> Path:
        return self.storage_dir / "clips"

    @property
    def hls_dir(self) -> Path:
        return self.storage_dir / "hls"

    def ensure_dirs(self) -> None:
        for d in (self.storage_dir, self.uploads_dir, self.clips_dir, self.hls_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
