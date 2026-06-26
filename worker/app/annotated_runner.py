"""Annotated video render runner.

Pops a video_id from the annotated_jobs Redis queue, runs YOLO detection on
every frame, draws bounding-box overlays, encodes to H.264 MP4 via ffmpeg pipe,
then segments to HLS for CDN delivery.

Lifecycle mirrors highlight_runner: status pending -> running -> done/failed.
"""
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_maker
from app.models import AnnotatedJob, AnnotatedJobStatus, Video

settings = get_settings()


async def run_annotated_job(job_id: int) -> None:
    """Renders annotated HLS for the video referenced by job_id."""
    from vision.annotated import generate_annotated_video
    try:
        from live.overlay import OverlayFlags
    except ModuleNotFoundError:
        from worker.live.overlay import OverlayFlags  # type: ignore

    async with async_session_maker() as session:
        job = await session.get(AnnotatedJob, job_id)
        if job is None:
            return

        video = await session.get(Video, job.video_id)
        if video is None:
            job.status = AnnotatedJobStatus.failed
            job.error = "Video not found"
            await session.commit()
            return

        job.status = AnnotatedJobStatus.running
        job.progress = 0.0
        await session.commit()

        video_path = settings.uploads_dir / video.filename
        out_mp4 = settings.clips_dir / f"annotated_{video.id}.mp4"
        out_hls_dir = settings.hls_dir / f"annotated_{video.id}"

        async def _save_progress(p: float) -> None:
            job.progress = round(p, 3)
            await session.commit()

        # Progress callback must be sync for generate_annotated_video;
        # we update DB synchronously inside the thread executor call below.
        _last_progress: list[float] = [0.0]

        def _progress(p: float) -> None:
            _last_progress[0] = p

        try:
            import asyncio

            ok = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: generate_annotated_video(
                    video_path,
                    out_mp4,
                    out_hls_dir,
                    yolo_model_path=settings.yolo_model_path or None,
                    on_progress=_progress,
                ),
            )

            if not ok:
                raise RuntimeError("generate_annotated_video returned False")

            video.annotated_hls_ready = True
            job.status = AnnotatedJobStatus.done
            job.progress = 1.0
            job.finished_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            job = await session.get(AnnotatedJob, job_id)
            if job:
                job.status = AnnotatedJobStatus.failed
                job.error = f"{type(exc).__name__}: {exc}"
                job.finished_at = datetime.now(timezone.utc)
                await session.commit()
