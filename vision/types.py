"""Lightweight types shared across the vision modules — no dependency on heavy CV
libraries, so they can be imported anywhere (including the API)."""
from dataclasses import dataclass, field


# Object classes we expect from a football-specific model (Roboflow sports /
# football-players-detection). Mapping the model's class indices onto these names
# happens in the detector.
CLASS_BALL = "ball"
CLASS_PLAYER = "player"
CLASS_GOALKEEPER = "goalkeeper"
CLASS_REFEREE = "referee"
# Stage 2 hook: goal detection (posts/net). Inactive until the model returns this
# class — then events.py will use goal-line crossing as a strong signal instead of
# the ball-motion heuristic alone.
CLASS_GOAL = "goal"


@dataclass
class Detection:
    cls: str                       # one of CLASS_*
    xyxy: tuple[float, float, float, float]
    confidence: float
    track_id: int | None = None    # assigned by the tracker


@dataclass
class FrameResult:
    frame_index: int
    timestamp_seconds: float
    detections: list[Detection] = field(default_factory=list)

    @property
    def ball(self) -> Detection | None:
        balls = [d for d in self.detections if d.cls == CLASS_BALL]
        if not balls:
            return None
        return max(balls, key=lambda d: d.confidence)


@dataclass
class DetectedEvent:
    type: str                      # "goal" | "shot"
    timestamp_seconds: float
    confidence: float
    label: str | None = None
