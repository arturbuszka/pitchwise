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
    # Path to a football-specific YOLO model (players/goalkeeper/referee/ball). The
    # default points at the Roboflow `football-players-detection` weights vendored under
    # worker/models — see worker/models/README.md to fetch them. Empty or a missing file
    # falls back to the COCO `yolo11n.pt` (see effective_yolo_model_path), so dev works
    # without the model present, just with worse ball detection.
    yolo_model_path: str = "models/football.pt"
    # ffmpeg binary used for live HLS encoding. Defaults to PATH lookup; set
    # FFMPEG_PATH to an absolute path when an older ffmpeg precedes it on PATH
    # (e.g. a Panda3D-bundled build that lacks -hls_flags).
    ffmpeg_path: str = "ffmpeg"
    # YOLO inference resolution for live sessions. 640 = model default (best quality,
    # ~28 fps on a GTX 1660). Lower it (e.g. 480) to trade accuracy for speed on
    # weaker GPUs/CPU.
    live_imgsz: int = 640
    # Live pipeline mode (switch with LIVE_PIPELINE_MODE + worker restart):
    #   "passthrough" — raw frames cv2 -> ffmpeg, NO analysis. Lightest, always works;
    #                   the safe default for confirming the stream renders.
    #   "detect"      — run YOLO + draw overlay (boxes/labels/traces) on every frame.
    #                   Heavier; lower fps until the frame-pacing fix lands.
    live_pipeline_mode: str = "passthrough"
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
    def effective_yolo_model_path(self) -> str | None:
        """Resolves the model to actually load. Returns the configured football model
        when its file exists, otherwise None so the detector falls back to the bundled
        COCO `yolo11n.pt`. Keeps dev working before the model has been fetched."""
        path = self.yolo_model_path.strip()
        if not path:
            return None
        if Path(path).is_file():
            return path
        return None

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
