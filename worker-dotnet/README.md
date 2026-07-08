# PitchWise Worker (.NET) — vision port

Port of the Python `worker/` + `vision/` batch pipeline to .NET. Replaces
`ultralytics` (YOLO11) + `supervision` (ByteTrack) + `sqlalchemy` with
ONNX Runtime + [ByteTrack.NET](https://github.com/arturbuszka/ByteTrack.NET) +
EF Core, reusing the API's shared `AppDbContext`.

## Projects

| Project | What |
|---------|------|
| `PitchWise.Vision` | Vision core: `Yolo11OnnxDetector`, `Detector` (detect+track), `Events`, `Pipeline`, `FfmpegTools`, `Overlay`, `Homography`, `StatsTracker`. Port of `vision/` + `live/` helpers. |
| `PitchWise.Worker` | `BackgroundService` consuming `vision_jobs` + `highlight_jobs` from Redis → EF Core. Port of `worker/app/`. |
| `PitchWise.Live` | ASP.NET Core live server (port 8001): WS `/ws/live/external/{id}` + HLS serving. Port of `worker/live/` (external session only). |
| `PitchWise.Vision.ParityTest` | Detection parity vs ultralytics golden. |
| `PitchWise.Vision.Smoke` | Full-pipeline E2E smoke on a video. |
| `vision-onnx/` | `export_and_golden.py` + exported `.onnx` + golden JSON + `.names.json` sidecar. |
| `Dockerfile` | Multi-stage image running BOTH worker + live (ffmpeg + yt-dlp, no Python). |

## Model setup

The detector runs an **ultralytics-exported YOLO11 ONNX** (output `[1, 4+C, N]`,
transposed, no objectness). Export + golden reference:

```bash
worker/.venv/Scripts/python.exe worker-dotnet/vision-onnx/export_and_golden.py \
    --model worker/yolo11n.pt --video mundial.mp4 --imgsz 640 --frames 0,25,50
```

This writes `<model>.onnx` + `golden_<model>.json`. Also create a class-names
sidecar `<model>.names.json` (`{"names": {"0": "person", ...}}` or flat) next to
the `.onnx` — the worker loads it via `ModelClassNames`.

**Production**: fetch/train `football.pt` (classes player/ball/referee/goalkeeper),
run the same export → the .NET code is unchanged (decoder reads class count from the
output shape). Only the `.onnx`, `.names.json` and golden change.

## Verify

**Detection parity** (proves C# pre/post-processing matches ultralytics):
```bash
cd worker-dotnet
dotnet run --project PitchWise.Vision.ParityTest -c Release -- \
    --onnx vision-onnx/yolo11n.onnx --golden vision-onnx/golden_yolo11n.json \
    --video ../mundial.mp4
# => PARITY OK 18/18
```

**Pipeline smoke** (detect → track → events on a clip):
```bash
dotnet run --project PitchWise.Vision.Smoke -c Release -- \
    --onnx vision-onnx/yolo11n.onnx --golden vision-onnx/golden_yolo11n.json \
    --video <short-clip.mp4> --stride 5
# yolo11n (COCO) finds players but barely the ball → 0 events is EXPECTED;
# football.pt is needed for goal/shot events.
```

**Batch worker end-to-end** (needs Postgres + Redis, shared with the API):
```bash
# env (same names as the Python worker / .NET API)
export DATABASE_CONNECTION="Host=localhost;Port=5432;Database=pitchwise;Username=pitchwise;Password=pitchwise"
export REDIS_URL="redis://localhost:6379"
export YOLO_MODEL_PATH="$(pwd)/vision-onnx/yolo11n.onnx"   # + yolo11n.names.json alongside
export STORAGE_DIR=../storage

dotnet run --project PitchWise.Worker -c Release
# then enqueue a job (the API normally does this):
#   redis-cli LPUSH vision_jobs '{"job_id": <id>}'
# expect: VisionJob pending→running→done, Event/Clip rows written,
#         AnalysisSession flips to done when all its jobs finish.
```

## Live server

```bash
cd worker-dotnet
export YOLO_MODEL_PATH="$(pwd)/vision-onnx/yolo11n.onnx"   # + .names.json alongside
export FFMPEG_PATH=/path/to/modern/ffmpeg   # needs -hls_flags support (ffmpeg >= 4)
export LIVE_PIPELINE_MODE=passthrough        # or "detect" for YOLO overlay
dotnet run --project PitchWise.Live -c Release   # listens on :8001
```
The frontend connects via the `ws_url` the API mints (`/ws/live/external/{id}`), sends
`{type:"start", source_url}`, and plays the HLS from `/live_hls/{id}/index.m3u8`.
`source_url` may be a YouTube/Twitch page (resolved via `yt-dlp`), a direct m3u8/rtmp,
or a local file path.

## Docker (no Python)

```bash
docker build -f worker-dotnet/Dockerfile -t pitchwise-worker .   # context = repo root
# or via compose (the `worker` service now uses worker-dotnet/Dockerfile):
docker compose up worker
```
Runs both the batch worker and the live server in one container. Bakes `yolo11n.onnx`;
drop `football.onnx` + `football.names.json` into the image / mount and set
`YOLO_MODEL_PATH` for production ball detection.

## Status

- ✅ Detection parity 18/18 vs ultralytics.
- ✅ Full pipeline E2E (detect+track+events) verified on real footage.
- ✅ Worker builds + boots (Redis resilient via `AbortOnConnectFail=false`).
- ✅ Live server E2E: passthrough (HLS segments) + detect (YOLO overlay + stats) both work.
- ✅ Dockerfile validated: linux publish bundles `libOpenCvSharpExtern.so` + ONNX libs.
- ✅ `annotated` dead code removed from the API.
- ⏳ Batch DB round-trip + full `docker build`/`run` need a running Postgres/Redis/Docker.
- ⏳ Remove Python `worker/` + `vision/` after a real Docker E2E confirms the image.
