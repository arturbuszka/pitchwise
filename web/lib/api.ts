const API = process.env.NEXT_PUBLIC_API_URL || "";

// ---------------------------------------------------------------------------
// Nowe interfejsy (nowy model danych)
// ---------------------------------------------------------------------------

export type Sport = "football" | "basketball" | "handball";
export type SessionStatus = "draft" | "processing" | "done";
export type VisionJobStatus = "pending" | "running" | "done" | "failed";
export type EventType =
  | "goal"
  | "shot"
  | "wayward_pass"
  | "foul"
  | "free_kick"
  | "offside"
  | "substitution"
  | "set_piece"
  | "manual";

export interface AnalysisSummary {
  id: number;
  name: string;
  subtitle: string | null;
  sport: Sport;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  video_count: number;
}

export interface VideoItem {
  id: number;
  analysis_id: number;
  name: string;
  duration_seconds: number | null;
  fps: number | null;
  order: number;
}

export interface AnalysisDetail extends AnalysisSummary {
  videos: VideoItem[];
}

export interface ClipItem {
  id: number;
  event_id: number;
  video_id: number;
  filename: string;
  start_seconds: number;
  end_seconds: number;
}

export interface AnalysisEvent {
  id: number;
  analysis_id: number;
  video_id: number | null;
  type: EventType;
  source: "auto" | "manual";
  timestamp_seconds: number;
  confidence: number | null;
  label: string | null;
  note: string | null;
  player_number: number | null;
  player_name: string | null;
  assist_number: number | null;
  assist_name: string | null;
  clip: ClipItem | null;
}

export interface VisionJob {
  id: number;
  video_id: number;
  status: VisionJobStatus;
  progress: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface EventTypeConfig {
  key: EventType;
  label: string;
  icon: string;
  color: string;
  bg: string;
}

// ---------------------------------------------------------------------------
// Nowe metody API
// ---------------------------------------------------------------------------

export const api = {
  analyses: {
    list: (sport?: string, search?: string): Promise<AnalysisSummary[]> => {
      const params = new URLSearchParams();
      if (sport) params.set("sport", sport);
      if (search) params.set("search", search);
      const qs = params.toString();
      return fetch(`${API}/api/analyses${qs ? `?${qs}` : ""}`, { cache: "no-store" }).then((r) => r.json());
    },
    get: (id: number): Promise<AnalysisDetail> =>
      fetch(`${API}/api/analyses/${id}`, { cache: "no-store" }).then((r) => r.json()),
    create: (name: string, sport: Sport, subtitle?: string): Promise<AnalysisDetail> =>
      fetch(`${API}/api/analyses`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, sport, subtitle }),
      }).then((r) => r.json()),

    events: {
      list: (analysisId: number, type?: EventType): Promise<AnalysisEvent[]> => {
        const qs = type ? `?type=${type}` : "";
        return fetch(`${API}/api/analyses/${analysisId}/events${qs}`, { cache: "no-store" }).then((r) => r.json());
      },
      create: (
        analysisId: number,
        payload: {
          timestamp_seconds: number;
          type?: EventType;
          label?: string;
          note?: string;
          video_id?: number;
          player_number?: number;
          player_name?: string;
          assist_number?: number;
          assist_name?: string;
        }
      ): Promise<AnalysisEvent> =>
        fetch(`${API}/api/analyses/${analysisId}/events`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }).then((r) => r.json()),
      delete: (analysisId: number, eventId: number): Promise<void> =>
        fetch(`${API}/api/analyses/${analysisId}/events/${eventId}`, { method: "DELETE" }).then(() => undefined),
    },

    videos: {
      list: (analysisId: number): Promise<VideoItem[]> =>
        fetch(`${API}/api/analyses/${analysisId}/videos`, { cache: "no-store" }).then((r) => r.json()),
      upload: (analysisId: number, file: File, name: string): Promise<VideoItem> => {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("name", name);
        return fetch(`${API}/api/analyses/${analysisId}/videos`, { method: "POST", body: fd }).then((r) => r.json());
      },
      streamUrl: (analysisId: number, videoId: number) =>
        `${API}/api/analyses/${analysisId}/videos/${videoId}/stream`,
      analyze: (analysisId: number, videoId: number): Promise<VisionJob> =>
        fetch(`${API}/api/analyses/${analysisId}/videos/${videoId}/analyze`, { method: "POST" }).then((r) => r.json()),
      status: (analysisId: number, videoId: number): Promise<VisionJob | null> =>
        fetch(`${API}/api/analyses/${analysisId}/videos/${videoId}/status`, { cache: "no-store" }).then((r) =>
          r.ok ? r.json() : null
        ),
    },

    chatUrl: (analysisId: number) => `${API}/api/analyses/${analysisId}/chat`,
  },

  eventTypes: {
    list: (sport?: string): Promise<EventTypeConfig[]> => {
      const qs = sport ? `?sport=${sport}` : "";
      return fetch(`${API}/api/event-types${qs}`, { cache: "no-store" }).then((r) => r.json());
    },
  },

  // ---------------------------------------------------------------------------
  // Stare metody (backward compat — do usunięcia po migracji komponentów)
  // ---------------------------------------------------------------------------

  matches: {
    list: (): Promise<Match[]> =>
      fetch(`${API}/api/matches`, { cache: "no-store" }).then((r) => r.json()),
    get: (id: number): Promise<Match> =>
      fetch(`${API}/api/matches/${id}`, { cache: "no-store" }).then((r) => r.json()),
    upload: (file: File, title: string): Promise<Match> => {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", title);
      return fetch(`${API}/api/matches`, { method: "POST", body: fd }).then((r) => r.json());
    },
  },
  analysis: {
    start: (matchId: number): Promise<OldAnalysis> =>
      fetch(`${API}/api/matches/${matchId}/analyze`, { method: "POST" }).then((r) => r.json()),
    get: (matchId: number): Promise<OldAnalysis | null> =>
      fetch(`${API}/api/matches/${matchId}/analysis`, { cache: "no-store" }).then((r) => (r.ok ? r.json() : null)),
  },
  events: {
    list: (matchId: number): Promise<OldEvent[]> =>
      fetch(`${API}/api/matches/${matchId}/events`, { cache: "no-store" }).then((r) => r.json()),
    createManual: (matchId: number, timestamp: number, label?: string): Promise<OldEvent> =>
      fetch(`${API}/api/matches/${matchId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timestamp_seconds: timestamp, label }),
      }).then((r) => r.json()),
    delete: (matchId: number, eventId: number): Promise<void> =>
      fetch(`${API}/api/matches/${matchId}/events/${eventId}`, { method: "DELETE" }).then(() => undefined),
  },
  clips: {
    list: (matchId: number): Promise<OldClip[]> =>
      fetch(`${API}/api/matches/${matchId}/clips`, { cache: "no-store" }).then((r) => r.json()),
    url: (matchId: number, clipId: number) => `${API}/api/matches/${matchId}/clips/${clipId}/file`,
  },
  videoUrl: (matchId: number) => `${API}/api/matches/${matchId}/video`,
};

// Stare interfejsy (backward compat)
export interface Match {
  id: number;
  title: string;
  filename: string;
  duration_seconds: number | null;
  fps: number | null;
  created_at: string;
}
export interface OldAnalysis {
  id: number;
  match_id: number;
  status: "pending" | "running" | "done" | "failed";
  progress: number;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}
export interface OldEvent {
  id: number;
  match_id: number;
  type: "goal" | "shot" | "manual";
  source: "auto" | "manual";
  timestamp_seconds: number;
  confidence: number | null;
  label: string | null;
}
export interface OldClip {
  id: number;
  event_id: number;
  match_id: number;
  filename: string;
  start_seconds: number;
  end_seconds: number;
}

export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export const CHAT_API = `${API}/api/chat`;
