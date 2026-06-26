"""Overlay rendering for live sessions using supervision annotators."""
from __future__ import annotations

from dataclasses import dataclass, field

from vision.types import CLASS_BALL, CLASS_PLAYER, CLASS_REFEREE, FrameResult


@dataclass
class OverlayFlags:
    boxes: bool = True
    labels: bool = True
    traces: bool = False

    def any_overlay(self) -> bool:
        return self.boxes or self.labels or self.traces


_COLOR_MAP = {
    CLASS_PLAYER: (255, 100, 30),    # orange-blue (BGR)
    CLASS_BALL: (0, 220, 255),       # yellow (BGR)
    CLASS_REFEREE: (0, 0, 220),      # red (BGR)
    "goalkeeper": (0, 200, 0),       # green (BGR)
}
_DEFAULT_COLOR = (200, 200, 200)


def draw_overlay(frame, fr: FrameResult, flags: OverlayFlags) -> None:
    """Draw bounding boxes and labels onto frame in-place (BGR numpy array)."""
    import cv2

    for det in fr.detections:
        x1, y1, x2, y2 = (int(v) for v in det.xyxy)
        color = _COLOR_MAP.get(det.cls, _DEFAULT_COLOR)

        if flags.boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        if flags.labels:
            label = det.cls
            if det.track_id is not None:
                label = f"{det.cls} #{det.track_id}"
            cv2.putText(
                frame,
                label,
                (x1, max(y1 - 6, 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )
