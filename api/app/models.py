"""Modele DB (SQLModel).

Schemat:
  AnalysisSession (sesja analityczna z wieloma filmami)
    ├─1:N──► Video        (pliki wideo wgrane do sesji)
    │            └─1:1──► VisionJob  (status przetwarzania YOLO)
    └─1:N──► Event        (zdarzenie wykryte lub tag ręczny)
                 └─1:1──► Clip       (wycięty highlight)
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionStatus(str, Enum):
    draft = "draft"
    processing = "processing"
    done = "done"


class VisionJobStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class EventType(str, Enum):
    goal = "goal"
    shot = "shot"
    wayward_pass = "wayward_pass"   # nieskuteczne podanie / strata
    foul = "foul"                   # faul / kartka
    free_kick = "free_kick"         # rzut wolny
    offside = "offside"             # spalony
    substitution = "substitution"   # zmiana
    set_piece = "set_piece"         # stały fragment
    manual = "manual"               # ręczny tag trenera


class EventSource(str, Enum):
    auto = "auto"
    manual = "manual"


# ---------------------------------------------------------------------------
# Konfiguracja wyświetlania typów zdarzeń (bez tabeli — zwracana przez API)
# ---------------------------------------------------------------------------

EVENT_TYPE_CONFIG: dict[str, dict] = {
    "goal":         {"label": "Bramka",         "icon": "⚽", "color": "#16a34a", "bg": "#e6f5ec"},
    "shot":         {"label": "Strzał",         "icon": "🎯", "color": "#2f5fe0", "bg": "#e8edff"},
    "wayward_pass": {"label": "Strata",         "icon": "↗",  "color": "#e0732f", "bg": "#fff0e6"},
    "foul":         {"label": "Faul",           "icon": "🟨", "color": "#ef4444", "bg": "#fee2e2"},
    "free_kick":    {"label": "Rzut wolny",     "icon": "⛳", "color": "#2f5fe0", "bg": "#e8edff"},
    "offside":      {"label": "Spalony",        "icon": "🚩", "color": "#8b5cf6", "bg": "#f3e8ff"},
    "substitution": {"label": "Zmiana",         "icon": "🔄", "color": "#06b6d4", "bg": "#e0f7fa"},
    "set_piece":    {"label": "Stały fragment", "icon": "📐", "color": "#64748b", "bg": "#f1f5f9"},
    "manual":       {"label": "Ręczny",         "icon": "✏️",  "color": "#6b7280", "bg": "#f9fafb"},
}


# ---------------------------------------------------------------------------
# Nowe modele
# ---------------------------------------------------------------------------

class AnalysisSession(SQLModel, table=True):
    """Główna encja sesji analitycznej."""
    __tablename__ = "analysissession"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str                                       # "Orły vs Sokoły"
    subtitle: Optional[str] = None                  # "Liga okręgowa · kolejka 14"
    sport: str = "football"                         # "football" | "basketball" | "handball"
    status: SessionStatus = Field(default=SessionStatus.draft)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Video(SQLModel, table=True):
    """Jeden plik wideo w ramach sesji analitycznej."""
    __tablename__ = "video"

    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="analysissession.id", index=True)
    name: str                                       # "1. połowa", "2. połowa"
    filename: str                                   # nazwa pliku w uploads_dir
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    order: int = 0                                  # kolejność w liście
    created_at: datetime = Field(default_factory=_now)


class VisionJob(SQLModel, table=True):
    """Status przetwarzania YOLO pipeline dla jednego wideo."""
    __tablename__ = "visionjob"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="video.id", index=True)
    status: VisionJobStatus = Field(default=VisionJobStatus.pending)
    progress: float = 0.0                           # 0..1
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None


class Event(SQLModel, table=True):
    """Zdarzenie wykryte automatycznie lub dodane ręcznie."""
    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="analysissession.id", index=True)
    video_id: Optional[int] = Field(default=None, foreign_key="video.id", index=True)
    type: EventType
    source: EventSource
    timestamp_seconds: float
    confidence: Optional[float] = None
    label: Optional[str] = None
    note: Optional[str] = None                      # "Strzał z pola karnego"
    player_number: Optional[int] = None             # #9
    player_name: Optional[str] = None               # "Wójcik"
    assist_number: Optional[int] = None             # #10
    assist_name: Optional[str] = None               # "Nowak"
    created_at: datetime = Field(default_factory=_now)


class Clip(SQLModel, table=True):
    """Wycięty fragment wideo wokół zdarzenia."""
    __tablename__ = "clip"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    video_id: int = Field(foreign_key="video.id", index=True)
    filename: str                                   # nazwa pliku w clips_dir
    start_seconds: float
    end_seconds: float
    created_at: datetime = Field(default_factory=_now)
