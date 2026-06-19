# Sport Highlights & Analysis (MVP: piłka nożna)

Narzędzie dla sztabów trenerskich i analityków do:
1. **Auto-highlightów** z nagrań meczów (auto-detekcja gola/strzału + ręczne tagowanie),
2. **Analizy rozgrywki** z czatem LLM (faza druga).

## Architektura

```
web (Next.js / TS)  ──HTTP/SSE──►  api (FastAPI / Python)
                                      │  ├─ kolejka analiz (arq + Redis)
                                      │  ├─ vision pipeline (YOLO + supervision)
                                      │  └─ adapter LLM (Claude API ↔ Ollama)
```

- **Backend + Vision = Python** (jeden język, bez mostu między nimi).
- **UI = TypeScript/Next.js** (`assistant-ui` do czatu, natywny `<video>` + canvas overlay).
- **LLM przełączalny** (env `LLM_PROVIDER`): Claude API na start, Ollama później.

## Wymagania

- Python 3.11+ (testowane na 3.13)
- Node 18+ (testowane na 22)
- **ffmpeg** w PATH — wymagany do wycinania klipów. (Aktualnie brak — zainstaluj: https://www.gyan.dev/ffmpeg/builds/ lub `winget install ffmpeg`.)
- Redis — do kolejki zadań (przez Docker Compose lub lokalnie). MVP może działać bez kolejki w trybie synchronicznym (`ANALYSIS_INLINE=1`).

## Uruchomienie (dev)

### Backend
```bash
cd api
python -m venv .venv && source .venv/Scripts/activate   # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # uzupełnij ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Worker kolejki (opcjonalny — bez niego ustaw `ANALYSIS_INLINE=1`):
```bash
cd api && arq app.tasks.WorkerSettings
```

### Frontend
```bash
cd web
npm install
cp .env.local.example .env.local
npm run dev      # http://localhost:3000
```

### Docker (całość)
```bash
docker compose up --build
```

## Struktura

- `api/` — FastAPI: REST API, modele DB, kolejka, adapter LLM.
- `vision/` — pipeline CV (detekcja, tracking, eventy, klipy). Importowany przez `api`.
- `web/` — Next.js UI.

## Status

MVP w budowie. Patrz plan: `~/.claude/plans/dostalem-oferte-na-linkedin-resilient-coral.md`.

### Uwagi (z planu)
- Detekcja eventów to największe ryzyko jakościowe → ręczne tagowanie jest fallbackiem.
- Modele vision (Roboflow) zwykle wymagają dotrenowania na realnym materiale (kąt/jakość kamery klubowej ≠ broadcast).
- Analiza pełnego meczu na CPU jest wolna → na MVP krótkie klipy / sampling klatek; docelowo GPU.
