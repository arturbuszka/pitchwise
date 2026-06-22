# PitchWise

Automated sports match analysis platform. Upload a game recording, let the computer vision pipeline detect goals and shots, get highlight clips generated automatically, and query a streaming AI chat assistant for coaching insights.

---

## Features

- **Video upload** — supports `.mp4`, `.mov`, `.mkv`, `.avi`
- **Auto-detection** — YOLO11 + ByteTrack detect players, ball, and referee; heuristics identify shots and goals
- **Highlight clips** — automatically extracted around each detected event (configurable pre/post padding)
- **Event timeline** — interactive timeline; clicking an event seeks the video player to that moment
- **AI chat** — streaming LLM assistant with full match context (works with OpenAI, Anthropic, or any OpenAI-compatible API including Ollama)
- **Manual tagging** — coaches can annotate custom events via API

---

## Architecture

```
Web (Next.js :3000) ──HTTP/SSE──▶ API (FastAPI :8000)
                                        │
                        ┌───────────────┼───────────────┐
                     SQLite           Redis           ffmpeg
                   (database)       (job queue)    (clip extraction)
                                        │
                                 Vision Pipeline
                                (YOLO11 + ByteTrack)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12, SQLModel / SQLAlchemy async |
| Vision | ultralytics YOLO11, supervision (ByteTrack), OpenCV, ffmpeg |
| LLM | OpenAI-compatible adapter (OpenAI, Anthropic, Ollama) |
| Queue | arq + Redis (production) or inline execution (dev) |
| Database | SQLite via aiosqlite |

---

## Running with Docker (recommended)

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Copy the example env file
cp .env.example .env

# 2. Fill in your LLM credentials in .env
#    LLM_PROVIDER=openai
#    LLM_API_KEY=sk-...
#    LLM_MODEL=gpt-4o-mini

# 3. Start all services
docker compose up
```

- Web app: http://localhost:3000
- API + interactive docs: http://localhost:8000/docs

Video files and the database are persisted in a local `./storage/` volume.

---

## Running locally (dev)

### Backend

```bash
cd api
python -m venv venv

# Activate venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt

# Minimum required env vars
export LLM_API_KEY=sk-...
export LLM_MODEL=gpt-4o-mini
export ANALYSIS_INLINE=1        # run analysis in-process, no Redis needed

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd web
npm install
npm run dev     # http://localhost:3000
```

The frontend expects the API at `http://localhost:8000` by default. Override with `NEXT_PUBLIC_API_URL`.

---

## Environment variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | LLM backend | `openai` |
| `LLM_BASE_URL` | OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API key | — |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `ANALYSIS_INLINE` | `1` = run analysis in-process (dev), `0` = use Redis queue (prod) | `1` |
| `FRAME_STRIDE` | Analyze every Nth frame (higher = faster, less accurate) | `5` |
| `CLIP_PRE_SECONDS` | Seconds of footage before detected event in clip | `6` |
| `CLIP_POST_SECONDS` | Seconds of footage after detected event in clip | `4` |
| `STORAGE_DIR` | Root directory for uploads and clips | `/app/storage` |
| `DATABASE_URL` | SQLAlchemy async connection string | SQLite in `STORAGE_DIR` |
| `WEB_ORIGIN` | Allowed CORS origin | `http://localhost:3000` |

---

## Project structure

```
pitchwise/
├── api/                    # FastAPI backend
│   └── app/
│       ├── routers/        # REST endpoints (matches, events, clips, chat)
│       ├── models.py       # SQLModel database schemas
│       ├── db.py           # Async DB session
│       └── llm.py          # Provider-agnostic LLM adapter
├── web/                    # Next.js frontend
│   ├── app/                # Pages (App Router)
│   └── components/         # UI components
├── vision/                 # Computer vision pipeline
│   ├── pipeline.py         # Orchestration
│   ├── detector.py         # YOLO11 + ByteTrack wrapper
│   └── events.py           # Shot / goal heuristics
├── docker-compose.yml
└── .env.example
```

---
