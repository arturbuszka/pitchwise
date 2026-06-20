"""Wysyłanie zadań analizy: do arq (Redis) albo inline w tle (dev)."""
import asyncio

from app.config import get_settings

settings = get_settings()


async def enqueue_analysis(analysis_id: int) -> None:
    """Stara kolejka dla Match-based pipeline (backward compat)."""
    if settings.analysis_inline:
        from app.analysis import run_analysis
        asyncio.create_task(run_analysis(analysis_id))
        return

    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("analyze_match_task", analysis_id)
    await pool.close()


async def enqueue_vision_job(job_id: int) -> None:
    """Nowa kolejka dla Video-based pipeline (VisionJob)."""
    if settings.analysis_inline:
        from app.vision_runner import run_vision_job
        asyncio.create_task(run_vision_job(job_id))
        return

    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("run_vision_job_task", job_id)
    await pool.close()
