"""ExternalPreviewSession: live HLS analysis from an external URL (YouTube, Twitch, HLS, RTMP).

Pipeline:
  1. yt-dlp -g <url>  → extracts real stream URL (m3u8 / direct HLS)
  2. cv2.VideoCapture(stream_url)  → reads frames in a thread
  3. YOLO detect + draw overlay on each frame
  4. ffmpeg (raw BGR pipe → H.264 → HLS segments)  → served by live FastAPI server

Control messages (WS text, frontend → backend):
  { "type": "start", "source_url": "https://..." }
  { "type": "toggle", "layer": "boxes"|"labels"|"traces", "on": bool }
  { "type": "calibrate", "points": [{"pixel": [x, y], "pitch": [px, py]}, ...] }
  { "type": "stop" }

Status messages (WS text, backend → frontend):
  { "type": "ready", "hls_url": str }
  { "type": "positions", "timestamp": float, "players": [{track_id, cls, pitch_x, pitch_y}] }
  { "type": "tip", "text": str }
  { "type": "stats", "fps": float, "infer_ms": float, "counts": {...} }
  { "type": "error", "message": str }
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import queue
import shutil
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from live.overlay import OverlayFlags, draw_overlay
from live.session import StatsTracker, get_shared_detector
from live.config import settings, HLS_BASE_DIR
from live.homography import Homography, pixel_to_normalized
from live.llm_tip import get_tactical_tip

logger = logging.getLogger(__name__)

HLS_SEGMENT_SECONDS = 2
HLS_LIST_SIZE = 10
# Max encode fps — kept near the rate the pipeline can actually sustain so ffmpeg's
# video clock tracks wall-clock and segments close on time. On GPU (CUDA) YOLO11
# runs ~28 fps at imgsz 640, so 25 is a safe live target; on CPU the loop naturally
# delivers fewer fps and ffmpeg follows the real input rate.
ENCODE_FPS_CAP = 25.0
POSITION_INTERVAL = 0.5   # seconds between position broadcasts
LLM_TIP_INTERVAL = 30.0   # seconds between LLM calls
MAX_POSITION_HISTORY = 60  # snapshots (~30s at 0.5s interval)
FRAME_QUEUE_SIZE = 8


class ExternalPreviewSession:
    def __init__(self, session_id: str, ws):
        self.session_id = session_id
        self.ws = ws
        self.flags = OverlayFlags()
        self._stop = asyncio.Event()
        self._started = asyncio.Event()
        self._source_url: str | None = None
        self._homography: Homography | None = None
        self._stats = StatsTracker()
        self._out_dir = HLS_BASE_DIR / session_id
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._position_history: deque[dict] = deque(maxlen=MAX_POSITION_HISTORY)
        # Thread-safe ring buffer: decode thread writes, event loop reads.
        # deque(maxlen=N) with a lock is simpler and safer than asyncio.Queue
        # across thread boundaries.
        self._ring: deque = deque(maxlen=FRAME_QUEUE_SIZE)
        self._ring_lock = threading.Lock()
        self._frame_available = asyncio.Event()
        self._frame_size: tuple[int, int] | None = None  # (w, h)
        self._ffmpeg_log = None  # file handle for ffmpeg stderr
        # Dedicated single-thread executor for YOLO inference + overlay, so it never
        # contends with the long-lived decode thread / ffmpeg writer on the shared
        # default executor (that contention starved the loop to ~1 fps).
        self._infer_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        # Encoded-frame queue + writer thread: ffmpeg's blocking stdin.write happens
        # off the event loop entirely so a momentarily-full pipe can't stall the loop.
        self._encode_q: queue.Queue = queue.Queue(maxsize=FRAME_QUEUE_SIZE)
        self._writer_thread: threading.Thread | None = None
        self._encode_broken = threading.Event()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        ctrl_task = asyncio.create_task(self._control_loop())
        try:
            await asyncio.wait_for(self._started.wait(), timeout=60)
            await self._stream_loop()
        except asyncio.TimeoutError:
            await self._send_error("No start message received within 60s")
        except Exception as exc:
            logger.exception("ExternalPreviewSession %s error", self.session_id)
            await self._send_error(str(exc))
        finally:
            ctrl_task.cancel()
            try:
                await ctrl_task
            except (asyncio.CancelledError, Exception):
                pass

    def cleanup(self) -> None:
        self._stop.set()
        try:
            self._encode_q.put_nowait(None)
        except Exception:
            pass
        self._infer_pool.shutdown(wait=False)
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
                    self._source_url = msg.get("source_url", "")
                    logger.info(
                        "ExternalPreviewSession %s: start received, source=%s",
                        self.session_id, self._source_url,
                    )
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

                elif msg_type == "calibrate":
                    points = msg.get("points", [])
                    pixel_pts = [p["pixel"] for p in points if "pixel" in p and "pitch" in p]
                    pitch_pts = [p["pitch"] for p in points if "pixel" in p and "pitch" in p]
                    if len(pixel_pts) >= 4:
                        try:
                            self._homography = Homography.from_points(pixel_pts, pitch_pts)
                        except Exception as e:
                            logger.warning("Homography calibration failed: %s", e)

                elif msg_type == "stop":
                    self._stop.set()
                    break

            # iter_text() ended: the client closed the socket. If this happened
            # before `start`, the session never ran — make that visible instead of
            # a silent "connection closed".
            if not self._started.is_set():
                logger.warning(
                    "ExternalPreviewSession %s: control channel closed before "
                    "'start' message — client disconnected during handshake?",
                    self.session_id,
                )
            self._stop.set()
            self._started.set()  # unblock run()'s wait_for so it exits promptly
        except Exception:
            self._stop.set()
            self._started.set()

    # ------------------------------------------------------------------
    # Main streaming loop
    # ------------------------------------------------------------------

    async def _stream_loop(self) -> None:
        import cv2

        source_url = self._source_url
        if not source_url:
            await self._send_error("No source URL provided")
            return

        loop = asyncio.get_running_loop()

        # Step 1: resolve real stream URL via yt-dlp (handles YouTube, Twitch, etc.)
        stream_url = await loop.run_in_executor(None, self._resolve_url, source_url)
        if stream_url is None:
            await self._send_error(f"Could not resolve stream URL: {source_url}")
            return

        logger.info("ExternalPreviewSession %s resolved: %s → %s", self.session_id, source_url, stream_url)

        # Step 2: open with cv2 to get dimensions + fps
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            await self._send_error(f"cv2 cannot open stream: {stream_url}")
            return

        source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # We run YOLO on every frame, which on CPU sustains only ~10 fps — far below a
        # 50 fps source. ffmpeg must be told the rate at which we ACTUALLY deliver
        # frames, not the source rate: otherwise it waits for `hls_time` *source*
        # seconds of frames (e.g. 100 frames for a 2s segment at 50 fps) before
        # writing the first segment, the playlist never appears, and the 30s guard
        # trips. Cap the encode fps so a segment fills from the real throughput.
        fps = min(source_fps, ENCODE_FPS_CAP)

        # Cap width
        max_w = getattr(settings, "max_width", 1280)
        if max_w and w > max_w:
            scale = max_w / w
            w = int(w * scale)
            h = int(h * scale)

        self._frame_size = (w, h)

        # Step 3: clean HLS dir and start encode
        for f in self._out_dir.glob("*"):
            f.unlink(missing_ok=True)

        ffmpeg_encode = self._start_encode_ffmpeg(w, h, fps)
        if ffmpeg_encode is None:
            cap.release()
            await self._send_error("ffmpeg encode process failed to start")
            return

        # Step 4: run the chosen pipeline. "passthrough" pipes raw frames (always works,
        # the safe default); "detect" runs YOLO + overlay. Switch via LIVE_PIPELINE_MODE.
        mode = (settings.live_pipeline_mode or "passthrough").strip().lower()
        logger.info("ExternalPreviewSession %s pipeline mode=%s", self.session_id, mode)
        try:
            if mode == "detect":
                await self._run_detect(cap, ffmpeg_encode, loop, w, h)
            else:
                await self._run_passthrough(cap, ffmpeg_encode, loop, w, h)
        finally:
            self._stop.set()
            # Stop the writer thread (sentinel) before killing ffmpeg.
            try:
                self._encode_q.put_nowait(None)
            except queue.Full:
                pass
            await loop.run_in_executor(None, self._kill_ffmpeg, ffmpeg_encode)

    async def _send_ready_if_needed(self, hls_ready_sent: bool, playlist_path: Path) -> bool:
        """Emit the 'ready' message once the first playlist is on disk. Returns the new
        hls_ready_sent flag."""
        if hls_ready_sent:
            return True
        if playlist_path.exists() and playlist_path.stat().st_size > 0:
            hls_url = f"/live_hls/{self.session_id}/index.m3u8"
            await self.ws.send_text(json.dumps({"type": "ready", "hls_url": hls_url}))
            logger.info("ExternalPreviewSession %s ready, hls=%s", self.session_id, hls_url)
            return True
        return False

    async def _write_frame(self, ffmpeg_encode, frame, hls_ready_sent: bool) -> bool:
        """Write one BGR frame to ffmpeg's stdin. Returns True on success; on a broken
        pipe surfaces the ffmpeg error (only before 'ready') and returns False."""
        try:
            ffmpeg_encode.stdin.write(frame.tobytes())
            return True
        except (BrokenPipeError, OSError):
            if not hls_ready_sent:
                tail = self._ffmpeg_stderr_tail()
                msg = "ffmpeg encoder exited unexpectedly"
                if tail:
                    msg += f": {tail}"
                logger.error("ExternalPreviewSession %s ffmpeg failed: %s", self.session_id, tail or "(no stderr)")
                await self._send_error(msg)
            return False

    # ------------------------------------------------------------------
    # Pipeline mode: passthrough (raw frames, no analysis)
    # ------------------------------------------------------------------

    async def _run_passthrough(self, cap, ffmpeg_encode, loop, w: int, h: int) -> None:
        """Bare frame pipe, NO analysis: cv2 → ffmpeg → HLS. The lightest path and the
        safe default — confirms pixels flow before any YOLO/overlay work."""
        import cv2

        playlist_path = self._out_dir / "index.m3u8"
        hls_ready_sent = False
        frame_idx = 0
        while not self._stop.is_set():
            ok, frame = await loop.run_in_executor(None, cap.read)
            if not ok:
                logger.info("ExternalPreviewSession %s: stream ended (read failed)", self.session_id)
                break

            fh, fw = frame.shape[:2]
            if fw != w or fh != h:
                frame = cv2.resize(frame, (w, h))

            if not await self._write_frame(ffmpeg_encode, frame, hls_ready_sent):
                break

            frame_idx += 1
            if frame_idx % 50 == 0:
                logger.info("ExternalPreviewSession %s passthrough: wrote %d frames, playlist=%s",
                            self.session_id, frame_idx, playlist_path.exists())

            hls_ready_sent = await self._send_ready_if_needed(hls_ready_sent, playlist_path)

    # ------------------------------------------------------------------
    # Pipeline mode: detect (YOLO + overlay on every frame)
    # ------------------------------------------------------------------

    async def _run_detect(self, cap, ffmpeg_encode, loop, w: int, h: int) -> None:
        """Run YOLO detection + draw the enabled overlay layers on every frame, then pipe
        to ffmpeg. Reuses the shared detector, draw_overlay and StatsTracker. Inference
        runs on the dedicated single-thread pool so it never starves the event loop.

        NOTE: throughput is bounded by YOLO fps; until the frame-pacing fix lands this can
        deliver few frames per HLS segment (see the plan's frame-starvation note)."""
        import cv2

        detector = get_shared_detector()
        playlist_path = self._out_dir / "index.m3u8"
        hls_ready_sent = False
        frame_idx = 0
        while not self._stop.is_set():
            ok, frame = await loop.run_in_executor(None, cap.read)
            if not ok:
                logger.info("ExternalPreviewSession %s: stream ended (read failed)", self.session_id)
                break

            fh, fw = frame.shape[:2]
            if fw != w or fh != h:
                frame = cv2.resize(frame, (w, h))

            ts = frame_idx / max(1.0, ENCODE_FPS_CAP)
            t0 = time.monotonic()
            # Inference + overlay on the dedicated pool (CPU/GPU bound, blocking).
            fr = await loop.run_in_executor(
                self._infer_pool, detector.detect_frame, frame, frame_idx, ts
            )
            if self.flags.any_overlay():
                draw_overlay(frame, fr, self.flags)
            infer_ms = (time.monotonic() - t0) * 1000.0

            counts: dict[str, int] = {}
            for d in fr.detections:
                counts[d.cls] = counts.get(d.cls, 0) + 1
            self._stats.record(infer_ms, counts)

            if not await self._write_frame(ffmpeg_encode, frame, hls_ready_sent):
                break

            frame_idx += 1
            if frame_idx % 30 == 0:
                try:
                    await self.ws.send_text(json.dumps({
                        "type": "stats",
                        "fps": round(self._stats.fps(), 1),
                        "infer_ms": round(infer_ms, 1),
                        "counts": counts,
                    }))
                except Exception:
                    pass

            hls_ready_sent = await self._send_ready_if_needed(hls_ready_sent, playlist_path)

    async def _emit_tip(self, snapshots: list[dict]) -> None:
        tip = await get_tactical_tip(snapshots, settings)
        if tip:
            try:
                await self.ws.send_text(json.dumps({"type": "tip", "text": tip}))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # URL resolver: yt-dlp -g for YouTube/Twitch/etc, passthrough otherwise
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_url(url: str) -> str | None:
        """Use yt-dlp to extract a direct stream URL from social media pages.
        For plain HLS/RTMP URLs returns them as-is."""
        # If already a direct stream URL, skip yt-dlp
        lowered = url.lower()
        if (lowered.startswith("rtmp") or
                lowered.endswith(".m3u8") or
                lowered.endswith(".ts") or
                "manifest" in lowered):
            return url

        try:
            result = subprocess.run(
                ["yt-dlp", "-g", "--no-playlist",
                 "-f", "best[protocol=m3u8_native]/best[protocol=https]/best",
                 url],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                # yt-dlp -g may return multiple lines (video + audio); take first
                lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
                if lines:
                    logger.info("yt-dlp resolved %s → %s", url, lines[0][:80])
                    return lines[0]
            logger.warning("yt-dlp failed for %s: %s", url, result.stderr[:200])
            return None
        except FileNotFoundError:
            logger.warning("yt-dlp not found, trying URL directly: %s", url)
            return url  # fallback: try as-is
        except subprocess.TimeoutExpired:
            logger.warning("yt-dlp timed out for: %s", url)
            return None
        except Exception as e:
            logger.warning("yt-dlp error for %s: %s", url, e)
            return None

    # ------------------------------------------------------------------
    # ffmpeg writer thread: drains the encode queue → ffmpeg stdin (blocking)
    # ------------------------------------------------------------------

    def _writer_loop(self, proc: subprocess.Popen) -> None:
        """Write queued frames to ffmpeg's stdin off the event loop. A `None`
        sentinel ends the loop; a BrokenPipeError flags the encoder as dead."""
        while True:
            data = self._encode_q.get()
            if data is None:
                break
            try:
                proc.stdin.write(data)
            except (BrokenPipeError, OSError):
                self._encode_broken.set()
                break

    def _enqueue_frame(self, data: bytes) -> bool:
        """Hand a frame to the writer thread. Drops the frame (returns False) if the
        queue is full — better to drop than to block the loop and fall behind live."""
        if self._encode_broken.is_set():
            return False
        try:
            self._encode_q.put_nowait(data)
            return True
        except queue.Full:
            return False

    # ------------------------------------------------------------------
    # Frame reader: cv2.VideoCapture in thread → asyncio queue
    # ------------------------------------------------------------------

    def _pop_frame(self):
        """Pop oldest frame from ring buffer. Returns None if empty."""
        with self._ring_lock:
            if self._ring:
                return self._ring.popleft()
            return None

    def _pop_latest_frame(self):
        """Take the NEWEST frame and discard the rest. For live we always want to
        process the freshest frame so the analysed output stays in sync with the
        source rather than falling behind by working through a backlog."""
        with self._ring_lock:
            if not self._ring:
                return None
            frame = self._ring[-1]
            self._ring.clear()
            return frame

    def _read_frames(self, cap, w: int, h: int, loop) -> None:
        """Decode thread: reads frames from cv2 into the ring buffer."""
        import cv2

        def _signal():
            """Signal the event loop that a new frame is available."""
            loop.call_soon_threadsafe(self._frame_available.set)

        try:
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break

                # Resize if needed
                fh, fw = frame.shape[:2]
                if fw != w or fh != h:
                    frame = cv2.resize(frame, (w, h))

                # deque(maxlen=N) auto-drops oldest — no manual eviction needed
                with self._ring_lock:
                    self._ring.append(frame)

                _signal()
        finally:
            cap.release()
            # Signal once more so the event loop wakes up and sees decode is done
            _signal()

    # ------------------------------------------------------------------
    # FFmpeg encode: raw BGR frames → HLS segments
    # ------------------------------------------------------------------

    def _start_encode_ffmpeg(self, w: int, h: int, fps: float) -> subprocess.Popen | None:
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
            # Force a keyframe every segment-length so HLS can cut clean, independent
            # segments and the first one closes promptly.
            "-g", str(max(1, int(fps * HLS_SEGMENT_SECONDS))),
            "-force_key_frames", f"expr:gte(t,n_forced*{HLS_SEGMENT_SECONDS})",
            "-pix_fmt", "yuv420p",
            "-f", "hls",
            "-hls_time", str(HLS_SEGMENT_SECONDS),
            "-hls_list_size", str(HLS_LIST_SIZE),
            "-hls_flags", "delete_segments+append_list+independent_segments",
            "-hls_segment_filename", seg_pattern,
            playlist,
        ]
        # Send ffmpeg's stderr to a log file so we can surface the real reason on a
        # crash (e.g. an old ffmpeg that doesn't know -hls_flags). A file avoids the
        # pipe-buffer deadlock you'd get from an unread stderr=PIPE.
        try:
            self._ffmpeg_log = open(self._out_dir / "ffmpeg.log", "wb")
            return subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._ffmpeg_log,
            )
        except FileNotFoundError:
            return None

    def _ffmpeg_stderr_tail(self, lines: int = 8) -> str:
        """Last few lines of ffmpeg's stderr log, for error messages."""
        try:
            log_path = self._out_dir / "ffmpeg.log"
            text = log_path.read_text(errors="replace")
            tail = [ln for ln in text.splitlines() if ln.strip()][-lines:]
            return " | ".join(tail)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Position projection
    # ------------------------------------------------------------------

    def _project_detections(self, detections) -> list[dict]:
        players = []
        w, h = self._frame_size or (1920, 1080)
        for d in detections:
            if self._homography is not None:
                px, py = self._homography.project(d.xyxy)
            else:
                px, py = pixel_to_normalized(d.xyxy, w, h)
            players.append({
                "track_id": d.track_id,
                "cls": d.cls,
                "pitch_x": round(px, 2),
                "pitch_y": round(py, 2),
            })
        return players

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        try:
            if self._ffmpeg_log is not None:
                self._ffmpeg_log.close()
        except Exception:
            pass

    async def _send_error(self, message: str) -> None:
        try:
            await self.ws.send_text(json.dumps({"type": "error", "message": message}))
        except Exception:
            pass
