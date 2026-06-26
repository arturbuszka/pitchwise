"""Generate an annotated (bounding-box overlay) version of a video file.

Runs YOLO detection on every frame, draws overlays via supervision annotators,
pipes raw BGR frames into ffmpeg for H.264 encoding, then segments the result
into HLS for CDN delivery.

Heavy imports (cv2, torch/ultralytics) are deferred so this module can be
imported without them available.
"""
from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

try:
    from live.overlay import OverlayFlags, draw_overlay
except ModuleNotFoundError:
    from worker.live.overlay import OverlayFlags, draw_overlay  # type: ignore
from vision.detector import Detector
from vision.clips import to_hls


def generate_annotated_video(
    video_path: Path | str,
    out_mp4: Path,
    out_hls_dir: Path,
    *,
    yolo_model_path: str | None = None,
    frame_stride: int = 1,
    flags: OverlayFlags | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> bool:
    """Re-detect + draw overlays on every frame, encode to MP4, segment to HLS.

    Returns True if both MP4 and HLS were produced successfully.
    frame_stride=1 means every frame (slower but smooth overlay).
    """
    import cv2

    if flags is None:
        flags = OverlayFlags(boxes=True, labels=True, traces=False)

    video_path = str(video_path)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{w}x{h}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "pipe:0",
        # no audio stream from raw pipe — preserve audio from source
        "-i", video_path,
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-strict", "experimental",
        "-movflags", "+faststart",
        str(out_mp4),
    ]

    detector = Detector(model_path=yolo_model_path, frame_stride=frame_stride)

    try:
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
    except FileNotFoundError:
        cap.release()
        return False

    frame_count = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_count % frame_stride == 0:
                frame_index = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                timestamp = frame_index / fps
                fr = detector.detect_frame(frame, frame_index, timestamp)
                if flags.any_overlay():
                    draw_overlay(frame, fr, flags)

            proc.stdin.write(frame.tobytes())
            frame_count += 1

            if on_progress and total_frames > 0:
                # annotated render is 0..0.85; HLS segmentation gets 0.85..1.0
                on_progress(min(0.85, frame_count / total_frames * 0.85))

    except BrokenPipeError:
        pass
    finally:
        proc.stdin.close()
        proc.wait()
        cap.release()

    if not out_mp4.exists():
        return False

    if on_progress:
        on_progress(0.85)

    ok = to_hls(out_mp4, out_hls_dir)

    if on_progress:
        on_progress(1.0)

    return ok
