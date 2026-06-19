"""Endpointy meczów: upload, lista, szczegóły, uruchomienie analizy, eventy, klipy."""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import get_or_create_pending_analysis
from app.config import get_settings
from app.db import get_session
from app.models import Analysis, Clip, Event, EventSource, Match
from app.queue import enqueue_analysis
from app.schemas import (
    AnalysisOut,
    ClipOut,
    EventCreate,
    EventOut,
    MatchOut,
)

router = APIRouter(prefix="/api/matches", tags=["matches"])
settings = get_settings()

_ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".avi"}


@router.post("", response_model=MatchOut)
async def upload_match(
    title: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, f"Nieobsługiwany format: {ext}. Dozwolone: {sorted(_ALLOWED_EXT)}")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = settings.uploads_dir / stored_name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    match = Match(title=title, filename=stored_name)
    session.add(match)
    await session.commit()
    await session.refresh(match)
    return match


@router.get("", response_model=list[MatchOut])
async def list_matches(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Match).order_by(Match.created_at.desc()))).scalars().all()
    return rows


@router.get("/{match_id}", response_model=MatchOut)
async def get_match(match_id: int, session: AsyncSession = Depends(get_session)):
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    return match


@router.get("/{match_id}/video")
async def get_match_video(match_id: int, session: AsyncSession = Depends(get_session)):
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    path = settings.uploads_dir / match.filename
    if not path.exists():
        raise HTTPException(404, "Video file missing")
    return FileResponse(path)


@router.post("/{match_id}/analyze", response_model=AnalysisOut)
async def start_analysis(match_id: int, session: AsyncSession = Depends(get_session)):
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    analysis = await get_or_create_pending_analysis(session, match_id)
    await enqueue_analysis(analysis.id)
    return analysis


@router.get("/{match_id}/analysis", response_model=AnalysisOut | None)
async def latest_analysis(match_id: int, session: AsyncSession = Depends(get_session)):
    row = (
        await session.execute(
            select(Analysis).where(Analysis.match_id == match_id).order_by(Analysis.created_at.desc())
        )
    ).scalars().first()
    return row


@router.get("/{match_id}/events", response_model=list[EventOut])
async def list_events(match_id: int, session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Event).where(Event.match_id == match_id).order_by(Event.timestamp_seconds)
        )
    ).scalars().all()
    return rows


@router.post("/{match_id}/events", response_model=EventOut)
async def create_event(
    match_id: int,
    payload: EventCreate,
    session: AsyncSession = Depends(get_session),
):
    """Ręczny tag trenera. Opcjonalnie wycina klip od razu."""
    match = await session.get(Match, match_id)
    if not match:
        raise HTTPException(404, "Match not found")

    event = Event(
        match_id=match_id,
        type=payload.type,
        source=EventSource.manual,
        timestamp_seconds=payload.timestamp_seconds,
        label=payload.label,
    )
    session.add(event)
    await session.flush()

    # wytnij klip dla ręcznego tagu (jeśli ffmpeg dostępny)
    from vision.clips import extract_clip

    start = max(0.0, payload.timestamp_seconds - settings.clip_pre_seconds)
    end = payload.timestamp_seconds + settings.clip_post_seconds
    clip_name = f"match{match_id}_event{event.id}.mp4"
    video_path = str(settings.uploads_dir / match.filename)
    if extract_clip(video_path, settings.clips_dir / clip_name, start, end):
        session.add(
            Clip(event_id=event.id, match_id=match_id, filename=clip_name, start_seconds=start, end_seconds=end)
        )

    await session.commit()
    await session.refresh(event)
    return event


@router.delete("/{match_id}/events/{event_id}")
async def delete_event(match_id: int, event_id: int, session: AsyncSession = Depends(get_session)):
    event = await session.get(Event, event_id)
    if not event or event.match_id != match_id:
        raise HTTPException(404, "Event not found")
    # usuń powiązane klipy
    clips = (await session.execute(select(Clip).where(Clip.event_id == event_id))).scalars().all()
    for clip in clips:
        (settings.clips_dir / clip.filename).unlink(missing_ok=True)
        await session.delete(clip)
    await session.delete(event)
    await session.commit()
    return {"ok": True}


@router.get("/{match_id}/clips", response_model=list[ClipOut])
async def list_clips(match_id: int, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Clip).where(Clip.match_id == match_id))).scalars().all()
    return rows


@router.get("/{match_id}/clips/{clip_id}/file")
async def get_clip_file(match_id: int, clip_id: int, session: AsyncSession = Depends(get_session)):
    clip = await session.get(Clip, clip_id)
    if not clip or clip.match_id != match_id:
        raise HTTPException(404, "Clip not found")
    path = settings.clips_dir / clip.filename
    if not path.exists():
        raise HTTPException(404, "Clip file missing")
    return FileResponse(path)
