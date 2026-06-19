const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Match {
  id: number;
  title: string;
  filename: string;
  duration_seconds: number | null;
  fps: number | null;
  created_at: string;
}

export interface Analysis {
  id: number;
  match_id: number;
  status: "pending" | "running" | "done" | "failed";
  progress: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface Event {
  id: number;
  match_id: number;
  type: "goal" | "shot" | "manual";
  source: "auto" | "manual";
  timestamp_seconds: number;
  confidence: number | null;
  label: string | null;
}

export interface Clip {
  id: number;
  event_id: number;
  match_id: number;
  filename: string;
  start_seconds: number;
  end_seconds: number;
}

export const api = {
  matches: {
    list: (): Promise<Match[]> =>
      fetch(`${API}/api/matches`, { cache: "no-store" }).then((r) => r.json()),
    get: (id: number): Promise<Match> =>
      fetch(`${API}/api/matches/${id}`, { cache: "no-store" }).then((r) =>
        r.json()
      ),
    upload: (file: File, title: string): Promise<Match> => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", title);
      return fetch(`${API}/api/matches`, { method: "POST", body: fd }).then(
        (r) => r.json()
      );
    },
  },
  analysis: {
    start: (matchId: number): Promise<Analysis> =>
      fetch(`${API}/api/matches/${matchId}/analyze`, {
        method: "POST",
      }).then((r) => r.json()),
    get: (matchId: number): Promise<Analysis | null> =>
      fetch(`${API}/api/matches/${matchId}/analysis`, {
        cache: "no-store",
      }).then((r) => (r.ok ? r.json() : null)),
  },
  events: {
    list: (matchId: number): Promise<Event[]> =>
      fetch(`${API}/api/matches/${matchId}/events`, {
        cache: "no-store",
      }).then((r) => r.json()),
    createManual: (
      matchId: number,
      timestamp: number,
      label?: string
    ): Promise<Event> =>
      fetch(`${API}/api/matches/${matchId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timestamp_seconds: timestamp, label }),
      }).then((r) => r.json()),
    delete: (matchId: number, eventId: number): Promise<void> =>
      fetch(`${API}/api/matches/${matchId}/events/${eventId}`, {
        method: "DELETE",
      }).then(() => undefined),
  },
  clips: {
    list: (matchId: number): Promise<Clip[]> =>
      fetch(`${API}/api/matches/${matchId}/clips`, {
        cache: "no-store",
      }).then((r) => r.json()),
    url: (matchId: number, clipId: number) =>
      `${API}/api/matches/${matchId}/clips/${clipId}/file`,
  },
  videoUrl: (matchId: number) => `${API}/api/matches/${matchId}/video`,
};

export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export const CHAT_API = `${API}/api/chat`;
