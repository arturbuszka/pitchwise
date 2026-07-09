# PitchWise worker (.NET) — replaces the Python worker/ + vision/.
# Runs BOTH the batch queue worker (PitchWise.Worker) and the live WS/HLS server
# (PitchWise.Live) in one container, mirroring the old `python -m app.worker &
# uvicorn live.server` setup — but with zero Python.
#
# Build context MUST be the repo root: PitchWise.Worker references ../../api-dotnet.
#   docker build -f worker-dotnet/Dockerfile -t pitchwise-worker .

# ---- build ----
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copy the projects the worker/live builds depend on.
COPY worker-dotnet/ ./worker-dotnet/
COPY api-dotnet/ ./api-dotnet/

# Publish both entrypoints. -r linux-x64 makes the csproj pull the LINUX OpenCvSharp
# native lib (libOpenCvSharpExtern.so); without an explicit RID it defaults to Windows.
RUN dotnet publish worker-dotnet/PitchWise.Worker/PitchWise.Worker.csproj -c Release -r linux-x64 --no-self-contained -o /out/worker \
 && dotnet publish worker-dotnet/PitchWise.Live/PitchWise.Live.csproj    -c Release -r linux-x64 --no-self-contained -o /out/live

# ---- runtime ----
FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app

# System deps: ffmpeg (HLS encode/probe), yt-dlp (stream resolver, single binary),
# and the native libs OpenCvSharp needs at runtime (OpenGL/threading/etc.).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg yt-dlp \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /out/worker ./worker
COPY --from=build /out/live   ./live
# Football model (player/ball/referee/goalkeeper, exported from Darkmyter's
# yolov8m-640-football-players weights — see worker-dotnet/README.md) + its
# .names.json sidecar. yolo11n (COCO fallback) is also baked in for override.
COPY worker-dotnet/vision-onnx/football.onnx worker-dotnet/vision-onnx/football.names.json ./models/
COPY worker-dotnet/vision-onnx/yolo11n.onnx worker-dotnet/vision-onnx/yolo11n.names.json ./models/

ENV YOLO_MODEL_PATH=/app/models/football.onnx \
    FFMPEG_PATH=ffmpeg \
    YT_DLP_PATH=yt-dlp \
    LIVE_HLS_DIR=/tmp/live_hls \
    LIVE_PIPELINE_MODE=detect

EXPOSE 8001

# Run the native apphost (not `dotnet foo.dll`) — on Windows dev boxes, invoking the
# bare .dll via the dotnet.exe muxer can resolve the OS-bundled onnxruntime.dll in
# System32 ahead of ours (crashes with "version [14] not supported"); the apphost
# doesn't go through that resolution path. Harmless on Linux either way.
RUN chmod +x /app/worker/PitchWise.Worker /app/live/PitchWise.Live
CMD ["sh", "-c", "/app/worker/PitchWise.Worker & /app/live/PitchWise.Live & wait -n"]
