"""Czat z LLM o meczu — streaming przez SSE. Buduje zwięzły kontekst meczu z DB
(eventy/statystyki, NIE surowe klatki — koszt tokenów)."""
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm import stream_chat
from app.models import Event, Match
from app.schemas import ChatRequest

router = APIRouter(prefix="/api/chat", tags=["chat"])

_SYSTEM = (
    "Jesteś asystentem analitycznym dla sztabu trenerskiego piłki nożnej. "
    "Odpowiadasz zwięźle i konkretnie po polsku, opierając się na dostarczonym "
    "kontekście meczu (wykryte i otagowane zdarzenia). Gdy danych brakuje, mów to wprost."
)


async def _build_match_context(session: AsyncSession, match_id: int) -> str:
    match = await session.get(Match, match_id)
    if not match:
        return ""
    events = (
        await session.execute(
            select(Event).where(Event.match_id == match_id).order_by(Event.timestamp_seconds)
        )
    ).scalars().all()

    lines = [f"Mecz: {match.title} (czas: {match.duration_seconds or '?'} s)."]
    if events:
        lines.append(f"Zdarzenia ({len(events)}):")
        for e in events:
            mm, ss = divmod(int(e.timestamp_seconds), 60)
            conf = f", pewność {e.confidence:.0%}" if e.confidence is not None else ""
            lines.append(f"- {mm:02d}:{ss:02d} {e.type.value} ({e.source.value}{conf}) {e.label or ''}".rstrip())
    else:
        lines.append("Brak wykrytych/otagowanych zdarzeń.")
    return "\n".join(lines)


@router.post("")
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    system = _SYSTEM
    if req.match_id is not None:
        context = await _build_match_context(session, req.match_id)
        if context:
            system = f"{_SYSTEM}\n\nKontekst meczu:\n{context}"

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for delta in stream_chat(messages, system=system):
                yield f"data: {delta}\n\n".encode()
        except Exception as exc:  # noqa: BLE001
            yield f"data: [błąd LLM: {type(exc).__name__}]\n\n".encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
