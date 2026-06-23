FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build context to korzeń repo — worker/app i vision są rodzeństwem pod /app.
COPY worker/app ./app
COPY vision ./vision

ENV PYTHONPATH=/app
# Worker zdejmuje joby z listy Redis (BRPOP) i woła vision pipeline. Bez serwera HTTP.
CMD ["python", "-m", "app.worker"]
