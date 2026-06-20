"""Endpoint konfiguracji typów zdarzeń — ikony, kolory, etykiety po polsku."""
from fastapi import APIRouter

from app.models import EVENT_TYPE_CONFIG
from app.schemas import EventTypeConfigOut

router = APIRouter(prefix="/api/event-types", tags=["event-types"])


@router.get("", response_model=list[EventTypeConfigOut])
async def list_event_types(sport: str | None = None):
    """Zwraca listę konfiguracji typów zdarzeń (etykiety, ikony, kolory).
    Parametr sport jest obecnie ignorowany — wszystkie typy są współdzielone."""
    return [
        EventTypeConfigOut(key=key, **cfg)
        for key, cfg in EVENT_TYPE_CONFIG.items()
    ]
