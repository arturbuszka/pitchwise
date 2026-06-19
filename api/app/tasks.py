"""Kolejka zadań (arq + Redis) dla długiej analizy wideo.

Uruchomienie workera:  arq app.tasks.WorkerSettings

Gdy ANALYSIS_INLINE=1 — analiza leci synchronicznie w request (patrz routers),
a worker/Redis nie są potrzebne (wygodne do dev/MVP na jednej maszynie).
"""
from arq.connections import RedisSettings

from app.analysis import run_analysis
from app.config import get_settings

settings = get_settings()


async def analyze_match_task(ctx, analysis_id: int) -> None:
    await run_analysis(analysis_id)


class WorkerSettings:
    functions = [analyze_match_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
