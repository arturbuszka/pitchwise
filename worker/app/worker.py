"""Worker analizy wideo — zdejmuje joby z listy Redis (BRPOP) i woła vision pipeline.

Zastępuje arq (app/tasks.py). Kontrakt z producentem (.NET API):
  - lista Redis: VISION_QUEUE (domyślnie "vision_jobs")
  - element: JSON {"job_id": <int>}

Uruchomienie:  python -m app.worker

Worker sam łączy się do Redis i sam zdejmuje zadania — API (.NET lub Python) tylko
wrzuca job_id przez LPUSH. Cała logika ML pozostaje w vision_runner.run_vision_job.
"""
import asyncio
import json
import logging
import os

import redis.asyncio as redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import get_settings
from app.vision_runner import run_vision_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

settings = get_settings()
QUEUE = os.getenv("VISION_QUEUE", "vision_jobs")


async def _handle(raw: str) -> None:
    try:
        payload = json.loads(raw)
        job_id = int(payload["job_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        log.warning("Pominięto nieprawidłowy element kolejki: %r", raw)
        return
    log.info("Start joba %s", job_id)
    try:
        await run_vision_job(job_id)
        log.info("Job %s zakończony", job_id)
    except Exception:  # noqa: BLE001 — pojedynczy job nie może wywrócić workera
        log.exception("Job %s zakończony błędem", job_id)


# BRPOP blokuje po stronie serwera Redis przez BRPOP_TIMEOUT sekund. Socket read
# timeout klienta musi być DŁUŻSZY, inaczej redis-py rzuca TimeoutError zamiast
# zwrócić None. Dajemy zapas (+5 s) i tak czy siak łapiemy TimeoutError jako "brak joba".
BRPOP_TIMEOUT = 5


async def main() -> None:
    client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=BRPOP_TIMEOUT + 5,
    )
    log.info("Worker nasłuchuje na liście Redis %r (%s)", QUEUE, settings.redis_url)
    try:
        while True:
            try:
                # BRPOP blokuje do pojawienia się elementu; zwraca (klucz, wartość).
                item = await client.brpop(QUEUE, timeout=BRPOP_TIMEOUT)
            except RedisTimeoutError:
                # Pusta kolejka przez cały timeout — to normalne, czekamy dalej.
                continue
            if item is None:
                continue
            _, raw = item
            await _handle(raw)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
