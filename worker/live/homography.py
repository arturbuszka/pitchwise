"""Pitch homography: maps pixel positions to real-world pitch coordinates.

Standard football pitch: 105m (length) x 68m (width).
Origin (0,0) = left goal line, bottom touchline.

Usage:
    h = Homography.from_points(pixel_pts, pitch_pts)  # min 4 pairs
    pitch_x, pitch_y = h.project(xyxy)               # bottom-center of bbox
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Homography:
    _matrix: object  # numpy 3x3

    @classmethod
    def from_points(
        cls,
        pixel_pts: list[tuple[float, float]],
        pitch_pts: list[tuple[float, float]],
    ) -> "Homography":
        if len(pixel_pts) < 4 or len(pitch_pts) < 4:
            raise ValueError("Need at least 4 point pairs for homography")
        import numpy as np
        import cv2

        src = np.array(pixel_pts, dtype=np.float32)
        dst = np.array(pitch_pts, dtype=np.float32)
        H, _ = cv2.findHomography(src, dst, cv2.RANSAC)
        if H is None:
            raise ValueError("findHomography failed — check point correspondences")
        return cls(_matrix=H)

    def project(self, xyxy: tuple[float, float, float, float]) -> tuple[float, float]:
        """Project foot position (bottom-center of bbox) to pitch coordinates."""
        import numpy as np

        x1, y1, x2, y2 = xyxy
        foot_x = (x1 + x2) / 2.0
        foot_y = y2
        pt = np.array([foot_x, foot_y, 1.0], dtype=np.float64)
        projected = self._matrix @ pt
        w = projected[2]
        if abs(w) < 1e-9:
            return (0.0, 0.0)
        return (float(projected[0] / w), float(projected[1] / w))


def pixel_to_normalized(
    xyxy: tuple[float, float, float, float],
    frame_w: int,
    frame_h: int,
) -> tuple[float, float]:
    """Fallback when no homography is set: normalize foot position to [0,1]."""
    x1, _, x2, y2 = xyxy
    foot_x = (x1 + x2) / 2.0
    return (foot_x / frame_w if frame_w else 0.0, y2 / frame_h if frame_h else 0.0)
