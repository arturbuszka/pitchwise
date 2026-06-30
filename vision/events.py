"""Event detection heuristics (goal / shot) — based on ball trajectory analysis.

NOTE: this is the hardest and most iterative part of the pipeline. We deliberately
stick to rule-based heuristics (no pitch homography) because the footage is highly
varied (full recordings, short clips, phone, TV) — homography requires visible pitch
lines and camera continuity, which short clips do not provide. Manual tagging in the
UI is the fallback when this detection gets it wrong.

Key change over the MVP: we operate on a SMOOTHED ball trajectory rather than on raw
frame-to-frame samples. Single wrong/missing YOLO detections (the default yolo11n
loses the small, fast ball) were the main source of the "ball disappears => goal"
false positive. Therefore we:
- interpolate short detection gaps (<= max_gap_frames),
- compute speed from a moving average (smooth_window),
- drop low-confidence detections.

Rules (without pitch calibration):
- "goal": sharp acceleration + ball moving TOWARD the frame edge + the ball actually
  disappearing AFTER reaching the edge zone. Disappearance in the center of the frame
  is usually a detection error, not a goal — and that case is exactly what we reject.
- "shot": high ball dynamics without disappearance near the edge — a weaker signal, a
  candidate for a shot/high-dynamics play.

`confidence` reflects the number of satisfied factors so the UI can sort and filter
candidates. All thresholds are parameters — to be tuned on real footage.

Stage 2 (future): once the model returns a goal class (CLASS_GOAL), a "goal line
crossing" condition will become a strong signal, and this heuristic will become the
fallback when the goal is not visible in frame.
"""
from dataclasses import dataclass

from vision.types import DetectedEvent, FrameResult


@dataclass
class EventConfig:
    # --- speed "spike" detection ---
    speed_spike_factor: float = 3.0     # how many times above median speed counts as a "spike"
    min_speed_px: float = 25.0          # minimum speed (px/sample) to count
    cooldown_seconds: float = 8.0       # min gap between events of the same type

    # --- trajectory quality (noise reduction from wrong YOLO detections) ---
    # With the football-specific model the ball is detected on far more frames and more
    # confidently than with COCO yolo11n, so the track is denser and needs less gap
    # interpolation. These remain starting points — tune on real footage.
    max_gap_frames: int = 2             # interpolate ball detection gaps <= this many samples
    smooth_window: int = 3              # moving-average window for speed
    min_ball_confidence: float = 0.35   # ignore weak ball detections when building the track

    # --- frame-edge "goal" rule (goal proxy without homography) ---
    ball_lost_frames: int = 4           # samples without the ball after a spike => disappearance
    edge_zone_frac: float = 0.15        # edge zone = this fraction of frame width/height
    direction_consistency: float = 0.6  # min consistency of motion toward the edge (0..1)

    # --- hook for Stage 2 (goal detection) ---
    # require_goal_line_cross: bool = False  # when the model returns CLASS_GOAL, force line crossing


@dataclass
class _Sample:
    """A ball-track sample after gap interpolation — center position and timestamp."""
    index: int                          # index in the original frames list
    timestamp_seconds: float
    center: tuple[float, float]
    interpolated: bool = False          # True = position computed, not detected


def _ball_center(fr: FrameResult, min_conf: float) -> tuple[float, float] | None:
    b = fr.ball
    if b is None or b.confidence < min_conf:
        return None
    x1, y1, x2, y2 = b.xyxy
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _frame_size(frames: list[FrameResult]) -> tuple[float, float]:
    """Estimates the frame size from the maximum detection coordinates (FrameResult has
    no resolution metadata). Good enough to derive the edge zone."""
    max_x = max_y = 0.0
    for fr in frames:
        for d in fr.detections:
            _, _, x2, y2 = d.xyxy
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)
    # fallback when there are no detections
    return (max_x or 1920.0, max_y or 1080.0)


def _build_track(frames: list[FrameResult], cfg: EventConfig) -> list[_Sample]:
    """Builds a smoothed ball track: collects detections (above the confidence threshold)
    and linearly interpolates short gaps (<= max_gap_frames), so that a brief loss by
    YOLO does not look like "the ball disappears"."""
    raw: list[_Sample] = []
    for i, fr in enumerate(frames):
        c = _ball_center(fr, cfg.min_ball_confidence)
        if c is not None:
            raw.append(_Sample(index=i, timestamp_seconds=fr.timestamp_seconds, center=c))

    if len(raw) < 2:
        return raw

    track: list[_Sample] = [raw[0]]
    for prev, cur in zip(raw, raw[1:]):
        gap = cur.index - prev.index - 1
        if 0 < gap <= cfg.max_gap_frames:
            # linear interpolation of position in the missing frames
            for k in range(1, gap + 1):
                t = k / (gap + 1)
                cx = prev.center[0] + (cur.center[0] - prev.center[0]) * t
                cy = prev.center[1] + (cur.center[1] - prev.center[1]) * t
                idx = prev.index + k
                track.append(
                    _Sample(
                        index=idx,
                        timestamp_seconds=frames[idx].timestamp_seconds,
                        center=(cx, cy),
                        interpolated=True,
                    )
                )
        track.append(cur)
    return track


def _smoothed_speeds(track: list[_Sample], window: int) -> list[float]:
    """Speed between consecutive track samples, smoothed with a moving average —
    removes bounding-box jitter noise."""
    raw: list[float] = [0.0]
    for prev, cur in zip(track, track[1:]):
        dx = cur.center[0] - prev.center[0]
        dy = cur.center[1] - prev.center[1]
        raw.append((dx * dx + dy * dy) ** 0.5)

    if window <= 1:
        return raw
    smoothed: list[float] = []
    half = window // 2
    for i in range(len(raw)):
        lo = max(0, i - half)
        hi = min(len(raw), i + half + 1)
        smoothed.append(sum(raw[lo:hi]) / (hi - lo))
    return smoothed


def _moves_toward_edge(
    track: list[_Sample],
    pos: int,
    frame_size: tuple[float, float],
    cfg: EventConfig,
) -> tuple[bool, bool]:
    """Whether around sample `pos` the ball consistently moves toward the frame edge and
    whether it ends up in the edge zone. Returns (moves_toward_edge, in_zone)."""
    w, h = frame_size
    last = track[pos]
    lx, ly = last.center

    in_zone = (
        lx <= w * cfg.edge_zone_frac
        or lx >= w * (1 - cfg.edge_zone_frac)
        or ly <= h * cfg.edge_zone_frac
        or ly >= h * (1 - cfg.edge_zone_frac)
    )

    # direction consistency: what fraction of the last steps moved the ball closer to the
    # nearest horizontal edge (goals sit at the side edges of a typical shot).
    lookback = track[max(0, pos - cfg.smooth_window - 1) : pos + 1]
    if len(lookback) < 2:
        return (False, in_zone)
    toward_left = lx < w / 2
    closer = 0
    steps = 0
    for prev, cur in zip(lookback, lookback[1:]):
        steps += 1
        moved = cur.center[0] - prev.center[0]
        if (toward_left and moved < 0) or (not toward_left and moved > 0):
            closer += 1
    consistent = steps > 0 and (closer / steps) >= cfg.direction_consistency
    return (consistent, in_zone)


def detect_events(
    frames: list[FrameResult],
    config: EventConfig | None = None,
) -> list[DetectedEvent]:
    cfg = config or EventConfig()
    events: list[DetectedEvent] = []

    track = _build_track(frames, cfg)
    if len(track) < 2:
        return events

    frame_size = _frame_size(frames)
    speeds = _smoothed_speeds(track, cfg.smooth_window)

    sorted_speeds = sorted(s for s in speeds if s > 0)
    if not sorted_speeds:
        return events
    median = sorted_speeds[len(sorted_speeds) // 2]
    threshold = max(cfg.min_speed_px, median * cfg.speed_spike_factor)

    last_event_ts: dict[str, float] = {}

    def _emit(ev_type: str, ts: float, conf: float, label: str | None) -> None:
        last = last_event_ts.get(ev_type)
        if last is not None and ts - last < cfg.cooldown_seconds:
            return
        events.append(
            DetectedEvent(type=ev_type, timestamp_seconds=ts, confidence=round(conf, 3), label=label)
        )
        last_event_ts[ev_type] = ts

    for pos, sample in enumerate(track):
        speed = speeds[pos]
        if speed < threshold:
            continue
        ts = sample.timestamp_seconds

        # after a spike: how many samples without a DETECTED ball (interpolated ones ran
        # out, because gaps > max_gap_frames are not filled) — i.e. a real disappearance.
        last_index = sample.index
        lost = 0
        for fr in frames[last_index + 1 : last_index + 1 + cfg.ball_lost_frames + 2]:
            if _ball_center(fr, cfg.min_ball_confidence) is None:
                lost += 1
            else:
                break
        disappeared = lost >= cfg.ball_lost_frames

        toward_edge, in_zone = _moves_toward_edge(track, pos, frame_size, cfg)

        # --- "goal" scoring (multi-factor, each factor raises confidence) ---
        if disappeared and in_zone:
            score = 0.4                                  # base: spike + disappearance in zone
            if toward_edge:
                score += 0.3                             # consistent motion toward the edge
            score += min(0.2, speed / (threshold * 4))   # the stronger the spike, the more certain
            _emit(
                "goal",
                ts,
                conf=min(0.95, score),
                label="candidate: goal (acceleration + motion toward edge + ball disappearance)",
            )
        elif disappeared and not in_zone:
            # disappearance in the center of the frame is most likely a detection error,
            # not a goal. We deliberately do NOT emit "goal" — this is the main
            # false-positive regression relative to the MVP.
            continue
        else:
            # high dynamics without disappearance near the edge => shot candidate.
            _emit(
                "shot",
                ts,
                conf=min(0.5, speed / (threshold * 3)),
                label="candidate: shot (ball acceleration)",
            )

    return events
