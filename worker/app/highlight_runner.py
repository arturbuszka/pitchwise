"""Highlight render runner.

Pops a highlight_id (via worker.py's highlight loop), cuts a clip around each
selected event, then stitches them into one MP4 with ffmpeg concat. Mirrors the
VisionJob lifecycle in vision_runner: status pending -> running -> done/failed,
with per-clip progress.
"""
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_maker
from app.models import Event, Highlight, HighlightStatus, Video

settings = get_settings()


def _parse_event_ids(csv: str) -> list[int]:
    out: list[int] = []
    for part in (csv or "").split(","):
        part = part.strip()
        if part:
            try:
                out.append(int(part))
            except ValueError:
                pass
    return out


async def run_highlight_job(highlight_id: int) -> None:
    """Renders a highlight reel from its selected events. Runs in the worker thread."""
    from vision.clips import concat_clips, extract_clip

    async with async_session_maker() as session:
        highlight = await session.get(Highlight, highlight_id)
        if highlight is None:
            return

        highlight.status = HighlightStatus.running
        highlight.progress = 0.0
        await session.commit()

        try:
            event_ids = _parse_event_ids(highlight.event_ids)
            if not event_ids:
                raise ValueError("No events selected")

            # Fetch the selected events, ordered by timestamp so the reel plays in
            # match order. Preserve only events from this analysis.
            rows = (
                await session.execute(
                    select(Event)
                    .where(Event.analysis_id == highlight.analysis_id)
                    .where(Event.id.in_(event_ids))
                    .order_by(Event.timestamp_seconds)
                )
            ).scalars().all()
            if not rows:
                raise ValueError("Selected events not found")

            # Cache video file paths by id (events may span multiple source videos).
            video_paths: dict[int, str] = {}

            clip_paths: list[Path] = []
            total = len(rows)
            for i, ev in enumerate(rows):
                if ev.video_id is None:
                    continue
                if ev.video_id not in video_paths:
                    video = await session.get(Video, ev.video_id)
                    if video is None:
                        continue
                    video_paths[ev.video_id] = str(settings.uploads_dir / video.filename)

                start = max(0.0, ev.timestamp_seconds - settings.clip_pre_seconds)
                end = ev.timestamp_seconds + settings.clip_post_seconds
                clip_name = f"hl{highlight.id}_ev{ev.id}.mp4"
                clip_path = settings.clips_dir / clip_name
                if extract_clip(video_paths[ev.video_id], clip_path, start, end):
                    clip_paths.append(clip_path)

                # progress is the clipping phase (0..0.8); concat is the final 0.8..1.0
                highlight.progress = round(0.8 * (i + 1) / total, 3)
                await session.commit()

            if not clip_paths:
                raise ValueError("Could not extract any clips")

            out_name = f"highlight{highlight.id}.mp4"
            out_path = settings.clips_dir / out_name
            if not concat_clips(clip_paths, out_path):
                raise RuntimeError("ffmpeg concat failed")

            highlight.filename = out_name
            highlight.status = HighlightStatus.done
            highlight.progress = 1.0
            highlight.finished_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            highlight = await session.get(Highlight, highlight_id)
            if highlight:
                highlight.status = HighlightStatus.failed
                highlight.error = f"{type(exc).__name__}: {exc}"
                highlight.finished_at = datetime.now(timezone.utc)
                await session.commit()
