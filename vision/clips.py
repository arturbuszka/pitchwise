"""Highlight clip extraction via ffmpeg (CLI).

ffmpeg must be on PATH. We use fast stream copy (-c copy), so cuts land on the nearest
keyframes — accurate enough for highlight previews and very fast. Frame-accurate cuts
would require re-encoding (slower) — to consider later.
"""
import subprocess
import tempfile
from pathlib import Path


def probe_video(video_path: str) -> tuple[float | None, float | None]:
    """Returns (duration_seconds, fps) via ffprobe. None on failure."""
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
    """Cuts [start, end] into out_path. Returns True on success."""
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


def concat_clips(clip_paths: list[Path], out_path: Path) -> bool:
    """Stitches clip_paths (in order) into a single out_path.

    Re-encodes via the concat demuxer so it works even when the clips come from
    different source videos with mismatched codecs/resolutions/fps — robustness over
    speed, which is the right trade-off for a highlight reel.
    """
    clips = [p for p in clip_paths if p.exists()]
    if not clips:
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # concat demuxer needs a list file of `file '<path>'` lines.
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_path = Path(f.name)
        for p in clips:
            # forward slashes + escaped single quotes are safest for ffmpeg's parser
            safe = str(p.resolve()).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(list_path),
                "-c:v", "libx264", "-preset", "veryfast",
                "-c:a", "aac",
                # older ffmpeg builds flag the native aac encoder as experimental;
                # this is a no-op on modern builds where it's already stable.
                "-strict", "experimental",
                "-movflags", "+faststart",
                str(out_path),
            ],
            capture_output=True, check=True,
        )
        return out_path.exists()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    finally:
        list_path.unlink(missing_ok=True)
