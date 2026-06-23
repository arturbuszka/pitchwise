"""Tests for the event detection heuristics (vision/events.py).

detect_events is a pure function (no CV/DB), so we test it on synthetic ball tracks
built from FrameResult. We assume a 1920x1080 frame — the edge zone
(edge_zone_frac=0.15) is x<=288 or x>=1632.
"""
import sys
from pathlib import Path

# Allow running the tests without installing the package (the repo is not installable).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vision.events import EventConfig, detect_events  # noqa: E402
from vision.types import CLASS_BALL, Detection, FrameResult  # noqa: E402

FPS = 25.0
STRIDE = 1  # in the tests each FrameResult is the next analyzed sample


def _ball_frame(idx: int, cx: float, cy: float, conf: float = 0.9) -> FrameResult:
    half = 8.0
    det = Detection(
        cls=CLASS_BALL,
        xyxy=(cx - half, cy - half, cx + half, cy + half),
        confidence=conf,
    )
    return FrameResult(frame_index=idx, timestamp_seconds=idx / FPS, detections=[det])


def _empty_frame(idx: int) -> FrameResult:
    return FrameResult(frame_index=idx, timestamp_seconds=idx / FPS, detections=[])


def _anchor_frame(idx: int) -> FrameResult:
    """A background frame with detections in the corners — fixes the frame size (~1920x1080)
    regardless of where the ball currently is."""
    corner = Detection(cls="player", xyxy=(1900.0, 1060.0, 1920.0, 1080.0), confidence=0.9)
    return FrameResult(frame_index=idx, timestamp_seconds=idx / FPS, detections=[corner])


def test_goal_trajectory_toward_edge_emits_high_confidence_goal():
    """The ball accelerates toward the right edge, reaches the zone and disappears => goal."""
    frames: list[FrameResult] = []
    idx = 0
    # calm motion (low speeds build the median)
    for x in range(800, 1000, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # a sharp sprint toward the right edge (large x jumps)
    for x in range(1000, 1750, 120):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # the ball disappears after entering the edge zone
    for _ in range(6):
        frames.append(_anchor_frame(idx))
        idx += 1

    events = detect_events(frames)
    goals = [e for e in events if e.type == "goal"]
    assert len(goals) == 1, f"expected 1 goal, got {events}"
    assert goals[0].confidence >= 0.6


def test_ball_vanishes_in_center_is_not_a_goal():
    """The ball disappearing in the CENTER of the frame = a detection error, not a goal. Key regression."""
    frames: list[FrameResult] = []
    idx = 0
    for x in range(800, 1000, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # spike, but the ball stays in the center (x ~ 960, far from the edge)
    for x in range(1000, 1100, 120):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    for _ in range(6):
        frames.append(_anchor_frame(idx))
        idx += 1

    events = detect_events(frames)
    assert not any(e.type == "goal" for e in events), f"false goal: {events}"


def test_short_detection_gap_is_interpolated_no_false_goal():
    """A short gap (1-2 frames) in detection must not look like a disappearance => no goal."""
    frames: list[FrameResult] = []
    idx = 0
    for x in range(800, 1000, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # a spike with a 2-frame gap in the middle — interpolation should fill it
    frames.append(_ball_frame(idx, 1000.0, 540.0)); idx += 1
    frames.append(_anchor_frame(idx)); idx += 1          # gap 1
    frames.append(_anchor_frame(idx)); idx += 1          # gap 2 (<= max_gap_frames)
    frames.append(_ball_frame(idx, 1300.0, 540.0)); idx += 1
    # the ball is still visible — it does not disappear
    for x in range(1320, 1500, 40):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1

    events = detect_events(frames)
    assert not any(e.type == "goal" for e in events), f"gap treated as a goal: {events}"


def test_high_dynamics_without_disappearance_emits_shot():
    """High ball dynamics without a disappearance => shot candidate."""
    frames: list[FrameResult] = []
    idx = 0
    for x in range(400, 600, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # spike in the center, the ball does NOT disappear
    for x in range(600, 1100, 130):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    for x in range(1100, 1200, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1

    events = detect_events(frames)
    assert any(e.type == "shot" for e in events), f"no shot: {events}"
    assert not any(e.type == "goal" for e in events)


def test_low_confidence_ball_is_ignored():
    """Ball detections below the confidence threshold do not build the track."""
    frames = [_ball_frame(i, 100.0 + i * 200, 540.0, conf=0.1) for i in range(6)]
    events = detect_events(frames, EventConfig(min_ball_confidence=0.3))
    assert events == []
