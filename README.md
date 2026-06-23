# PitchWise

Automated sports match analysis platform. Upload a game recording, let the computer
vision pipeline detect goals and shots, and query a streaming AI chat assistant for
coaching insights.

---

## Features

- **Video upload** — supports `.mp4`, `.mov`, `.mkv`, `.avi`
- **Auto-detection** — YOLO11 + ByteTrack detect players, ball, and referee; trajectory
  heuristics identify shots and goals
- **Event timeline** — interactive results panel; clicking an event seeks the video player
  to that moment
- **AI chat** — streaming LLM assistant with full match context (works with OpenAI,
  Anthropic, or any OpenAI-compatible API including Ollama)
- **Manual tagging** — coaches can annotate custom events via the API
- **Highlight clips** — optional per-event clip extraction with ffmpeg (off by default,
  enable with `GENERATE_CLIPS=1`)

---

## Architecture

The platform is split into independent services. The .NET API and the Python worker
communicate **only** through Redis (a job id) and a shared PostgreSQL database — the API
never calls the vision code directly.

```
  Web (Next.js :3000)
        │  HTTP / SSE
        ▼
  .NET API (:8000)  ──LPUSH {"job_id":N}──►  Redis list "vision_jobs"
        │                                          │ BRPOP
        │  read / write                            ▼
        └──────────────►  PostgreSQL  ◄── read / write ──  Python worker
                          (sessions,                       (vision pipeline:
                           events, jobs)                    YOLO11 + ByteTrack)
```

- **Schema ownership** — the .NET API creates the database schema (EF Core
  `EnsureCreated`). The Python worker only reads and writes; it never creates tables. The
  shared schema (enum columns as text, timestamps as `timestamptz`) is the contract
  between the two sides.
- **Frontend** — talks to the API over the same `/api/...` paths on port 8000, with
  `snake_case` JSON and SSE for chat streaming.

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| API | ASP.NET Core 9, EF Core 9 (Npgsql), StackExchange.Redis |
| Worker | Python 3.12, SQLModel / SQLAlchemy async, asyncpg, redis |
| Vision | ultralytics YOLO11, supervision (ByteTrack), OpenCV, ffmpeg |
| LLM | OpenAI-compatible adapter (OpenAI, Anthropic, Ollama) |
| Queue | Redis (plain list, LPUSH/BRPOP) |
| Database | PostgreSQL |

---

## Running with Docker (recommended)

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Copy the example env file and fill in your LLM credentials
cp .env.example .env
#    LLM_PROVIDER=openai
#    LLM_API_KEY=sk-...
#    LLM_MODEL=gpt-4o-mini

# 2. Start all services (postgres, redis, api, worker, web)
docker compose up
```

- Web app: http://localhost:3000
- API: http://localhost:8000

Uploaded videos and generated clips are persisted under the local `./storage/` volume.

---

## Running locally (dev)

On Windows you can launch everything at once with the helper script, which starts the
infrastructure and opens the API, worker, and web in separate terminals:

```powershell
.\dev.ps1
```

Otherwise, start each piece manually:

### 1. Infrastructure (Postgres + Redis)

```bash
docker compose -f docker-compose.infra.yml up -d
```

### 2. .NET API (creates the schema, listens on :8000)

```bash
cd api-dotnet
dotnet run
```

Configured via environment variables or `appsettings.json` (the `App` section):
`DATABASE_CONNECTION`, `REDIS_URL`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`,
`LLM_MODEL`, `WEB_ORIGIN`, `STORAGE_DIR`, `VISION_QUEUE`.

### 3. Python worker (vision)

```bash
cd worker
pip install -r requirements.txt

# Point it at the same database and Redis as the API
export DATABASE_URL="postgresql+asyncpg://pitchwise:pitchwise@localhost:5432/pitchwise"
export REDIS_URL="redis://localhost:6379"

python -m app.worker
```

ffmpeg must be available on `PATH` for video probing and clip extraction.

### 4. Frontend

```bash
cd web
npm install
npm run dev     # http://localhost:3000
```

The frontend calls the API at `http://localhost:8000` by default. Override with
`NEXT_PUBLIC_API_URL`.

---

## Environment variables

Copy `.env.example` to `.env` and adjust as needed. The worker has its own
`worker/.env.example`.

| Variable | Description | Default |
|---|---|---|
| `LLM_PROVIDER` | LLM backend label | `openai` |
| `LLM_BASE_URL` | OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API key (empty for Ollama) | — |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `DATABASE_CONNECTION` | Npgsql connection string (.NET API) | local Postgres |
| `DATABASE_URL` | SQLAlchemy async connection string (worker) | local Postgres (asyncpg) |
| `REDIS_URL` | Redis connection | `redis://localhost:6379` |
| `VISION_QUEUE` | Redis list name for jobs | `vision_jobs` |
| `FRAME_STRIDE` | Analyze every Nth frame (higher = faster, less accurate) | `5` |
| `CLIP_PRE_SECONDS` | Seconds of footage before a detected event in a clip | `6` |
| `CLIP_POST_SECONDS` | Seconds of footage after a detected event in a clip | `4` |
| `STORAGE_DIR` | Root directory for uploads and clips | `/app/storage` |
| `WEB_ORIGIN` | Allowed CORS origin | `http://localhost:3000` |

---

## Project structure

```
pitchwise/
├── api-dotnet/             # ASP.NET Core REST API (schema owner, queue producer)
│   ├── Controllers/        # analyses, videos, events, chat (SSE), health, event-types
│   ├── Models/             # EF Core entities + enums (mirror worker/app/models.py)
│   ├── Data/               # AppDbContext, enum ↔ string mappings
│   └── Services/           # VisionQueue (Redis), LlmClient (streaming chat)
├── worker/                 # Python worker (Redis consumer)
│   └── app/
│       ├── worker.py       # BRPOP loop → run_vision_job
│       ├── vision_runner.py# orchestrates the pipeline + DB persistence
│       └── models.py       # SQLModel schema (read/write; .NET owns DDL)
├── vision/                 # Computer vision pipeline (pure domain code)
│   ├── pipeline.py         # orchestration: detect → track → events
│   ├── detector.py         # YOLO11 + ByteTrack wrapper
│   ├── events.py           # shot / goal heuristics
│   └── clips.py            # ffmpeg probing and clip extraction
├── web/                    # Next.js frontend (App Router)
├── tests/                  # pytest tests for the event heuristics
├── docker-compose.yml      # full stack
├── docker-compose.infra.yml# Postgres + Redis only (for local dev)
└── dev.ps1                 # Windows dev launcher
```

---

## Smoke test

With the API running:

```bash
# health
curl http://localhost:8000/api/health

# event types (static config)
curl http://localhost:8000/api/event-types

# create an analysis
curl -X POST http://localhost:8000/api/analyses \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","sport":"football"}'
```

---

## Tests

```bash
pytest tests/
```

---

## License

[MIT](LICENSE)
