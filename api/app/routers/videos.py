"""Endpointy wideo: upload, streaming, uruchamianie pipeline YOLO, status VisionJob."""
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import AnalysisSession, Video, VisionJob, VisionJobStatus
from app.schemas import VideoOut, VisionJobOut

router = APIRouter(prefix="/api/analyses", tags=["videos"])
settings = get_settings()

_ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".avi"}


async def _get_video_or_404(db: AsyncSession, analysis_id: int, video_id: int) -> Video:
    video = await db.get(Video, video_id)
    if not video or video.analysis_id != analysis_id:
        raise HTTPException(404, "Wideo nie znalezione")
    return video


# ---------------------------------------------------------------------------
# Filmy w sesji
# ---------------------------------------------------------------------------

@router.get("/{analysis_id}/videos", response_model=list[VideoOut])
async def list_videos(analysis_id: int, db: AsyncSession = Depends(get_session)):
    obj = await db.get(AnalysisSession, analysis_id)
    if not obj:
        raise HTTPException(404, "Analiza nie znaleziona")
    rows = (
        await db.execute(
            select(Video)
            .where(Video.analysis_id == analysis_id)
            .order_by(Video.order, Video.created_at)
        )
    ).scalars().all()
    return [
        VideoOut(id=v.id, analysis_id=v.analysis_id, name=v.name,
                 duration_seconds=v.duration_seconds, fps=v.fps, order=v.order)
        for v in rows
    ]


@router.post("/{analysis_id}/videos", response_model=VideoOut)
async def upload_video(
    analysis_id: int,
    name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
):
    obj = await db.get(AnalysisSession, analysis_id)
    if not obj:
        raise HTTPException(404, "Analiza nie znaleziona")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, f"Nieobsługiwany format: {ext}. Dozwolone: {sorted(_ALLOWED_EXT)}")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = settings.uploads_dir / stored_name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # ustal kolejność: koniec listy
    existing_count = (
        await db.execute(select(Video).where(Video.analysis_id == analysis_id))
    ).scalars().all()
    order = len(existing_count)

    video = Video(
        analysis_id=analysis_id,
        name=name,
        filename=stored_name,
        order=order,
    )
    db.add(video)

    # zaktualizuj updated_at sesji
    obj.updated_at = datetime.now(timezone.utc)
    db.add(obj)

    await db.commit()
    await db.refresh(video)
    return VideoOut(
        id=video.id, analysis_id=video.analysis_id, name=video.name,
        duration_seconds=video.duration_seconds, fps=video.fps, order=video.order,
    )


@router.get("/{analysis_id}/videos/{video_id}/stream")
async def stream_video(
    analysis_id: int,
    video_id: int,
    db: AsyncSession = Depends(get_session),
):
    video = await _get_video_or_404(db, analysis_id, video_id)
    path = settings.uploads_dir / video.filename
    if not path.exists():
        raise HTTPException(404, "Plik wideo nie istnieje")
    return FileResponse(path)


# ---------------------------------------------------------------------------
# Uruchamianie pipeline YOLO
# ---------------------------------------------------------------------------

@router.post("/{analysis_id}/videos/{video_id}/analyze", response_model=VisionJobOut)
async def start_video_analysis(
    analysis_id: int,
    video_id: int,
    db: AsyncSession = Depends(get_session),
):
    video = await _get_video_or_404(db, analysis_id, video_id)

    # sprawdź czy nie ma już aktywnego joba
    existing = (
        await db.execute(
            select(VisionJob)
            .where(VisionJob.video_id == video_id)
            .where(VisionJob.status.in_([VisionJobStatus.pending, VisionJobStatus.running]))
        )
    ).scalars().first()
    if existing:
        return VisionJobOut(
            id=existing.id, video_id=existing.video_id, status=existing.status,
            progress=existing.progress, error=existing.error,
            created_at=existing.created_at, finished_at=existing.finished_at,
        )

    job = VisionJob(video_id=video_id)
    db.add(job)

    # oznacz sesję jako "processing"
    session_obj = await db.get(AnalysisSession, analysis_id)
    if session_obj:
        from app.models import SessionStatus
        session_obj.status = SessionStatus.processing
        session_obj.updated_at = datetime.now(timezone.utc)
        db.add(session_obj)

    await db.commit()
    await db.refresh(job)

    from app.queue import enqueue_vision_job
    await enqueue_vision_job(job.id)

    return VisionJobOut(
        id=job.id, video_id=job.video_id, status=job.status,
        progress=job.progress, error=job.error,
        created_at=job.created_at, finished_at=job.finished_at,
    )


@router.get("/{analysis_id}/videos/{video_id}/status", response_model=VisionJobOut | None)
async def get_video_analysis_status(
    analysis_id: int,
    video_id: int,
    db: AsyncSession = Depends(get_session),
):
    await _get_video_or_404(db, analysis_id, video_id)
    job = (
        await db.execute(
            select(VisionJob)
            .where(VisionJob.video_id == video_id)
            .order_by(VisionJob.created_at.desc())
        )
    ).scalars().first()
    if not job:
        return None
    return VisionJobOut(
        id=job.id, video_id=job.video_id, status=job.status,
        progress=job.progress, error=job.error,
        created_at=job.created_at, finished_at=job.finished_at,
    )


# ---------------------------------------------------------------------------
# Klipy wideo
# ---------------------------------------------------------------------------

@router.get("/{analysis_id}/clips/{clip_id}/stream")
async def stream_clip(
    analysis_id: int,
    clip_id: int,
    db: AsyncSession = Depends(get_session),
):
    from app.models import Clip
    clip = await db.get(Clip, clip_id)
    if not clip:
        raise HTTPException(404, "Klip nie znaleziony")
    # sprawdź że klip należy do tej analizy przez video
    video = await db.get(Video, clip.video_id)
    if not video or video.analysis_id != analysis_id:
        raise HTTPException(404, "Klip nie znaleziony")
    path = settings.clips_dir / clip.filename
    if not path.exists():
        raise HTTPException(404, "Plik klipu nie istnieje")
    return FileResponse(path)
