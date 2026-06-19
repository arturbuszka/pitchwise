"""Wysyłanie zadania analizy: do arq (Redis) albo inline w tle (dev)."""
import asyncio

from app.config import get_settings

settings = get_settings()


async def enqueue_analysis(analysis_id: int) -> None:
    if settings.analysis_inline:
        # tryb dev: odpalamy w tle bieżącego procesu, bez Redis/workera
        from app.analysis import run_analysis

        asyncio.create_task(run_analysis(analysis_id))
        return

    from arq import create_pool
    from arq.connections import RedisSettings

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await pool.enqueue_job("analyze_match_task", analysis_id)
    await pool.close()
