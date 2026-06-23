# Port `/api` na .NET — uruchomienie i architektura

Warstwa API została przepisana z FastAPI (Python) na **ASP.NET Core** (`api-dotnet/`).
Pipeline wizyjny (YOLO11 + ByteTrack) **pozostaje w Pythonie** jako worker.

## Architektura

```
[Frontend web/ :3000]
      │ HTTP / SSE   (NEXT_PUBLIC_API_URL=http://localhost:8000 — bez zmian)
      ▼
[.NET API :8000]  ──LPUSH {"job_id":N}──►  [Redis: lista vision_jobs]
      │                                          │ BRPOP
      │  read/write                              ▼
      └────────────►  [PostgreSQL]  ◄──── read/write ──── [Python worker (app/worker.py)]
                                            (status, progres, eventy)
```

- **Komunikacja .NET ↔ Python** wyłącznie przez Redis (job_id) i wspólny Postgres.
  .NET nigdy nie woła kodu vision bezpośrednio.
- **Schemat DB** tworzy .NET (EF Core `EnsureCreated`). Python tylko czyta/pisze.
- **Front nie wymaga zmian** — te same ścieżki `/api/...`, port 8000, JSON `snake_case`, SSE.

## Uruchomienie (dev)

### 1. Infrastruktura (Postgres + Redis)
```bash
docker compose -f docker-compose.infra.yml up -d
```

### 2. .NET API (tworzy schemat, nasłuchuje na :8000)
```bash
cd api-dotnet
dotnet run
```
Konfiguracja przez ENV (te same nazwy co dawniej) lub `appsettings.json` (sekcja `App`):
`DATABASE_CONNECTION`, `REDIS_URL`, `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`,
`LLM_MODEL`, `WEB_ORIGIN`, `WEB_ORIGIN_ALT`, `STORAGE_DIR`, `VISION_QUEUE`.

### 3. Worker Python (vision)
```bash
cd worker
pip install -r requirements.txt
# wskazać tę samą bazę i Redis co .NET:
export DATABASE_URL="postgresql+asyncpg://pitchwise:pitchwise@localhost:5432/pitchwise"
export REDIS_URL="redis://localhost:6379"
python -m app.worker
```

### 4. Frontend (bez zmian)
```bash
cd web && npm run dev   # NEXT_PUBLIC_API_URL już wskazuje http://localhost:8000
```

## Co się zmieniło po stronie Pythona

- katalog `api/` przemianowany na `worker/` (to już nie API, lecz worker vision).
- `app/worker.py` — **nowy** entrypoint: pętla `BRPOP vision_jobs` → `run_vision_job`.
- `app/tasks.py` — **usunięty** (arq wycofane).
- `app/queue.py` — `enqueue_vision_job` używa gołej listy Redis (`LPUSH`) zamiast arq.
- `app/db.py` — `init_db` nie tworzy już tabel (schemat należy do .NET).
- `app/config.py` — `database_url` domyślnie Postgres (asyncpg).
- `app/models.py` — kolumny enum jako `text` (`native_enum=False`) i datetime jako
  `timestamptz` (`DateTime(timezone=True)`), żeby zgadzały się ze schematem tworzonym
  przez .NET. **To kontrakt** — bez tego asyncpg rzuca błędy typów (ENUM/timestamp).
- `requirements.txt` — `aiosqlite`/`arq` → `asyncpg`; `redis` zostaje.
- `vision/*`, `vision_runner.py` — **bez zmian logiki**.

## Kontrakt .NET ↔ Python (musi się zgadzać)

Schemat tworzy .NET (EF Core). Worker Python pisze do tych samych tabel, więc typy
muszą pasować:
- **Enumy** → kolumny `text` po obu stronach (`status`, `type`, `source`).
- **Daty** → `timestamp with time zone` po obu stronach (UTC).
- **Storage** → ten sam katalog `STORAGE_DIR` dla API i workera (API zapisuje uploady,
  worker je czyta). `dev.ps1` ustawia wspólny `./storage`.

## Smoke test

```bash
# health
curl http://localhost:8000/api/health
# event-types (stała konfiguracja)
curl http://localhost:8000/api/event-types
# utwórz analizę
curl -X POST http://localhost:8000/api/analyses -H "Content-Type: application/json" \
  -d '{"name":"Test","sport":"football"}'
```
Pełna lista kroków weryfikacji end-to-end w pliku planu
(`.claude/plans/potrzebuje-zamienic-api-z-peaceful-harbor.md`).
```
