"""Wycinanie klipów highlightów przez ffmpeg (CLI).

ffmpeg musi być w PATH. Używamy szybkiego kopiowania strumienia (-c copy), więc
cięcie odbywa się na najbliższych klatkach kluczowych — wystarczająco dokładne do
podglądu highlightów i bardzo szybkie. Dla cięcia co do klatki należałoby
re-enkodować (wolniej) — do rozważenia później.
"""
import subprocess
from pathlib import Path


def probe_video(video_path: str) -> tuple[float | None, float | None]:
    """Zwraca (duration_seconds, fps) przez ffprobe. None gdy się nie uda."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=r_frame_rate,duration",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=0",
                video_path,
            ],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None

    duration: float | None = None
    fps: float | None = None
    for line in out.splitlines():
        if line.startswith("duration=") and duration is None:
            try:
                duration = float(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("r_frame_rate="):
            val = line.split("=", 1)[1]
            if "/" in val:
                num, den = val.split("/")
                try:
                    fps = float(num) / float(den) if float(den) else None
                except ValueError:
                    pass
    return duration, fps


def extract_clip(
    video_path: str,
    out_path: Path,
    start_seconds: float,
    end_seconds: float,
) -> bool:
    """Wycina [start, end] do out_path. Zwraca True przy sukcesie."""
    start = max(0.0, start_seconds)
    duration = max(0.5, end_seconds - start)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", f"{start:.3f}",
                "-i", video_path,
                "-t", f"{duration:.3f}",
                "-c", "copy",
                str(out_path),
            ],
            capture_output=True, check=True,
        )
        return out_path.exists()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
