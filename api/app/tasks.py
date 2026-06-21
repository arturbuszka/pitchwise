"""Kolejka zadań (arq + Redis) dla długiej analizy wideo.

Uruchomienie workera:  arq app.tasks.WorkerSettings

Gdy ANALYSIS_INLINE=1 — analiza leci synchronicznie w request (patrz routers),
a worker/Redis nie są potrzebne (wygodne do dev/MVP na jednej maszynie).
"""
from arq.connections import RedisSettings

from app.config import get_settings
from app.vision_runner import run_vision_job

settings = get_settings()


async def run_vision_job_task(ctx, job_id: int) -> None:
    await run_vision_job(job_id)


class WorkerSettings:
    functions = [run_vision_job_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
