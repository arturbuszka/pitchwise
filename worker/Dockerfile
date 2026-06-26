FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build context is the repo root — worker/app, worker/live and vision are siblings under /app.
COPY worker/app ./app
COPY worker/live ./live
COPY vision ./vision

ENV PYTHONPATH=/app

# Start both the Redis queue worker and the live WebSocket/HLS server.
CMD ["sh", "-c", "python -m app.worker & uvicorn live.server:app --host 0.0.0.0 --port 8001 & wait"]
