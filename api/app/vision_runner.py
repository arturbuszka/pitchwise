"""Runner pipeline vision dla nowego modelu VisionJob/Video/AnalysisSession."""
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_maker
from app.models import (
    AnalysisSession, Clip, Event, EventSource, EventType,
    SessionStatus, Video, VisionJob, VisionJobStatus,
)

settings = get_settings()


async def run_vision_job(job_id: int) -> None:
    """Wykonuje analizę wideo w tle. Aktualizuje VisionJob, Event, Clip, Video w DB."""
    from vision.clips import extract_clip
    from vision.pipeline import analyze_video

    async with async_session_maker() as session:
        job = await session.get(VisionJob, job_id)
        if job is None:
            return

        video = await session.get(Video, job.video_id)
        if video is None:
            job.status = VisionJobStatus.failed
            job.error = "Video not found"
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return

        job.status = VisionJobStatus.running
        await session.commit()

        video_path = str(settings.uploads_dir / video.filename)

        try:
            result = analyze_video(
                video_path,
                yolo_model_path=settings.yolo_model_path or None,
                frame_stride=settings.frame_stride,
            )

            # zapisz metadane wideo
            video.duration_seconds = result.duration_seconds
            video.fps = result.fps

            # zapisz zdarzenia + wytnij klipy
            for det in result.events:
                event = Event(
                    analysis_id=video.analysis_id,
                    video_id=video.id,
                    type=EventType(det.type),
                    source=EventSource.auto,
                    timestamp_seconds=det.timestamp_seconds,
                    confidence=det.confidence,
                    label=det.label,
                )
                session.add(event)
                await session.flush()

                start = max(0.0, det.timestamp_seconds - settings.clip_pre_seconds)
                end = det.timestamp_seconds + settings.clip_post_seconds
                clip_name = f"video{video.id}_event{event.id}.mp4"
                clip_path = settings.clips_dir / clip_name
                if extract_clip(video_path, clip_path, start, end):
                    session.add(
                        Clip(
                            event_id=event.id,
                            video_id=video.id,
                            filename=clip_name,
                            start_seconds=start,
                            end_seconds=end,
                        )
                    )

            job.status = VisionJobStatus.done
            job.progress = 1.0
            job.finished_at = datetime.now(timezone.utc)

            # zaktualizuj status sesji na "done" jeśli wszystkie joby skończone
            analysis_session = await session.get(AnalysisSession, video.analysis_id)
            if analysis_session:
                all_jobs = (
                    await session.execute(
                        select(VisionJob)
                        .join(Video, VisionJob.video_id == Video.id)
                        .where(Video.analysis_id == video.analysis_id)
                        .where(VisionJob.id != job_id)
                    )
                ).scalars().all()
                all_done = all(j.status == VisionJobStatus.done for j in all_jobs)
                if all_done:
                    analysis_session.status = SessionStatus.done
                    analysis_session.updated_at = datetime.now(timezone.utc)
                    session.add(analysis_session)

            await session.commit()

        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            job = await session.get(VisionJob, job_id)
            if job:
                job.status = VisionJobStatus.failed
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = datetime.now(timezone.utc)
                await session.commit()
