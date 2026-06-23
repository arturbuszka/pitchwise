"""Heurystyka detekcji eventów (gol / strzał) — analiza trajektorii piłki.

UWAGA (z planu): to NAJTRUDNIEJSZY i najbardziej iteracyjny element. Świadomie
zostajemy przy regułach (bez homografii boiska), bo materiał jest różnorodny
(pełne nagrania, krótkie ucinki, telefon, TV) — homografia wymaga widocznych
linii boiska i ciągłości kamery, czego ucinki nie dają. Ręczne tagowanie w UI
jest fallbackiem, gdy ta detekcja się myli.

Kluczowa zmiana względem MVP: pracujemy na WYGŁADZONEJ TRAJEKTORII piłki, a nie
na surowych próbkach klatka-do-klatki. Pojedyncze błędne/brakujące detekcje YOLO
(domyślny yolo11n gubi małą, szybką piłkę) były głównym źródłem false-positive
"piłka znika => gol". Dlatego:
- interpolujemy krótkie luki w detekcji (≤ max_gap_frames),
- liczymy prędkość ze średniej ruchomej (smooth_window),
- odrzucamy detekcje o niskim confidence.

Reguły (bez kalibracji boiska):
- "goal": gwałtowne przyspieszenie + ruch piłki KU KRAWĘDZI kadru + faktyczny
  zanik piłki PO osiągnięciu strefy przykrawędziowej. Zanik w centrum kadru to
  najczęściej błąd detekcji, nie gol — i właśnie ten przypadek odrzucamy.
- "shot": duża dynamika piłki bez zaniku przy krawędzi — słabszy sygnał, kandydat
  na strzał/zagranie o dużej dynamice.

`confidence` odzwierciedla liczbę spełnionych czynników, żeby UI mogło sortować
i filtrować kandydatów. Wszystkie progi są parametrami — do strojenia na realnym
materiale.

Etap 2 (przyszłość): gdy model będzie zwracał klasę bramki (CLASS_GOAL), warunek
"przecięcie linii bramkowej" wejdzie jako mocny sygnał, a ta heurystyka zostanie
fallbackiem gdy bramki nie widać w kadrze.
"""
from dataclasses import dataclass

from vision.types import DetectedEvent, FrameResult


@dataclass
class EventConfig:
    # --- detekcja "spike'u" prędkości ---
    speed_spike_factor: float = 3.0     # ile razy ponad medianę prędkości = "spike"
    min_speed_px: float = 25.0          # minimalna prędkość (px/próbkę) by liczyć
    cooldown_seconds: float = 8.0       # min. odstęp między eventami tego samego typu

    # --- jakość trajektorii (redukcja szumu z błędnych detekcji YOLO) ---
    max_gap_frames: int = 2             # interpoluj luki w detekcji piłki ≤ tylu próbek
    smooth_window: int = 3              # okno średniej ruchomej dla prędkości
    min_ball_confidence: float = 0.3    # ignoruj słabe detekcje piłki przy budowie toru

    # --- reguła "gola" przy krawędzi kadru (proxy bramki bez homografii) ---
    ball_lost_frames: int = 4           # ile próbek bez piłki po spike'u => zanik
    edge_zone_frac: float = 0.15        # strefa przykrawędziowa = ten ułamek szer./wys. kadru
    direction_consistency: float = 0.6  # min. zgodność kierunku ruchu ku krawędzi (0..1)

    # --- hak pod Etap 2 (detekcja bramki) ---
    # require_goal_line_cross: bool = False  # gdy model zwraca CLASS_GOAL, wymuś przecięcie linii


@dataclass
class _Sample:
    """Próbka toru piłki po interpolacji luk — pozycja środka i znacznik czasu."""
    index: int                          # indeks w oryginalnej liście frames
    timestamp_seconds: float
    center: tuple[float, float]
    interpolated: bool = False          # True = pozycja wyliczona, nie wykryta


def _ball_center(fr: FrameResult, min_conf: float) -> tuple[float, float] | None:
    b = fr.ball
    if b is None or b.confidence < min_conf:
        return None
    x1, y1, x2, y2 = b.xyxy
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _frame_size(frames: list[FrameResult]) -> tuple[float, float]:
    """Szacuje rozmiar kadru z maksymalnych współrzędnych detekcji (brak metadanych
    o rozdzielczości w FrameResult). Wystarcza do wyznaczenia strefy przykrawędziowej."""
    max_x = max_y = 0.0
    for fr in frames:
        for d in fr.detections:
            _, _, x2, y2 = d.xyxy
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)
    # zabezpieczenie, gdy brak detekcji
    return (max_x or 1920.0, max_y or 1080.0)


def _build_track(frames: list[FrameResult], cfg: EventConfig) -> list[_Sample]:
    """Buduje wygładzony tor piłki: zbiera wykrycia (powyżej progu confidence)
    i interpoluje liniowo krótkie luki (≤ max_gap_frames), by chwilowe zgubienie
    przez YOLO nie wyglądało jak "piłka znika"."""
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
            # interpolacja liniowa pozycji w brakujących klatkach
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
    """Prędkość między kolejnymi próbkami toru, wygładzona średnią ruchomą —
    usuwa szum drgań bounding-boxa."""
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
    """Czy w okolicy próbki `pos` piłka konsekwentnie zmierza ku krawędzi kadru i
    czy kończy w strefie przykrawędziowej. Zwraca (kieruje_się_ku_krawędzi, w_strefie)."""
    w, h = frame_size
    last = track[pos]
    lx, ly = last.center

    in_zone = (
        lx <= w * cfg.edge_zone_frac
        or lx >= w * (1 - cfg.edge_zone_frac)
        or ly <= h * cfg.edge_zone_frac
        or ly >= h * (1 - cfg.edge_zone_frac)
    )

    # zgodność kierunku: jaki ułamek z ostatnich kroków zbliżał piłkę do najbliższej
    # krawędzi poziomej (bramki są przy krawędziach bocznych kadru typowego ujęcia).
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

        # po spike'u: ile próbek bez WYKRYTEJ piłki (interpolowane się skończyły,
        # bo luki > max_gap_frames nie są uzupełniane) — czyli realny zanik.
        last_index = sample.index
        lost = 0
        for fr in frames[last_index + 1 : last_index + 1 + cfg.ball_lost_frames + 2]:
            if _ball_center(fr, cfg.min_ball_confidence) is None:
                lost += 1
            else:
                break
        disappeared = lost >= cfg.ball_lost_frames

        toward_edge, in_zone = _moves_toward_edge(track, pos, frame_size, cfg)

        # --- scoring "gola" (wieloczynnikowy, każdy czynnik podnosi confidence) ---
        if disappeared and in_zone:
            score = 0.4                                  # baza: spike + zanik w strefie
            if toward_edge:
                score += 0.3                             # konsekwentny ruch ku krawędzi
            score += min(0.2, speed / (threshold * 4))   # im mocniejszy spike, tym pewniej
            _emit(
                "goal",
                ts,
                conf=min(0.95, score),
                label="kandydat: gol (przyspieszenie + ruch ku krawędzi + zanik piłki)",
            )
        elif disappeared and not in_zone:
            # zanik w centrum kadru = najpewniej błąd detekcji, nie gol. Świadomie
            # NIE emitujemy "goal" — to główna regresja false-positive względem MVP.
            continue
        else:
            # duża dynamika bez zaniku przy krawędzi => kandydat na strzał.
            _emit(
                "shot",
                ts,
                conf=min(0.5, speed / (threshold * 3)),
                label="kandydat: strzał (przyspieszenie piłki)",
            )

    return events
