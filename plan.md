# Plan: Narzędzie do auto-highlightów i analizy rozgrywki (sport) — MVP: piłka nożna

## Context

Pomysł: narzędzie dla **sztabów trenerskich i analityków** do (1) automatycznego tworzenia highlightów z nagrań meczów oraz (2) panelu analizy trenerskiej z czatem LLM. Rynek polski (dużo trenerów z "zajawką") + własne zainteresowanie autora. Wcześniejszy pomysł autora, do którego wraca po ofercie z LinkedIn ("automated video highlights").

**Kluczowe ustalenie architektoniczne:** to są **sporty rzeczywiste** (nie gry komputerowe), więc nie ma API/demo/replay — jedynym źródłem danych jest **nagranie wideo**. Dlatego **computer vision (YOLO + tracking) jest tu konieczne i właściwe** (w grach komputerowych byłoby odwrotnie — tam parsuje się dane gry). To plasuje projekt w dojrzałej niszy *sports analytics* z dużą ilością open-source do wykorzystania.

**Decyzje podjęte z użytkownikiem:**
- **Sport MVP:** piłka nożna (najwięcej gotowych modeli open-source).
- **Produkt MVP:** auto-highlights najpierw; panel analizy trenerskiej w drugiej kolejności.
- **Highlights MVP:** auto-detekcja gola/strzału + ręczne tagowanie przez trenera (reszta eventów — kontry, stałe fragmenty — iteracyjnie później).
- **Stack:** Backend + Vision = **Python** (jeden język → brak mostu między nimi). UI = **TypeScript/Next.js** (najlepszy ekosystem chat-UI + video playera). Rezygnacja z C#/.NET (świadoma — eliminuje trzeci język i drugi most).
- **LLM:** openAI API (zdalne) na start, **przełączalny** przez konfigurację .

**Cel MVP:** wgrać nagranie meczu piłki nożnej → dostać przyciętą paczkę klipów (gole/strzały wykryte automatycznie + momenty otagowane ręcznie) z trackingiem graczy/piłki, oglądalną w webowym playerze, plus podstawowy czat LLM o meczu.

## Architektura

```
┌─────────────────────────────────────────────────────────┐
│  UI  —  Next.js + TypeScript (React)                      │
│  • upload meczu + lista meczów/analiz                     │
│  • video player z frame-seek + overlay tracking (canvas)  │
│  • timeline z wykrytymi/otagowanymi eventami → klipy      │
│  • chat z LLM o meczu  (assistant-ui)                     │
└───────────────────────────┬───────────────────────────────┘
                            │ HTTP/JSON + SSE (streaming czatu)
┌───────────────────────────▼───────────────────────────────┐
│  Backend / mózg  —  Python (FastAPI)                       │
│  • REST API: mecze, uploady, analizy, eventy, klipy        │
│  • kolejka zadań analizy (długie przetwarzanie wideo)      │
│  • DB (metadane meczów, eventy, tagi)                      │
│  • adapter LLM (openAI api)         │
│  • sklejanie/wycinanie klipów (ffmpeg)                     │
└───────┬───────────────────────────────────┬───────────────┘
        │ in-process / worker                │ Anthropic SDK
┌───────▼────────────────────────┐   ┌───────▼───────────────┐
│  Vision pipeline (Python)       │   │  LLM                  │
│  • YOLO: gracze / piłka / sędzia│   │  Claude API (start)   │
│  • ByteTrack (supervision): track│   │  ↕ przełącznik        │
│  • keypointy boiska → homografia │   │  Ollama (później)     │
│  • detekcja eventów (gol/strzał) │   └───────────────────────┘
│  • ekstrakcja klipów (ffmpeg)    │
└─────────────────────────────────┘
```

Backend i vision = ten sam język (Python) → vision uruchamiany jako worker w tym samym repo/procesie kolejki, **bez mostu sieciowego między nimi**. Jedyna granica językowa to UI(TS) ↔ Backend(Python) przez czyste REST/SSE.

## Stack i biblioteki (do wykorzystania, nie pisać od zera)

**Vision (Python):**
- **Roboflow `sports`** (https://github.com/roboflow/sports, **MIT**) — baza pipeline'u dla piłki: detekcja graczy/piłki/sędziów, **keypointy boiska → homografia** (mapa 2D), przypisanie drużyn (klastrowanie kolorów). UWAGA: to **kod + datasety, NIE gotowy pakiet pip** — trzeba zbudować ze źródeł i prawdopodobnie dotrenować na własnych nagraniach. **Brak trackingu/re-ID w samym repo** — dokładamy poniżej.
- **`ultralytics`** (YOLO11) — silnik detekcji. Gotowe modele piłkarskie dostępne na Roboflow Universe (`football-players-detection`) jako punkt startu zamiast trenowania od zera.
- **`supervision`** (Roboflow) — **ByteTrack** (tracking obiektów między klatkami), anotacje, narzędzia do klipów. To uzupełnia brak trackingu w `sports`.
- **`ffmpeg`** (przez `ffmpeg-python`) — wycinanie i sklejanie klipów highlightów.
- Inspiracje do skopiowania wzorców: `Ayan-OP/Soccer-Analytics`, `TrishamBP/football_analysis_yolo` (YOLOv8 + supervision + ByteTrack, kompletne piłkarskie pipeline'y).

**Backend (Python):**
- **FastAPI** + **Uvicorn** — REST API + SSE do streamingu czatu.
- Kolejka zadań: **`arq`** lub **Celery** (analiza wideo trwa minuty — musi być async, poza request/response).
- **SQLModel/SQLAlchemy** + **SQLite** (MVP) → Postgres później.
- **`anthropic`** SDK (Claude API). Patrz "LLM" niżej co do warstwy abstrakcji.

**UI (TypeScript):**
- **Next.js** (App Router) + TypeScript + Tailwind.
- **`assistant-ui`** (https://www.assistant-ui.com/) — gotowy, dojrzały komponent czatu AI **wbudowany jako jeden panel** obok panelu analizy. NIE forkujemy całej cudzej apki (np. Open WebUI) — bo czat to tylko fragment dashboardu; wstawiamy komponent do własnego UI.
- Video: natywny `<video>` + **canvas overlay** na tracking/boisko (frame-seek precyzyjny — kluczowe dla highlightów; to powód wyboru TS/JS nad Python-UI typu Streamlit).
- Wykresy/heatmapy (faza analizy): recharts / d3 / canvas.

**LLM (przełączalny):**
- Warstwa adaptera w backendzie z jednym interfejsem `chat(messages, model)`.
- Start: Claude API (Anthropic SDK). **Przed implementacją tej warstwy przeczytać skill `claude-api`** (model IDs, streaming, pricing, tool use) — nie kodować z pamięci.
- Przełącznik na **Ollama** później (ten sam interfejs, inny adapter). Konfiguracja przez env/ustawienia.

## Zakres MVP (kolejność implementacji)

1. **Szkielet repo:** monorepo — `/api` (FastAPI), `/vision` (pipeline Python, importowany przez api), `/web` (Next.js). Docker Compose do uruchomienia całości.
2. **Backend baza:** modele DB (Match, Analysis, Event, Clip, Tag), endpointy upload meczu + lista + status analizy. Kolejka zadań analizy.
3. **Vision — detekcja i tracking:** integracja `ultralytics` + gotowy model piłkarski z Roboflow Universe + `supervision` ByteTrack. Output: per-frame pozycje graczy/piłki + ID trackingu. Zapis do DB.
4. **Vision — eventy (gol/strzał):** heurystyka na bazie pozycji piłki względem bramki/pola karnego (z homografii boiska z `sports`) + nagłe zmiany. To najmocniejszy sygnał; świadomie wąski zakres na MVP.
5. **Highlights — ekstrakcja klipów:** dla każdego eventu (auto + ręczny tag) wycięcie okna czasowego przez ffmpeg → paczka klipów do pobrania/odtworzenia.
6. **UI:** upload, lista meczów, video player z timeline eventów, **ręczne tagowanie** (klik na timeline → event), odtwarzanie klipów, overlay trackingu na canvas.
7. **Chat LLM:** panel `assistant-ui` → backend SSE → adapter Claude. Kontekst: dane meczu/eventy z DB ("opowiedz o tej akcji", "ile było strzałów").

**Świadomie POZA MVP (faza analizy / iteracje):** pełna auto-detekcja kontr/stałych fragmentów, heatmapy/statystyki taktyczne, re-ID zawodników między ujęciami, analiza live (real-time), multi-sport (koszykówka/handball), własny trening modeli per-klub.

## Krytyczne pliki (do utworzenia)

To greenfield — wszystko nowe. Najważniejsze do zaprojektowania jako pierwsze:
- `vision/pipeline.py` — orkiestracja: detekcja → tracking → homografia → eventy → klipy. Serce systemu; tu wpinamy `ultralytics` + `supervision`.
- `vision/events.py` — heurystyka detekcji gola/strzału (najbardziej iteracyjny, ryzykowny element — zacząć od prostej reguły, walidować na realnych nagraniach).
- `api/main.py` + `api/tasks.py` — FastAPI + kolejka analizy (długie zadania async).
- `api/llm/adapter.py` — przełączalna warstwa LLM (Claude ↔ Ollama).
- `web/app/` — Next.js: strona meczu z playerem + timeline; komponent czatu (`assistant-ui`).
- `docker-compose.yml` — spięcie api + worker + web.

## Weryfikacja (end-to-end)

1. **Vision w izolacji:** uruchomić `vision/pipeline.py` na krótkim klipie meczu (np. 2 min z YouTube/własne) → sprawdzić, że YOLO wykrywa graczy/piłkę i ByteTrack utrzymuje ID. Wizualnie: zapis adnotowanego wideo (`supervision` annotators).
2. **Detekcja eventu:** podać klip z golem → potwierdzić, że `events.py` oznacza moment w okolicy faktycznego gola (tolerancja ± kilka s). Tu spodziewać się iteracji — to najtrudniejszy fragment.
3. **Pełny przepływ:** przez UI wgrać mecz → poczekać na analizę → zobaczyć eventy na timeline → dodać ręczny tag → wygenerować i odtworzyć klipy.
4. **Czat:** zadać pytanie o mecz w panelu czatu → potwierdzić streaming odpowiedzi z open api i że odpowiedź używa danych meczu z DB.

## Ryzyka / uwagi

- **Detekcja eventów to największe ryzyko jakościowe.** Dlatego ręczne tagowanie jest w MVP jako fallback — produkt jest użyteczny nawet gdy auto-detekcja jest niedoskonała. Nie obiecywać sztabowi 100% auto-detekcji na start.
- **Roboflow `sports` to nie plug-and-play** — wymaga budowy ze źródeł i prawdopodobnie dotrenowania modeli na nagraniach w jakości/kącie kamery typowym dla amatorskiego/klubowego polskiego footage'u (inny niż broadcast). Zarezerwować czas na zebranie i adnotację własnego mini-datasetu.
- **Wydajność:** analiza pełnego meczu (90 min) na CPU będzie wolna. Na MVP — krótsze klipy / sampling klatek; docelowo GPU. Dlatego analiza jest async w kolejce.
- **Jakość/kąt kamery** amatorskich nagrań to realne wyzwanie dla vision — warto wcześnie przetestować na *prawdziwym* materiale docelowych klientów, nie na broadcast HD.