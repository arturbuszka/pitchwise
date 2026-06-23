"""Video analysis worker — pops jobs off a Redis list (BRPOP) and calls the vision pipeline.

Replaces arq (app/tasks.py). Contract with the producer (.NET API):
  - Redis list: VISION_QUEUE (default "vision_jobs")
  - element: JSON {"job_id": <int>}

Run with:  python -m app.worker

The worker connects to Redis and pops jobs itself — the API (.NET or Python) only
pushes job_id via LPUSH. All ML logic stays in vision_runner.run_vision_job.
"""
import asyncio
import json
import logging
import os

import redis.asyncio as redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.config import get_settings
from app.highlight_runner import run_highlight_job
from app.vision_runner import run_vision_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

settings = get_settings()
QUEUE = os.getenv("VISION_QUEUE", "vision_jobs")
HIGHLIGHT_QUEUE = os.getenv("HIGHLIGHT_QUEUE", "highlight_jobs")


async def _handle(raw: str) -> None:
    try:
        payload = json.loads(raw)
        job_id = int(payload["job_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        log.warning("Skipped invalid queue item: %r", raw)
        return
    log.info("Starting job %s", job_id)
    try:
        await run_vision_job(job_id)
        log.info("Job %s finished", job_id)
    except Exception:  # noqa: BLE001 — a single job must not bring the worker down
        log.exception("Job %s failed", job_id)


async def _handle_highlight(raw: str) -> None:
    try:
        payload = json.loads(raw)
        highlight_id = int(payload["highlight_id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        log.warning("Skipped invalid highlight queue item: %r", raw)
        return
    log.info("Starting highlight %s", highlight_id)
    try:
        await run_highlight_job(highlight_id)
        log.info("Highlight %s finished", highlight_id)
    except Exception:  # noqa: BLE001
        log.exception("Highlight %s failed", highlight_id)


# BRPOP blocks on the Redis server side for BRPOP_TIMEOUT seconds. The client's socket
# read timeout must be LONGER, otherwise redis-py raises TimeoutError instead of
# returning None. We add a margin (+5s) and catch TimeoutError as "no job" anyway.
BRPOP_TIMEOUT = 5


async def _consume(client, queue: str, handler) -> None:
    """Generic BRPOP loop: pops items off `queue` and passes them to `handler`."""
    log.info("Worker listening on Redis list %r (%s)", queue, settings.redis_url)
    while True:
        try:
            # BRPOP blocks until an item appears; returns (key, value).
            item = await client.brpop(queue, timeout=BRPOP_TIMEOUT)
        except RedisTimeoutError:
            # Empty queue for the whole timeout — normal, keep waiting.
            continue
        if item is None:
            continue
        _, raw = item
        await handler(raw)


async def main() -> None:
    client = redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=BRPOP_TIMEOUT + 5,
    )
    try:
        # Vision and highlight jobs are independent queues consumed concurrently.
        await asyncio.gather(
            _consume(client, QUEUE, _handle),
            _consume(client, HIGHLIGHT_QUEUE, _handle_highlight),
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
