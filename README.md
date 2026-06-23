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
- **Highlight reels** — select events and stitch them into a single reel (ffmpeg, rendered
  in the background via a Redis queue)
- **Share links** — public, time-limited link to a highlight; the page streams (never
  downloads) and expired links return `410`
- **HLS delivery (CDN-style)** — reels are segmented to HLS and served by an nginx edge
  with signed, expiring URLs and edge caching; the API stays off the byte path
  (see [Highlight delivery](#highlight-delivery-hls-cdn-style))

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

### Highlight delivery (HLS, CDN-style)

A coach selects events → the worker stitches a highlight reel (ffmpeg) and segments it
into HLS (`.m3u8` + `.ts`). Delivery follows the production model used by every large
streaming service: **the application server never serves video bytes.** An nginx edge
(standing in for a CDN) validates a signed, expiring URL and caches the segments; the
API only mints the URL and steps aside.

```
                        ┌──────────────────────────────────────────────┐
  Viewer (hls.js)       │  bytes: edge → viewer (cached), API off path  │
        │               └──────────────────────────────────────────────┘
        │ 1. GET signed HLS url
        ▼
  .NET API (:8000) ── mints signed url (HMAC-style secure_link, expiry) ──┐
        │  (JSON only, NO bytes)                                          │
        │                                                                 ▼
        │ 2. GET /hls/{id}/index.m3u8?md5=…&expires=…   ┌──────────────────────────┐
        └──────────────────────────────────────────────►  nginx edge (:8080)      │
                                                        │  • secure_link validates │
                                                        │    signature + expiry    │
                                                        │    (403 / 410, no API)   │
                                                        │  • proxy_cache: 1st=MISS │
                                                        │    rest=HIT (X-Cache hdr)│
                                                        └────────────┬─────────────┘
                                                        reads ./storage/hls (origin)
                                                                     ▼
                                                        worker writes segments here
```

- **Signed URLs** — the API computes an nginx `secure_link` signature
  (`md5(expires + /hls/{id}/ + secret)`); nginx validates it on every `.ts` **without
  contacting the API**. Bad signature → `403`, expired → `410`. One token authorizes the
  whole `/hls/{id}/` directory, so the player fetches segments autonomously.
- **Edge cache** — `proxy_cache` makes the first viewer a `MISS` (warms the edge) and
  every later viewer a `HIT` (`X-Cache-Status` header). The fan-out to many viewers of a
  shared link is absorbed at the edge; the API sees one request per viewer (the URL mint),
  never the bytes. A load script lives in [`loadtest/`](loadtest/hls_fanout.sh).
- **Player** — [`HlsPlayer`](web/components/HlsPlayer.tsx) uses hls.js (Chrome/Firefox),
  native HLS (Safari/iOS), and falls back to the plain MP4 `/stream` endpoint otherwise.
- **Next step (designed, not built)** — a rolling `EVENT` manifest appended as each event
  clip finishes, so viewers watch a highlight while it is still being assembled
  (near-real-time, the WSC-style "highlights in seconds" path).

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| API | ASP.NET Core 9, EF Core 9 (Npgsql), StackExchange.Redis |
| Worker | Python 3.12, SQLModel / SQLAlchemy async, asyncpg, redis |
| Vision | ultralytics YOLO11, supervision (ByteTrack), OpenCV, ffmpeg |
| LLM | OpenAI-compatible adapter (OpenAI, Anthropic, Ollama) |
| Queue | Redis (plain list, LPUSH/BRPOP) |
| Database | PostgreSQL |
| Video delivery | HLS (ffmpeg segmentation) + nginx edge (`secure_link`, `proxy_cache`), hls.js player |

---

## Running with Docker (recommended)

**Prerequisites:** Docker and Docker Compose.

```bash
# 1. Copy the example env file and fill in your LLM credentials
cp .env.example .env
#    LLM_PROVIDER=openai
#    LLM_API_KEY=sk-...
#    LLM_MODEL=gpt-4o-mini

# 2. Start all services (postgres, redis, api, worker, nginx edge, web)
docker compose up -d
```

- Web app: http://localhost:3000
- API: http://localhost:8000
- HLS edge (nginx, serves video segments): http://localhost:8080

Uploaded videos and generated clips/HLS segments are persisted under the local
`./storage/` volume (`uploads/`, `clips/`, `hls/`).

> **AI chat needs LLM credentials passed to the `api` service.** The root `.env` is used
> by Compose for `${VAR}` interpolation only — it is **not** auto-injected into containers.
> The `api` service does not list `LLM_*` by default, so the chat assistant stays
> unconfigured (everything else — analysis, highlights, HLS — works without it). To enable
> chat, add to the `api.environment` block in `docker-compose.yml`:
> ```yaml
>       LLM_PROVIDER: "${LLM_PROVIDER}"
>       LLM_BASE_URL: "${LLM_BASE_URL}"
>       LLM_API_KEY: "${LLM_API_KEY}"
>       LLM_MODEL:   "${LLM_MODEL}"
> ```
> (keeps the key out of the committed yml; Compose pulls it from your gitignored `.env`.)

> **web → api connectivity (the `/api` proxy).** The browser calls the API via relative
> `/api/*` paths (same-origin, so no CORS), which Next's `rewrites()` proxy forwards to
> the API. Inside Compose the API is reachable as `http://api:8000` (service name), not
> `localhost`. Because `output: "standalone"` **bakes `rewrites()` at build time**, the
> destination is set via the `API_INTERNAL_URL` **build arg** (Compose passes
> `http://api:8000`; it defaults to `http://localhost:8000` for host dev). The same var is
> also a runtime env for server-side rendering. If you change it, rebuild the web image
> (`docker compose up -d --build web`) — a runtime-only change won't move the baked proxy.

> **HLS signing secret.** The `api` and `nginx` services share `HLS_SIGNING_SECRET`
> (default `devsecret`). For anything beyond local dev, set a strong value in `.env` —
> both services read `${HLS_SIGNING_SECRET}`, so the signatures stay in sync.

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

In `npm run dev`, `rewrites()` is evaluated at runtime, so the `/api` proxy and SSR use
`API_INTERNAL_URL` (default `http://localhost:8000`) with no extra setup — the API on the
host is reached directly. (Under Compose this is set to `http://api:8000`; see the
web → api note above.)

### 5. HLS edge (optional, for highlight streaming)

The signed-URL HLS path needs the nginx edge. Running on the host, point it at the same
`./storage/hls` and use the same secret the API signs with (`HLS_SIGNING_SECRET`):

```bash
docker run --rm -p 8080:80 \
  -e HLS_SIGNING_SECRET=devsecret -e NGINX_ENVSUBST_FILTER=HLS_SIGNING_SECRET \
  -v "$PWD/storage/hls:/srv/hls:ro" \
  -v "$PWD/nginx/nginx.conf.template:/etc/nginx/templates/default.conf.template:ro" \
  nginx:1.27
```

Without it, the player falls back to the MP4 `/stream` endpoint, so highlights still play.
ffmpeg in the worker container handles HLS segmentation; a very old host ffmpeg may lack
`-hls_playlist_type` (segmentation then no-ops and `hls_ready` stays false — MP4 fallback
covers it).

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
| `STORAGE_DIR` | Root directory for uploads, clips, and HLS segments | `/app/storage` |
| `WEB_ORIGIN` | Allowed CORS origin | `http://localhost:3000` |
| `API_INTERNAL_URL` | Where the web `/api` proxy + SSR reach the API (build arg **and** runtime env; Compose sets `http://api:8000`) | `http://localhost:8000` |
| `HLS_SIGNING_SECRET` | Shared secret for nginx `secure_link` signatures (set on **both** `api` and `nginx`) | `devsecret` |
| `HLS_BASE_URL` | Browser-facing base URL of the nginx HLS edge | `http://localhost:8080` |
| `HLS_LINK_TTL_SECONDS` | Lifetime of a signed HLS URL | `3600` |

---

## Project structure

```
pitchwise/
├── api-dotnet/             # ASP.NET Core REST API (schema owner, queue producer)
│   ├── Controllers/        # analyses, videos, events, chat (SSE), highlights, share
│   ├── Models/             # EF Core entities + enums (mirror worker/app/models.py)
│   ├── Data/               # AppDbContext, enum ↔ string mappings
│   ├── Migrations/         # dev SQL for columns EnsureCreated won't add to an existing DB
│   └── Services/           # VisionQueue + HighlightQueue (Redis), HlsSigner, LlmClient
├── worker/                 # Python worker (Redis consumer)
│   └── app/
│       ├── worker.py       # BRPOP loops → run_vision_job / run_highlight_job
│       ├── vision_runner.py   # orchestrates the vision pipeline + DB persistence
│       ├── highlight_runner.py# stitches a reel, segments it to HLS
│       └── models.py       # SQLModel schema (read/write; .NET owns DDL)
├── vision/                 # Computer vision pipeline (pure domain code)
│   ├── pipeline.py         # orchestration: detect → track → events
│   ├── detector.py         # YOLO11 + ByteTrack wrapper
│   ├── events.py           # shot / goal heuristics
│   └── clips.py            # ffmpeg: probe, clip extract, concat, HLS segmentation
├── nginx/                  # CDN-style HLS edge (secure_link + proxy_cache)
├── web/                    # Next.js frontend (App Router)
├── loadtest/               # HLS fan-out load script (prove the edge absorbs traffic)
├── tests/                  # pytest tests for the event heuristics
├── docker-compose.yml      # full stack (incl. nginx HLS edge)
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
