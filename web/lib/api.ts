const API =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window === "undefined" ? "http://localhost:8000" : "");

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

export type HighlightStatus = "pending" | "running" | "done" | "failed";

export interface Highlight {
  id: number;
  analysis_id: number;
  name: string;
  status: HighlightStatus;
  progress: number;
  error: string | null;
  share_token: string | null;
  share_expires_at: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface ShareLink {
  token: string;
  url: string;
  expires_at: string;
}

export interface SharePublic {
  name: string;
  status: HighlightStatus;
  expires_at: string;
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
      // Upload with progress (XHR) — fetch does not report upload progress.
      // Recommended for large files (up to ~2GB). onProgress receives 0..1.
      uploadWithProgress: (
        analysisId: number,
        file: File,
        name: string,
        onProgress?: (fraction: number) => void
      ): Promise<VideoItem> =>
        new Promise<VideoItem>((resolve, reject) => {
          const fd = new FormData();
          fd.append("file", file);
          fd.append("name", name);
          const xhr = new XMLHttpRequest();
          xhr.open("POST", `${API}/api/analyses/${analysisId}/videos`);
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
          };
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              try {
                resolve(JSON.parse(xhr.responseText) as VideoItem);
              } catch {
                reject(new Error("Invalid server response"));
              }
            } else {
              reject(new Error(`Upload failed (HTTP ${xhr.status})`));
            }
          };
          xhr.onerror = () => reject(new Error("Network error during upload"));
          xhr.send(fd);
        }),
      streamUrl: (analysisId: number, videoId: number) =>
        `${API}/api/analyses/${analysisId}/videos/${videoId}/stream`,
      analyze: (analysisId: number, videoId: number): Promise<VisionJob> =>
        fetch(`${API}/api/analyses/${analysisId}/videos/${videoId}/analyze`, { method: "POST" }).then((r) => r.json()),
      status: (analysisId: number, videoId: number): Promise<VisionJob | null> =>
        fetch(`${API}/api/analyses/${analysisId}/videos/${videoId}/status`, { cache: "no-store" }).then((r) =>
          r.ok ? r.json() : null
        ),
    },

    highlights: {
      create: (analysisId: number, name: string, eventIds: number[]): Promise<Highlight> =>
        fetch(`${API}/api/analyses/${analysisId}/highlights`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, event_ids: eventIds }),
        }).then((r) => r.json()),
      status: (analysisId: number, id: number): Promise<Highlight | null> =>
        fetch(`${API}/api/analyses/${analysisId}/highlights/${id}/status`, { cache: "no-store" }).then((r) =>
          r.ok ? r.json() : null
        ),
      streamUrl: (analysisId: number, id: number) =>
        `${API}/api/analyses/${analysisId}/highlights/${id}/stream`,
      share: (analysisId: number, id: number): Promise<ShareLink> =>
        fetch(`${API}/api/analyses/${analysisId}/highlights/${id}/share`, { method: "POST" }).then((r) => r.json()),
    },

    chatUrl: (analysisId: number) => `${API}/api/analyses/${analysisId}/chat`,
  },

  // Public share access (no auth, time-limited token).
  share: {
    meta: (token: string): Promise<{ ok: boolean; status: number; data: SharePublic | null }> =>
      fetch(`${API}/api/share/${token}`, { cache: "no-store" }).then(async (r) => ({
        ok: r.ok,
        status: r.status,
        data: r.ok ? ((await r.json()) as SharePublic) : null,
      })),
    streamUrl: (token: string) => `${API}/api/share/${token}/stream`,
  },

  eventTypes: {
    list: (sport?: string): Promise<EventTypeConfig[]> => {
      const qs = sport ? `?sport=${sport}` : "";
      return fetch(`${API}/api/event-types${qs}`, { cache: "no-store" }).then((r) => r.json());
    },
  },
};

export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}
