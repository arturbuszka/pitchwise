"""FastAPI live server — WebSocket endpoints for live HLS preview sessions.

Runs on port 8001 alongside the main Redis worker.
HLS segments are served as static files from /tmp/live_hls/.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from live.config import settings, HLS_BASE_DIR
from live.file_session import FilePreviewSession
from live.external_session import ExternalPreviewSession

logger = logging.getLogger(__name__)

HLS_BASE_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load the YOLO model at server startup so the first live session
    # doesn't stall waiting for model initialisation (can take 10-15s).
    from live.session import get_shared_detector
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        await loop.run_in_executor(pool, get_shared_detector)
    logger.info("YOLO detector pre-loaded")
    yield


app = FastAPI(title="PitchWise Live Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin, settings.web_origin_alt, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/live_hls/{session_id}/{filename}")
async def live_hls(session_id: str, filename: str):
    """Serve HLS playlist/segments with correct MIME types and no caching.

    StaticFiles served the .m3u8 as `audio/x-mpegurl` with Range support (206
    responses), which hls.js mishandles for a live, growing playlist — the manifest
    parsed but no media rendered. We serve the playlist as
    `application/vnd.apple.mpegurl` and segments as `video/mp2t`, full 200 responses,
    with `no-cache` so the player always sees fresh segments.
    """
    # Guard against path traversal — only a flat <session>/<file> is allowed.
    if "/" in session_id or "/" in filename or ".." in session_id or ".." in filename:
        raise HTTPException(status_code=400, detail="invalid path")

    path = HLS_BASE_DIR / session_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="not found")

    if filename.endswith(".m3u8"):
        media_type = "application/vnd.apple.mpegurl"
    elif filename.endswith(".ts"):
        media_type = "video/mp2t"
    else:
        media_type = "application/octet-stream"

    return Response(
        content=path.read_bytes(),
        media_type=media_type,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.websocket("/ws/live/{session_id}")
async def file_live_ws(websocket: WebSocket, session_id: str):
    """Live preview session from a local uploaded file."""
    await websocket.accept()
    session = FilePreviewSession(session_id, websocket)
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("FilePreviewSession %s crashed", session_id)
    finally:
        session.cleanup()


@app.websocket("/ws/live/external/{session_id}")
async def external_live_ws(websocket: WebSocket, session_id: str):
    """Live analysis session from an external HLS/RTMP URL."""
    await websocket.accept()
    session = ExternalPreviewSession(session_id, websocket)
    try:
        await session.run()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ExternalPreviewSession %s crashed", session_id)
    finally:
        session.cleanup()
