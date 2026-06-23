"""Testy heurystyki detekcji eventów (vision/events.py).

detect_events jest czystą funkcją (bez CV/DB), więc testujemy ją na sztucznych
torach piłki budowanych z FrameResult. Kadr zakładamy 1920x1080 — strefa
przykrawędziowa (edge_zone_frac=0.15) to x≤288 lub x≥1632.
"""
import sys
from pathlib import Path

# Pozwól uruchomić testy bez instalacji pakietu (repo nie jest instalowalne).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vision.events import EventConfig, detect_events  # noqa: E402
from vision.types import CLASS_BALL, Detection, FrameResult  # noqa: E402

FPS = 25.0
STRIDE = 1  # w testach każdy FrameResult to kolejna analizowana próbka


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
    """Klatka tła z detekcjami w narożnikach — ustala rozmiar kadru (~1920x1080)
    niezależnie od tego, gdzie aktualnie jest piłka."""
    corner = Detection(cls="player", xyxy=(1900.0, 1060.0, 1920.0, 1080.0), confidence=0.9)
    return FrameResult(frame_index=idx, timestamp_seconds=idx / FPS, detections=[corner])


def test_goal_trajectory_toward_edge_emits_high_confidence_goal():
    """Piłka przyspiesza ku prawej krawędzi, dochodzi do strefy i znika => goal."""
    frames: list[FrameResult] = []
    idx = 0
    # spokojny ruch (niskie prędkości budują medianę)
    for x in range(800, 1000, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # gwałtowny sprint ku prawej krawędzi (duże skoki x)
    for x in range(1000, 1750, 120):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # piłka znika po wejściu w strefę przykrawędziową
    for _ in range(6):
        frames.append(_anchor_frame(idx))
        idx += 1

    events = detect_events(frames)
    goals = [e for e in events if e.type == "goal"]
    assert len(goals) == 1, f"oczekiwano 1 gola, dostano {events}"
    assert goals[0].confidence >= 0.6


def test_ball_vanishes_in_center_is_not_a_goal():
    """Zanik piłki w CENTRUM kadru = błąd detekcji, nie gol. Kluczowa regresja."""
    frames: list[FrameResult] = []
    idx = 0
    for x in range(800, 1000, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # spike, ale piłka zostaje w centrum (x ~ 960, daleko od krawędzi)
    for x in range(1000, 1100, 120):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    for _ in range(6):
        frames.append(_anchor_frame(idx))
        idx += 1

    events = detect_events(frames)
    assert not any(e.type == "goal" for e in events), f"fałszywy gol: {events}"


def test_short_detection_gap_is_interpolated_no_false_goal():
    """Krótka luka (1-2 klatki) w detekcji nie może wyglądać jak zanik => brak gola."""
    frames: list[FrameResult] = []
    idx = 0
    for x in range(800, 1000, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # spike z 2-klatkową luką w środku — interpolacja powinna ją wypełnić
    frames.append(_ball_frame(idx, 1000.0, 540.0)); idx += 1
    frames.append(_anchor_frame(idx)); idx += 1          # luka 1
    frames.append(_anchor_frame(idx)); idx += 1          # luka 2 (≤ max_gap_frames)
    frames.append(_ball_frame(idx, 1300.0, 540.0)); idx += 1
    # piłka dalej widoczna — nie znika
    for x in range(1320, 1500, 40):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1

    events = detect_events(frames)
    assert not any(e.type == "goal" for e in events), f"luka uznana za gola: {events}"


def test_high_dynamics_without_disappearance_emits_shot():
    """Duża dynamika piłki bez zaniku => kandydat na strzał (shot)."""
    frames: list[FrameResult] = []
    idx = 0
    for x in range(400, 600, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    # spike w centrum, piłka NIE znika
    for x in range(600, 1100, 130):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1
    for x in range(1100, 1200, 20):
        frames.append(_ball_frame(idx, float(x), 540.0))
        idx += 1

    events = detect_events(frames)
    assert any(e.type == "shot" for e in events), f"brak strzału: {events}"
    assert not any(e.type == "goal" for e in events)


def test_low_confidence_ball_is_ignored():
    """Detekcje piłki poniżej progu confidence nie budują toru."""
    frames = [_ball_frame(i, 100.0 + i * 200, 540.0, conf=0.1) for i in range(6)]
    events = detect_events(frames, EventConfig(min_ball_confidence=0.3))
    assert events == []
