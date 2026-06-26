import os
import tempfile
from pathlib import Path

try:
    # In Docker: PYTHONPATH=/app, worker/app is copied as /app/app/
    from app.config import Settings, get_settings
except ModuleNotFoundError:
    # Local dev: running from repo root with worker/app on path as worker.app
    from worker.app.config import Settings, get_settings  # type: ignore

settings: Settings = get_settings()

# Where live sessions write HLS segments. The StaticFiles mount (server.py) and the
# ffmpeg output dir (external_session / file_session) MUST resolve to the same path.
# On Linux/Docker this is /tmp/live_hls; on a Windows host `/tmp` would resolve to
# the current drive root, so derive it from the OS temp dir instead. Override with
# LIVE_HLS_DIR if needed.
HLS_BASE_DIR = Path(os.environ.get("LIVE_HLS_DIR") or (Path(tempfile.gettempdir()) / "live_hls"))

__all__ = ["settings", "HLS_BASE_DIR"]
