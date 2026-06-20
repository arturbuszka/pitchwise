"""Endpointy sesji analitycznych: CRUD, zdarzenia, chat."""
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.llm import stream_chat
from app.models import (
    AnalysisSession, Clip, Event, EventSource, EventType,
    SessionStatus, Video,
)
from app.schemas import (
    AnalysisCreate, AnalysisDetail, AnalysisListItem,
    ChatRequest, ClipOut, EventCreate, EventOut, VideoOut,
)

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

_CHAT_SYSTEM = (
    "Jesteś asystentem analitycznym dla sztabu trenerskiego. "
    "Odpowiadasz zwięźle i konkretnie po polsku, opierając się na dostarczonym "
    "kontekście sesji analitycznej (wykryte i otagowane zdarzenia). "
    "Gdy danych brakuje, mów to wprost."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_session_or_404(db: AsyncSession, analysis_id: int) -> AnalysisSession:
    obj = await db.get(AnalysisSession, analysis_id)
    if not obj:
        raise HTTPException(404, "Analiza nie znaleziona")
    return obj


async def _event_to_out(db: AsyncSession, event: Event) -> EventOut:
    clip = None
    if event.id is not None:
        clip_row = (
            await db.execute(select(Clip).where(Clip.event_id == event.id))
        ).scalars().first()
        if clip_row:
            clip = ClipOut(
                id=clip_row.id,
                event_id=clip_row.event_id,
                video_id=clip_row.video_id,
                filename=clip_row.filename,
                start_seconds=clip_row.start_seconds,
                end_seconds=clip_row.end_seconds,
            )
    return EventOut(
        id=event.id,
        analysis_id=event.analysis_id,
        video_id=event.video_id,
        type=event.type,
        source=event.source,
        timestamp_seconds=event.timestamp_seconds,
        confidence=event.confidence,
        label=event.label,
        note=event.note,
        player_number=event.player_number,
        player_name=event.player_name,
        assist_number=event.assist_number,
        assist_name=event.assist_name,
        clip=clip,
    )


async def _build_analysis_context(db: AsyncSession, analysis_id: int) -> str:
    session_obj = await db.get(AnalysisSession, analysis_id)
    if not session_obj:
        return ""
    events = (
        await db.execute(
            select(Event)
            .where(Event.analysis_id == analysis_id)
            .order_by(Event.timestamp_seconds)
        )
    ).scalars().all()

    lines = [f"Analiza: {session_obj.name} ({session_obj.sport})."]
    if session_obj.subtitle:
        lines[0] += f" {session_obj.subtitle}"
    if events:
        lines.append(f"Zdarzenia ({len(events)}):")
        for e in events:
            mm, ss = divmod(int(e.timestamp_seconds), 60)
            conf = f", pewność {e.confidence:.0%}" if e.confidence is not None else ""
            player = ""
            if e.player_name:
                player = f" #{e.player_number} {e.player_name}" if e.player_number else f" {e.player_name}"
            assist = ""
            if e.assist_name:
                assist = f" (asysta #{e.assist_number} {e.assist_name})" if e.assist_number else f" (asysta {e.assist_name})"
            note = f" — {e.note}" if e.note else ""
            lines.append(
                f"- {mm:02d}:{ss:02d} {e.type.value} ({e.source.value}{conf}){player}{assist}{note}".rstrip()
            )
    else:
        lines.append("Brak wykrytych/otagowanych zdarzeń.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analyses CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AnalysisListItem])
async def list_analyses(
    sport: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    q = select(AnalysisSession).order_by(AnalysisSession.updated_at.desc())
    if sport:
        q = q.where(AnalysisSession.sport == sport)
    if search:
        q = q.where(AnalysisSession.name.ilike(f"%{search}%"))
    rows = (await db.execute(q)).scalars().all()

    result = []
    for row in rows:
        video_count = (
            await db.execute(
                select(func.count()).where(Video.analysis_id == row.id)
            )
        ).scalar() or 0
        result.append(
            AnalysisListItem(
                id=row.id,
                name=row.name,
                subtitle=row.subtitle,
                sport=row.sport,
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
                video_count=video_count,
            )
        )
    return result


@router.post("", response_model=AnalysisDetail)
async def create_analysis(
    payload: AnalysisCreate,
    db: AsyncSession = Depends(get_session),
):
    obj = AnalysisSession(
        name=payload.name,
        subtitle=payload.subtitle,
        sport=payload.sport,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return AnalysisDetail(
        id=obj.id,
        name=obj.name,
        subtitle=obj.subtitle,
        sport=obj.sport,
        status=obj.status,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        videos=[],
    )


@router.get("/{analysis_id}", response_model=AnalysisDetail)
async def get_analysis(analysis_id: int, db: AsyncSession = Depends(get_session)):
    obj = await _get_session_or_404(db, analysis_id)
    videos = (
        await db.execute(
            select(Video).where(Video.analysis_id == analysis_id).order_by(Video.order, Video.created_at)
        )
    ).scalars().all()
    return AnalysisDetail(
        id=obj.id,
        name=obj.name,
        subtitle=obj.subtitle,
        sport=obj.sport,
        status=obj.status,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        videos=[
            VideoOut(
                id=v.id, analysis_id=v.analysis_id, name=v.name,
                duration_seconds=v.duration_seconds, fps=v.fps, order=v.order,
            )
            for v in videos
        ],
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@router.get("/{analysis_id}/events", response_model=list[EventOut])
async def list_events(
    analysis_id: int,
    type: EventType | None = None,
    db: AsyncSession = Depends(get_session),
):
    await _get_session_or_404(db, analysis_id)
    q = (
        select(Event)
        .where(Event.analysis_id == analysis_id)
        .order_by(Event.timestamp_seconds)
    )
    if type is not None:
        q = q.where(Event.type == type)
    events = (await db.execute(q)).scalars().all()
    return [await _event_to_out(db, e) for e in events]


@router.post("/{analysis_id}/events", response_model=EventOut)
async def create_event(
    analysis_id: int,
    payload: EventCreate,
    db: AsyncSession = Depends(get_session),
):
    from datetime import timezone
    from datetime import datetime

    session_obj = await _get_session_or_404(db, analysis_id)

    if payload.video_id is not None:
        video = await db.get(Video, payload.video_id)
        if not video or video.analysis_id != analysis_id:
            raise HTTPException(400, "video_id nie należy do tej analizy")

    event = Event(
        analysis_id=analysis_id,
        video_id=payload.video_id,
        type=payload.type,
        source=EventSource.manual,
        timestamp_seconds=payload.timestamp_seconds,
        label=payload.label,
        note=payload.note,
        player_number=payload.player_number,
        player_name=payload.player_name,
        assist_number=payload.assist_number,
        assist_name=payload.assist_name,
    )
    db.add(event)

    # zaktualizuj updated_at sesji
    session_obj.updated_at = datetime.now(timezone.utc)
    db.add(session_obj)

    await db.commit()
    await db.refresh(event)
    return await _event_to_out(db, event)


@router.delete("/{analysis_id}/events/{event_id}")
async def delete_event(
    analysis_id: int,
    event_id: int,
    db: AsyncSession = Depends(get_session),
):
    from app.config import get_settings
    settings = get_settings()

    event = await db.get(Event, event_id)
    if not event or event.analysis_id != analysis_id:
        raise HTTPException(404, "Event nie znaleziony")
    clips = (await db.execute(select(Clip).where(Clip.event_id == event_id))).scalars().all()
    for clip in clips:
        (settings.clips_dir / clip.filename).unlink(missing_ok=True)
        await db.delete(clip)
    await db.delete(event)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chat (SSE streaming)
# ---------------------------------------------------------------------------

@router.post("/{analysis_id}/chat")
async def chat(
    analysis_id: int,
    req: ChatRequest,
    db: AsyncSession = Depends(get_session),
):
    await _get_session_or_404(db, analysis_id)
    context = await _build_analysis_context(db, analysis_id)
    system = _CHAT_SYSTEM
    if context:
        system = f"{_CHAT_SYSTEM}\n\nKontekst analizy:\n{context}"

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for delta in stream_chat(messages, system=system):
                yield f"data: {delta}\n\n".encode()
        except Exception as exc:  # noqa: BLE001
            yield f"data: [błąd LLM: {type(exc).__name__}]\n\n".encode()
        yield b"data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
