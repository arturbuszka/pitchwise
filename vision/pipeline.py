"""Vision orchestration: detection → tracking → events → (clips are handled by the API).

The core of the system. Returns a structure the API persists to the DB and uses to cut
clips. Designed as a pure domain function — no DB/HTTP dependencies.
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from vision.clips import probe_video
from vision.detector import Detector
from vision.events import EventConfig, detect_events
from vision.types import DetectedEvent


@dataclass
class PipelineResult:
    duration_seconds: float | None
    fps: float | None
    events: list[DetectedEvent] = field(default_factory=list)
    frames_processed: int = 0


def analyze_video(
    video_path: str,
    *,
    yolo_model_path: str | None = None,
    frame_stride: int = 5,
    event_config: EventConfig | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> PipelineResult:
    """Full recording analysis → detected events.

    on_progress: callback(0..1) for progress reporting (UI/queue).
    """
    duration, fps = probe_video(video_path)

    detector = Detector(model_path=yolo_model_path, frame_stride=frame_stride)

    frames = []
    for fr in detector.run(video_path):
        frames.append(fr)
        if on_progress and duration and fr.timestamp_seconds > 0:
            on_progress(min(0.95, fr.timestamp_seconds / duration))

    events: list[DetectedEvent] = detect_events(frames, event_config)

    if on_progress:
        on_progress(1.0)

    return PipelineResult(
        duration_seconds=duration,
        fps=fps,
        events=events,
        frames_processed=len(frames),
    )
