FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build context is the repo root — worker/app, worker/live and vision are siblings under /app.
COPY worker/app ./app
COPY worker/live ./live
COPY vision ./vision
# Football model weights. `worker/models/*.pt` is git-ignored, so on a clean checkout the
# directory only carries README/fetch_model and the worker falls back to yolo11n.pt. To
# bake the real model into the image, fetch it into worker/models/football.pt before
# building (see worker/models/README.md) — or use Git LFS.
COPY worker/models ./models

ENV PYTHONPATH=/app

# Start both the Redis queue worker and the live WebSocket/HLS server.
CMD ["sh", "-c", "python -m app.worker & uvicorn live.server:app --host 0.0.0.0 --port 8001 & wait"]
