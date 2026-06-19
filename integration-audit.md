# PitchWise — Audyt integracji nowego layoutu

## Kontekst

Nowy wireframe Next.js został zaimplementowany (5 nowych komponentów + modyfikacje istniejących).
Poniższy dokument opisuje, które funkcje UI mają pełne podpięcie do backendu, a które są zaślepkami.

---

## ✅ W pełni podpięte

| Funkcja UI | Komponent | Endpoint API |
|---|---|---|
| Lista analiz (home) | `HomeClient` → `api.matches.list()` | `GET /api/matches` |
| Tworzenie nowej analizy | `NewAnalysisModal` → `api.matches.upload()` | `POST /api/matches` |
| Widok szczegółów meczu | `MatchDetailClient` (server fetch) | `GET /api/matches/{id}` |
| Odtwarzanie wideo | `<video src={videoUrl}>` | `GET /api/matches/{id}/video` |
| Status analizy + polling co 3s | `AnalysisStatus` → `api.analysis.get()` | `GET /api/matches/{id}/analysis` |
| Uruchomienie analizy | `AnalysisStatus` → `api.analysis.start()` | `POST /api/matches/{id}/analyze` |
| Lista eventów | `ResultsTable` ← props z server fetch | `GET /api/matches/{id}/events` |
| Seek wideo po kliknięciu eventu | `ResultsTable` → `onSeek` → `videoRef.currentTime` | (lokalne) |
| Chat z LLM (streaming SSE) | `Chat` → `CHAT_API` | `POST /api/chat` |
| Szybkie akcje → chat | `QuickActions` → `setPendingAction` → `Chat` | (lokalne → chat) |
| Lista klipów (fetch) | `page.tsx` → `api.clips.list()` | `GET /api/matches/{id}/clips` |

---

## ❌ Zaślepki (UI gotowe, brak logiki)

### P1 — Krytyczne dla UX

| Funkcja UI | Lokalizacja | Problem |
|---|---|---|
| **Filtr sportowy (home)** | `HomeClient.tsx` — `sport` state | Dropdown zmienia stan, ale nie filtruje listy meczów |
| **Sport w modalu tworzenia** | `NewAnalysisModal.tsx` — `sport` state | Wybór sportu nie trafia do API (brak pola `sport` w FormData i modelu) |
| **Wyświetlanie klipów** | `ResultsTable.tsx` — `clips` prop jako `_clips` | Klipy są pobierane i przekazywane, ale nieużywane — kliknięcie eventu jedynie seekuje wideo, nie odtwarza klipu |

### P2 — Ważne funkcje biznesowe

| Funkcja UI | Lokalizacja | Problem |
|---|---|---|
| **Ręczny tag eventu** | brak w UI | `api.events.createManual()` istnieje w `lib/api.ts`, ale żaden komponent go nie wywołuje |
| **Usuwanie eventu** | brak w UI | `api.events.delete()` istnieje w `lib/api.ts`, ale żaden komponent go nie wywołuje |

### P3 — Kosmetyczne / nice-to-have

| Funkcja UI | Lokalizacja | Problem |
|---|---|---|
| **"+ załącz" (drugi film)** | `MatchDetailClient.tsx:75` | Przycisk bez `onClick`, nie otwiera żadnego inputu |
| **"⧉ Odłącz"** | `MatchDetailClient.tsx:120` | Przycisk bez `onClick`, brak endpointu w API |
| **"⤢ Rozmiar"** | `MatchDetailClient.tsx:123` | Przycisk bez `onClick`, brak logiki resize/fullscreen |
| **"⚙ Ustawienia"** | `MatchDetailClient.tsx:98` | Link `href="#"`, brak strony `/settings` |

---

## Plan napraw

### P1 — Filtr sportowy w HomeClient

**Plik:** `web/components/HomeClient.tsx`

Zmiana: filtrować `matches` po `sport` lokalnie po stronie klienta.

```tsx
const filtered = matches.filter(
  (m) => sport === "all" || m.sport === sport
);
```

Wymaga też dodania pola `sport` do modelu `Match`.

---

### P1 — Pole `sport` end-to-end

**Backend:**
- `api/app/models.py` — dodać `sport: str = "football"` do `Match`
- `api/app/schemas.py` — dodać `sport` do `MatchOut`
- `api/app/routers/matches.py` — zapisywać `sport: str = Form("football")` przy upload

**Frontend:**
- `web/lib/api.ts` — dodać `sport: string` do interfejsu `Match`
- `web/components/NewAnalysisModal.tsx` — `fd.append("sport", sport)` w `handleSubmit()`

---

### P1 — Klipy w ResultsTable

**Plik:** `web/components/ResultsTable.tsx`

Zmiana: jeśli do eventu istnieje klip (`clips.find(c => c.event_id === ev.id)`), pokazać miniaturę / przycisk "▶ Klip" obok timestampu, a kliknięcie → `<video src={api.clips.url(...)}>`

---

### P2 — Ręczny tag „Taguj moment"

**Plik:** `web/components/MatchDetailClient.tsx`

Dodać przycisk "🏷 Taguj moment" obok nagłówka wideo. Kliknięcie → odczytuje `videoRef.current.currentTime` → wywołuje `api.events.createManual(matchId, currentTime)` → odświeża eventy.

---

### P2 — Usuwanie eventu

**Plik:** `web/components/ResultsTable.tsx`

Dodać ikonę 🗑 na końcu każdego wiersza → wywołuje `api.events.delete(matchId, ev.id)` → usuwa event z lokalnego stanu.

---

## Weryfikacja po naprawach

1. `docker compose up` (lub `npm run dev` + `uvicorn`)
2. Stworzyć nową analizę — sprawdzić czy `sport` widoczny w bazie / odpowiedzi API
3. Na home — zmienić filtr sportu → tabela powinna się odfiltrować
4. Na stronie meczu z eventami z klipami — kliknięcie eventu → klip powinien się pojawić
5. Kliknąć "Taguj moment" → event z aktualnym timestampem powinien pojawić się w tabeli
6. Usunąć event ikoną 🗑 → wiersz powinien zniknąć

---

## Podsumowanie

Backend ma **wszystkie potrzebne endpointy** (`createManual`, `delete`, `clips`). Praca do wykonania leży **wyłącznie po stronie frontendu** (P1/P2), z wyjątkiem pola `sport`, które wymaga migracji bazy i zmiany schematu API.
