"""Heurystyka detekcji eventów (gol / strzał) — MVP.

UWAGA (z planu): to NAJTRUDNIEJSZY i najbardziej iteracyjny element. Świadomie
zaczynamy od prostej, czytelnej reguły opartej na ruchu piłki, bez homografii
boiska (która dojdzie później, by zlokalizować strefę bramki/pola karnego).
Ręczne tagowanie w UI jest fallbackiem, gdy ta detekcja się myli.

Reguła MVP (bez kalibracji boiska):
- "shot": gwałtowne przyspieszenie piłki (skok prędkości ponad próg) — kandydat
  na strzał/zagranie o dużej dynamice.
- "goal": po przyspieszeniu następuje urwanie się detekcji piłki (piłka znika z
  kadru / siatka) na dłużej niż próg — słaby, ale pierwszy sygnał na gola.

Wszystkie progi są parametrami — do strojenia na realnym materiale.
"""
from dataclasses import dataclass

from vision.types import DetectedEvent, FrameResult


@dataclass
class EventConfig:
    speed_spike_factor: float = 3.0     # ile razy ponad medianę prędkości = "spike"
    min_speed_px: float = 25.0          # minimalna prędkość (px/klatkę próbki) by liczyć
    ball_lost_frames: int = 4           # ile próbek bez piłki po spike'u => kandydat na gola
    cooldown_seconds: float = 8.0       # min. odstęp między eventami tego samego typu


def _ball_center(fr: FrameResult) -> tuple[float, float] | None:
    b = fr.ball
    if b is None:
        return None
    x1, y1, x2, y2 = b.xyxy
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def detect_events(
    frames: list[FrameResult],
    config: EventConfig | None = None,
) -> list[DetectedEvent]:
    cfg = config or EventConfig()
    events: list[DetectedEvent] = []

    # prędkości piłki między kolejnymi próbkami z dostępną pozycją
    speeds: list[tuple[int, float]] = []  # (index w frames, prędkość)
    prev_center: tuple[float, float] | None = None
    prev_i: int | None = None
    for i, fr in enumerate(frames):
        c = _ball_center(fr)
        if c is not None and prev_center is not None:
            dx = c[0] - prev_center[0]
            dy = c[1] - prev_center[1]
            speeds.append((i, (dx * dx + dy * dy) ** 0.5))
        if c is not None:
            prev_center = c
            prev_i = i
        _ = prev_i

    if not speeds:
        return events

    sorted_speeds = sorted(s for _, s in speeds)
    median = sorted_speeds[len(sorted_speeds) // 2]
    threshold = max(cfg.min_speed_px, median * cfg.speed_spike_factor)

    last_event_ts: dict[str, float] = {}

    def _emit(ev_type: str, ts: float, conf: float, label: str | None) -> None:
        last = last_event_ts.get(ev_type)
        if last is not None and ts - last < cfg.cooldown_seconds:
            return
        events.append(DetectedEvent(type=ev_type, timestamp_seconds=ts, confidence=conf, label=label))
        last_event_ts[ev_type] = ts

    for idx, speed in speeds:
        if speed < threshold:
            continue
        ts = frames[idx].timestamp_seconds

        # czy po spike'u piłka "znika" => kandydat na gola
        lost = 0
        for fr in frames[idx + 1 : idx + 1 + cfg.ball_lost_frames + 2]:
            if fr.ball is None:
                lost += 1
            else:
                break
        if lost >= cfg.ball_lost_frames:
            _emit("goal", ts, conf=min(0.6, speed / (threshold * 2)), label="kandydat: gol (piłka znika po przyspieszeniu)")
        else:
            _emit("shot", ts, conf=min(0.5, speed / (threshold * 2)), label="kandydat: strzał (przyspieszenie piłki)")

    return events
