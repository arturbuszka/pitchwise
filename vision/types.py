"""Lekkie typy współdzielone przez moduły vision — bez zależności od ciężkich
bibliotek CV, żeby dało się je importować wszędzie (także w API)."""
from dataclasses import dataclass, field


# Klasy obiektów, których oczekujemy od modelu piłkarskiego (Roboflow sports /
# football-players-detection). Mapowanie indeksów klas modelu na te nazwy odbywa
# się w detektorze.
CLASS_BALL = "ball"
CLASS_PLAYER = "player"
CLASS_GOALKEEPER = "goalkeeper"
CLASS_REFEREE = "referee"


@dataclass
class Detection:
    cls: str                       # jedna z CLASS_*
    xyxy: tuple[float, float, float, float]
    confidence: float
    track_id: int | None = None    # nadawany przez tracker


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
