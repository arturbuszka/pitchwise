"""FilePreviewSession: live HLS streaming from a local video file with YOLO overlays.

Reads the file frame-by-frame, runs detection, draws overlays, pipes raw BGR frames
into ffmpeg which encodes H.264 and writes HLS segments to a temp directory served
by the live FastAPI server.

Control messages (WS text, frontend → backend):
  { "type": "start", "file_path": "/abs/path/to/video.mp4" }
  { "type": "toggle", "layer": "boxes"|"labels"|"traces", "on": bool }
  { "type": "seek", "timestamp_seconds": float }
  { "type": "stop" }

Status messages (WS text, backend → frontend):
  { "type": "ready", "hls_url": str, "duration_seconds": float }
  { "type": "position", "current_seconds": float, "duration_seconds": float }
  { "type": "seeking" }
  { "type": "stats", "fps": float, "infer_ms": float, "counts": {...} }
  { "type": "done" }
  { "type": "error", "message": str }
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import time
from pathlib import Path

from live.overlay import OverlayFlags, draw_overlay
from live.session import StatsTracker, get_shared_detector
from live.config import settings, HLS_BASE_DIR

logger = logging.getLogger(__name__)

HLS_SEGMENT_SECONDS = 2
HLS_LIST_SIZE = 10


class FilePreviewSession:
    def __init__(self, session_id: str, ws):
        self.session_id = session_id
        self.ws = ws
        self.flags = OverlayFlags()
        self._stop = asyncio.Event()
        self._started = asyncio.Event()
        self._file_path: str | None = None
        self._seek_pending: float | None = None
        self._stats = StatsTracker()
        self._out_dir = HLS_BASE_DIR / session_id
        self._out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        ctrl_task = asyncio.create_task(self._control_loop())
        try:
            await asyncio.wait_for(self._started.wait(), timeout=60)
            await self._stream_loop(start_seconds=0.0)
        except asyncio.TimeoutError:
            await self._send_error("No start message received within 60s")
        except Exception as exc:
            logger.exception("FilePreviewSession %s error", self.session_id)
            await self._send_error(str(exc))
        finally:
            ctrl_task.cancel()
            try:
                await ctrl_task
            except (asyncio.CancelledError, Exception):
                pass

    def cleanup(self) -> None:
        shutil.rmtree(self._out_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Control loop
    # ------------------------------------------------------------------

    async def _control_loop(self) -> None:
        try:
            async for message in self.ws.iter_text():
                try:
                    msg = json.loads(message)
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "start":
                    self._file_path = msg.get("file_path", "")
                    self._started.set()

                elif msg_type == "toggle":
                    layer = msg.get("layer")
                    on = bool(msg.get("on", True))
                    if layer == "boxes":
                        self.flags.boxes = on
                    elif layer == "labels":
                        self.flags.labels = on
                    elif layer == "traces":
                        self.flags.traces = on

                elif msg_type == "seek":
                    ts = float(msg.get("timestamp_seconds", 0.0))
                    self._seek_pending = ts

                elif msg_type == "stop":
                    self._stop.set()
                    break

        except Exception:
            self._stop.set()

    # ------------------------------------------------------------------
    # Main streaming loop — restarts on seek
    # ------------------------------------------------------------------

    async def _stream_loop(self, start_seconds: float) -> None:
        import cv2

        file_path = self._file_path
        if not file_path or not Path(file_path).exists():
            await self._send_error(f"File not found: {file_path}")
            return

        # Validate path stays inside uploads dir (security)
        uploads_dir = str(settings.uploads_dir) if hasattr(settings, "uploads_dir") else "/app/storage/uploads"
        if not str(Path(file_path).resolve()).startswith(uploads_dir):
            await self._send_error("Access denied")
            return

        while not self._stop.is_set():
            self._seek_pending = None

            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                await self._send_error(f"Cannot open file: {file_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = total_frames / fps if total_frames > 0 else 0.0

            cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)

            # Clean the HLS dir for fresh segments on each (re)start
            for f in self._out_dir.glob("*"):
                f.unlink(missing_ok=True)

            ffmpeg_proc = self._start_ffmpeg(w, h, fps)
            if ffmpeg_proc is None:
                cap.release()
                await self._send_error("ffmpeg not available")
                return

            await self.ws.send_text(json.dumps({
                "type": "ready",
                "duration_seconds": round(duration, 1),
            }))

            loop = asyncio.get_running_loop()
            detector = get_shared_detector()
            frame_idx = 0
            frame_delay = 1.0 / fps
            stats_deadline = time.monotonic()
            position_deadline = time.monotonic()

            try:
                while not self._stop.is_set():
                    # Check for pending seek — restart the outer loop
                    if self._seek_pending is not None:
                        start_seconds = self._seek_pending
                        await self.ws.send_text(json.dumps({"type": "seeking"}))
                        break

                    ok, frame = await loop.run_in_executor(None, cap.read)
                    if not ok:
                        # EOF
                        await self._flush_ffmpeg(ffmpeg_proc)
                        await self.ws.send_text(json.dumps({"type": "done"}))
                        self._stop.set()
                        break

                    # Resize if needed
                    if settings.max_width > 0 and w > settings.max_width:
                        scale = settings.max_width / w
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        frame = await loop.run_in_executor(
                            None, lambda f=frame: __import__("cv2").resize(f, (new_w, new_h))
                        )

                    t0 = time.monotonic()
                    if self.flags.any_overlay():
                        current_ts = start_seconds + frame_idx / fps
                        fr = await loop.run_in_executor(
                            None, detector.detect_frame, frame, frame_idx, current_ts
                        )
                        infer_ms = (time.monotonic() - t0) * 1000
                        await loop.run_in_executor(None, draw_overlay, frame, fr, self.flags)

                        counts: dict[str, int] = {}
                        for d in fr.detections:
                            counts[d.cls] = counts.get(d.cls, 0) + 1
                        self._stats.record(infer_ms, counts)
                    else:
                        infer_ms = 0.0

                    # Write frame to ffmpeg pipe
                    try:
                        await loop.run_in_executor(None, ffmpeg_proc.stdin.write, frame.tobytes())
                    except BrokenPipeError:
                        break

                    frame_idx += 1
                    now = time.monotonic()

                    # Position update every 1s
                    if now - position_deadline >= 1.0:
                        position_deadline = now
                        current_sec = start_seconds + frame_idx / fps
                        try:
                            await self.ws.send_text(json.dumps({
                                "type": "position",
                                "current_seconds": round(current_sec, 1),
                                "duration_seconds": round(duration, 1),
                            }))
                        except Exception:
                            pass

                    # Stats every 3s
                    if now - stats_deadline >= 3.0:
                        stats_deadline = now
                        try:
                            await self.ws.send_text(json.dumps({
                                "type": "stats",
                                "fps": round(self._stats.fps(), 1),
                                "infer_ms": round(infer_ms, 1),
                                "counts": self._stats._last_counts,
                            }))
                        except Exception:
                            pass

                    # Pace to real video speed
                    await asyncio.sleep(frame_delay)

            finally:
                cap.release()
                await loop.run_in_executor(None, self._kill_ffmpeg, ffmpeg_proc)

            # If stop was set (not a seek), exit
            if self._stop.is_set() or self._seek_pending is None:
                break

    # ------------------------------------------------------------------
    # FFmpeg helpers
    # ------------------------------------------------------------------

    def _start_ffmpeg(self, w: int, h: int, fps: float) -> subprocess.Popen | None:
        playlist = str(self._out_dir / "index.m3u8")
        seg_pattern = str(self._out_dir / "seg_%05d.ts")
        cmd = [
            settings.ffmpeg_path, "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "pipe:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",
            "-f", "hls",
            "-hls_time", str(HLS_SEGMENT_SECONDS),
            "-hls_list_size", str(HLS_LIST_SIZE),
            "-hls_flags", "delete_segments+append_list+independent_segments",
            "-hls_segment_filename", seg_pattern,
            playlist,
        ]
        try:
            return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            return None

    async def _flush_ffmpeg(self, proc: subprocess.Popen) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, proc.stdin.close)
            await loop.run_in_executor(None, proc.wait)
        except Exception:
            pass

    def _kill_ffmpeg(self, proc: subprocess.Popen) -> None:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _send_error(self, message: str) -> None:
        try:
            await self.ws.send_text(json.dumps({"type": "error", "message": message}))
        except Exception:
            pass
