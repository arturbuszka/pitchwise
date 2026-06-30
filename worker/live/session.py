"""Shared detector singleton and rolling stats tracker for live sessions."""
from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vision.detector import Detector

_shared_detector: "Detector | None" = None


def get_shared_detector() -> "Detector":
    global _shared_detector
    if _shared_detector is None:
        from vision.detector import Detector
        from live.config import settings

        model_path = settings.effective_yolo_model_path
        _shared_detector = Detector(
            model_path=model_path,
            frame_stride=1,
            imgsz=getattr(settings, "live_imgsz", None),
        )
    return _shared_detector


class StatsTracker:
    def __init__(self, window: int = 30):
        self._infer_times: deque[float] = deque(maxlen=window)
        self._frame_times: deque[float] = deque(maxlen=window)
        self._last_frame_t: float | None = None
        self._last_counts: dict[str, int] = {}

    def record(self, infer_ms: float, counts: dict[str, int]) -> None:
        self._infer_times.append(infer_ms)
        self._last_counts = counts
        now = time.monotonic()
        if self._last_frame_t is not None:
            self._frame_times.append(now - self._last_frame_t)
        self._last_frame_t = now

    def fps(self) -> float:
        if len(self._frame_times) < 2:
            return 0.0
        avg = sum(self._frame_times) / len(self._frame_times)
        return 1.0 / avg if avg > 0 else 0.0

    def avg_infer_ms(self) -> float:
        if not self._infer_times:
            return 0.0
        return sum(self._infer_times) / len(self._infer_times)
