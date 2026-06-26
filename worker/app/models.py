"""DB models (SQLModel).

Schema:
  AnalysisSession (an analysis session with multiple videos)
    ├─1:N──► Video        (video files uploaded to the session)
    │            └─1:1──► VisionJob  (YOLO processing status)
    └─1:N──► Event        (a detected event or a manual tag)
                 └─1:1──► Clip       (the extracted highlight)
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


def _str_enum(enum_cls) -> Column:
    """An enum column as a plain VARCHAR/text (native_enum=False) holding string values
    (e.g. "goal"). Must match .NET, which creates these columns as text — otherwise
    asyncpg tries to cast to a non-existent Postgres ENUM type."""
    return Column(
        SAEnum(enum_cls, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )


def _tz_dt(nullable: bool = False) -> Column:
    """A datetime column as TIMESTAMP WITH TIME ZONE (timestamptz). .NET (EF Core)
    creates created_at/updated_at/finished_at as timestamptz; without this asyncpg gets
    an offset-aware datetime into an offset-naive column and raises DataError."""
    return Column(DateTime(timezone=True), nullable=nullable)


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


class HighlightStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class EventType(str, Enum):
    goal = "goal"
    shot = "shot"
    wayward_pass = "wayward_pass"   # wayward pass / turnover
    foul = "foul"                   # foul / card
    free_kick = "free_kick"         # free kick
    offside = "offside"             # offside
    substitution = "substitution"   # substitution
    set_piece = "set_piece"         # set piece
    manual = "manual"               # manual coach tag


class EventSource(str, Enum):
    auto = "auto"
    manual = "manual"


# ---------------------------------------------------------------------------
# Event type display config (no table — returned by the API)
# ---------------------------------------------------------------------------

EVENT_TYPE_CONFIG: dict[str, dict] = {
    "goal":         {"label": "Goal",          "icon": "⚽", "color": "#16a34a", "bg": "#e6f5ec"},
    "shot":         {"label": "Shot",          "icon": "🎯", "color": "#2f5fe0", "bg": "#e8edff"},
    "wayward_pass": {"label": "Turnover",      "icon": "↗",  "color": "#e0732f", "bg": "#fff0e6"},
    "foul":         {"label": "Foul",          "icon": "🟨", "color": "#ef4444", "bg": "#fee2e2"},
    "free_kick":    {"label": "Free kick",     "icon": "⛳", "color": "#2f5fe0", "bg": "#e8edff"},
    "offside":      {"label": "Offside",       "icon": "🚩", "color": "#8b5cf6", "bg": "#f3e8ff"},
    "substitution": {"label": "Substitution",  "icon": "🔄", "color": "#06b6d4", "bg": "#e0f7fa"},
    "set_piece":    {"label": "Set piece",     "icon": "📐", "color": "#64748b", "bg": "#f1f5f9"},
    "manual":       {"label": "Manual",        "icon": "✏️",  "color": "#6b7280", "bg": "#f9fafb"},
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AnalysisSession(SQLModel, table=True):
    """The main analysis session entity."""
    __tablename__ = "analysissession"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str                                       # "Eagles vs Falcons"
    subtitle: Optional[str] = None                  # "District league · round 14"
    sport: str = "football"                         # "football" | "basketball" | "handball"
    status: SessionStatus = Field(default=SessionStatus.draft, sa_column=_str_enum(SessionStatus))
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())
    updated_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())


class Video(SQLModel, table=True):
    """A single video file within an analysis session."""
    __tablename__ = "video"

    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="analysissession.id", index=True)
    name: str                                       # "1st half", "2nd half"
    filename: str                                   # file name in uploads_dir
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    order: int = 0                                  # order in the list
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())


class VisionJob(SQLModel, table=True):
    """YOLO pipeline processing status for a single video."""
    __tablename__ = "visionjob"

    id: Optional[int] = Field(default=None, primary_key=True)
    video_id: int = Field(foreign_key="video.id", index=True)
    status: VisionJobStatus = Field(default=VisionJobStatus.pending, sa_column=_str_enum(VisionJobStatus))
    progress: float = 0.0                           # 0..1
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())
    finished_at: Optional[datetime] = Field(default=None, sa_column=_tz_dt(nullable=True))


class Event(SQLModel, table=True):
    """An event detected automatically or added manually."""
    __tablename__ = "event"

    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="analysissession.id", index=True)
    video_id: Optional[int] = Field(default=None, foreign_key="video.id", index=True)
    type: EventType = Field(sa_column=_str_enum(EventType))
    source: EventSource = Field(sa_column=_str_enum(EventSource))
    timestamp_seconds: float
    confidence: Optional[float] = None
    label: Optional[str] = None
    note: Optional[str] = None                      # "Shot from inside the box"
    player_number: Optional[int] = None             # #9
    player_name: Optional[str] = None               # "Smith"
    assist_number: Optional[int] = None             # #10
    assist_name: Optional[str] = None               # "Jones"
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())


class Clip(SQLModel, table=True):
    """A video fragment cut around an event."""
    __tablename__ = "clip"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    video_id: int = Field(foreign_key="video.id", index=True)
    filename: str                                   # file name in clips_dir
    start_seconds: float
    end_seconds: float
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())


class LiveSession(SQLModel, table=True):
    """A live analysis session consuming an external HLS/RTMP stream."""
    __tablename__ = "livesession"

    id: str = Field(primary_key=True)               # UUID4 string
    source_url: str
    status: str = "idle"                             # idle | running | stopped
    ws_url: str = ""
    hls_url: str = ""
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())
    stopped_at: Optional[datetime] = Field(default=None, sa_column=_tz_dt(nullable=True))


class Highlight(SQLModel, table=True):
    """A highlight reel stitched from clips around a set of selected events.

    .NET owns this schema (EnsureCreated); the worker only reads/writes rows.
    event_ids is a CSV of Event ids (e.g. "12,15,18"). share_token/share_expires_at
    back the public, time-limited share link.
    """
    __tablename__ = "highlight"

    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_id: int = Field(foreign_key="analysissession.id", index=True)
    name: str
    event_ids: str = ""                             # CSV of Event ids
    status: HighlightStatus = Field(default=HighlightStatus.pending, sa_column=_str_enum(HighlightStatus))
    progress: float = 0.0                           # 0..1
    filename: Optional[str] = None                  # stitched file in clips_dir
    hls_ready: bool = False                          # HLS segments produced (hls_dir/{id}/)
    error: Optional[str] = None
    share_token: Optional[str] = Field(default=None, index=True)
    share_expires_at: Optional[datetime] = Field(default=None, sa_column=_tz_dt(nullable=True))
    created_at: datetime = Field(default_factory=_now, sa_column=_tz_dt())
    finished_at: Optional[datetime] = Field(default=None, sa_column=_tz_dt(nullable=True))
