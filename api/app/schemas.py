"""Schematy request/response API (warstwa transportu, oddzielona od modeli DB)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models import AnalysisStatus, EventSource, EventType


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


class EventOut(BaseModel):
    id: int
    match_id: int
    type: EventType
    source: EventSource
    timestamp_seconds: float
    confidence: Optional[float]
    label: Optional[str]


class EventCreate(BaseModel):
    """Ręczny tag trenera z UI."""
    timestamp_seconds: float
    type: EventType = EventType.manual
    label: Optional[str] = None


class ClipOut(BaseModel):
    id: int
    event_id: int
    match_id: int
    filename: str
    start_seconds: float
    end_seconds: float


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    match_id: Optional[int] = None  # opcjonalny kontekst meczu
    messages: list[ChatMessage]
