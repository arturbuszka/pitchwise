"""Schematy request/response API (warstwa transportu, oddzielona od modeli DB)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import (
    AnalysisStatus, EventSource, EventType,
    SessionStatus, VisionJobStatus,
)


# ---------------------------------------------------------------------------
# Nowe schematy dla /api/analyses
# ---------------------------------------------------------------------------

class AnalysisCreate(BaseModel):
    name: str
    subtitle: Optional[str] = None
    sport: str = "football"


class VideoOut(BaseModel):
    id: int
    analysis_id: int
    name: str
    duration_seconds: Optional[float]
    fps: Optional[float]
    order: int


class AnalysisListItem(BaseModel):
    """Skrócony widok analizy dla listy na stronie głównej."""
    id: int
    name: str
    subtitle: Optional[str]
    sport: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    video_count: int


class AnalysisDetail(BaseModel):
    """Pełny widok analizy z listą filmów."""
    id: int
    name: str
    subtitle: Optional[str]
    sport: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    videos: list[VideoOut]


class VisionJobOut(BaseModel):
    id: int
    video_id: int
    status: VisionJobStatus
    progress: float
    error: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]


class ClipOut(BaseModel):
    id: int
    event_id: int
    video_id: int
    filename: str
    start_seconds: float
    end_seconds: float


class EventOut(BaseModel):
    id: int
    analysis_id: int
    video_id: Optional[int]
    type: EventType
    source: EventSource
    timestamp_seconds: float
    confidence: Optional[float]
    label: Optional[str]
    note: Optional[str]
    player_number: Optional[int]
    player_name: Optional[str]
    assist_number: Optional[int]
    assist_name: Optional[str]
    clip: Optional[ClipOut] = None


class EventCreate(BaseModel):
    timestamp_seconds: float
    type: EventType = EventType.manual
    label: Optional[str] = None
    note: Optional[str] = None
    video_id: Optional[int] = None
    player_number: Optional[int] = None
    player_name: Optional[str] = None
    assist_number: Optional[int] = None
    assist_name: Optional[str] = None


class EventTypeConfigOut(BaseModel):
    key: str
    label: str
    icon: str
    color: str
    bg: str


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    analysis_id: Optional[int] = None
    messages: list[ChatMessage]


# ---------------------------------------------------------------------------
# Stare schematy (backward compat — do usunięcia po migracji frontendu)
# ---------------------------------------------------------------------------

class MatchOut(BaseModel):
    id: int
    title: str
    filename: str
    duration_seconds: Optional[float]
    fps: Optional[float]
    created_at: datetime


class AnalysisOut(BaseModel):
    id: int
    match_id: int
    status: AnalysisStatus
    progress: float
    error: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]


class OldEventOut(BaseModel):
    id: int
    match_id: int
    type: EventType
    source: EventSource
    timestamp_seconds: float
    confidence: Optional[float]
    label: Optional[str]


class OldEventCreate(BaseModel):
    timestamp_seconds: float
    type: EventType = EventType.manual
    label: Optional[str] = None


class OldClipOut(BaseModel):
    id: int
    event_id: int
    match_id: int
    filename: str
    start_seconds: float
    end_seconds: float


class OldChatRequest(BaseModel):
    match_id: Optional[int] = None
    messages: list[ChatMessage]
