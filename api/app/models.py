"""Modele DB (SQLModel). Schemat MVP:

Match (wgrany mecz) ──1:N──► Analysis (przebieg analizy vision)
                    └─1:N──► Event   (gol/strzał wykryty auto LUB tag ręczny)
                                  └─1:1 (opcjonalnie)──► Clip (wycięty highlight)
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class EventType(str, Enum):
    goal = "goal"
    shot = "shot"
    manual = "manual"  # ręczny tag trenera


class EventSource(str, Enum):
    auto = "auto"      # wykryty przez vision
    manual = "manual"  # dodany ręcznie w UI


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    filename: str                       # nazwa pliku w uploads_dir
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    created_at: datetime = Field(default_factory=_now)


class Analysis(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    status: AnalysisStatus = Field(default=AnalysisStatus.pending)
    progress: float = 0.0               # 0..1
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    type: EventType
    source: EventSource
    timestamp_seconds: float            # moment eventu w nagraniu
    confidence: Optional[float] = None  # tylko dla auto
    label: Optional[str] = None         # opis (np. tekst tagu trenera)
    created_at: datetime = Field(default_factory=_now)


class Clip(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    filename: str                       # nazwa pliku w clips_dir
    start_seconds: float
    end_seconds: float
    created_at: datetime = Field(default_factory=_now)
