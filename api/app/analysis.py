"""Serwis analizy: uruchamia vision pipeline i zapisuje wyniki (Analysis, Event,
Clip) do DB. Wołany albo inline (dev), albo przez worker kolejki (arq)."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_maker
from app.models import (
    Analysis,
    AnalysisStatus,
    Clip,
    Event,
    EventSource,
    EventType,
    Match,
)

settings = get_settings()


async def _set_progress(session: AsyncSession, analysis_id: int, progress: float) -> None:
    analysis = await session.get(Analysis, analysis_id)
    if analysis:
        analysis.progress = progress
        await session.commit()


async def run_analysis(analysis_id: int) -> None:
    """Wykonuje analizę meczu w tle. Aktualizuje status/progress w DB."""
    # Import vision dopiero tutaj (ciężkie zależności CV) — API startuje bez nich.
    from vision.clips import extract_clip
    from vision.pipeline import analyze_video

    async with async_session_maker() as session:
        analysis = await session.get(Analysis, analysis_id)
        if analysis is None:
            return
        match = await session.get(Match, analysis.match_id)
        if match is None:
            analysis.status = AnalysisStatus.failed
            analysis.error = "Match not found"
            await session.commit()
            return

        analysis.status = AnalysisStatus.running
        await session.commit()

        video_path = str(settings.uploads_dir / match.filename)

        try:
            # on_progress jest synchroniczny (woła go pipeline w pętli) — odkładamy
            # zapis postępu do prostego pola; pełny zapis robimy etapami niżej.
            progress_holder = {"p": 0.0}

            def on_progress(p: float) -> None:
                progress_holder["p"] = p

            result = analyze_video(
                video_path,
                yolo_model_path=settings.yolo_model_path or None,
                frame_stride=settings.frame_stride,
                on_progress=on_progress,
            )

            # zapis metadanych meczu
            match.duration_seconds = result.duration_seconds
            match.fps = result.fps

            # zapis eventów + wycięcie klipów
            for det in result.events:
                event = Event(
                    match_id=match.id,
                    type=EventType(det.type),
                    source=EventSource.auto,
                    timestamp_seconds=det.timestamp_seconds,
                    confidence=det.confidence,
                    label=det.label,
                )
                session.add(event)
                await session.flush()  # by uzyskać event.id

                start = max(0.0, det.timestamp_seconds - settings.clip_pre_seconds)
                end = det.timestamp_seconds + settings.clip_post_seconds
                clip_name = f"match{match.id}_event{event.id}.mp4"
                clip_path = settings.clips_dir / clip_name
                if extract_clip(video_path, clip_path, start, end):
                    session.add(
                        Clip(
                            event_id=event.id,
                            match_id=match.id,
                            filename=clip_name,
                            start_seconds=start,
                            end_seconds=end,
                        )
                    )

            analysis.status = AnalysisStatus.done
            analysis.progress = 1.0
            analysis.finished_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:  # noqa: BLE001 — chcemy zapisać dowolny błąd analizy
            await session.rollback()
            analysis = await session.get(Analysis, analysis_id)
            if analysis:
                analysis.status = AnalysisStatus.failed
                analysis.error = f"{type(exc).__name__}: {exc}"
                analysis.finished_at = datetime.now(timezone.utc)
                await session.commit()


async def get_or_create_pending_analysis(session: AsyncSession, match_id: int) -> Analysis:
    """Zwraca istniejącą trwającą analizę lub tworzy nową pending."""
    existing = (
        await session.execute(
            select(Analysis)
            .where(Analysis.match_id == match_id)
            .where(Analysis.status.in_([AnalysisStatus.pending, AnalysisStatus.running]))
        )
    ).scalars().first()
    if existing:
        return existing

    analysis = Analysis(match_id=match_id, status=AnalysisStatus.pending)
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)
    return analysis
