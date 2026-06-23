FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build context is the repo root — worker/app and vision are siblings under /app.
COPY worker/app ./app
COPY vision ./vision

ENV PYTHONPATH=/app
# The worker pops jobs off the Redis list (BRPOP) and calls the vision pipeline. No HTTP server.
CMD ["python", "-m", "app.worker"]
