"use client";

import { OldEvent as Event, OldClip as Clip, formatTime } from "@/lib/api";

const TAG_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  goal: { bg: "bg-green-100", text: "text-green-700", label: "Bramka" },
  shot: { bg: "bg-blue-100", text: "text-blue-700", label: "Strzał" },
  manual: { bg: "bg-purple-100", text: "text-purple-700", label: "Tag ręczny" },
};

export function ResultsTable({
  events,
  clips: _clips,
  onSeek,
}: {
  events: Event[];
  clips: Clip[];
  matchId: number;
  onSeek: (seconds: number) => void;
}) {
  if (events.length === 0) {
    return (
      <p className="text-[#9aa0a8] text-sm text-center py-6">
        Brak wyników — uruchom analizę lub użyj szybkich akcji.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {events.map((ev) => {
        const tag = TAG_STYLE[ev.type] ?? TAG_STYLE.manual;
        const conf = ev.confidence !== null ? Math.round(ev.confidence * 100) : null;

        return (
          <div
            key={ev.id}
            onClick={() => onSeek(ev.timestamp_seconds)}
            className="flex items-center gap-3 bg-white rounded-xl px-3 py-2.5 cursor-pointer hover:shadow-sm border border-[#eceef1] hover:border-[#2f5fe0]/30 transition-all"
          >
            {/* Timestamp */}
            <span className="bg-[#14181f] text-white text-xs font-mono rounded-[7px] px-2 py-1 shrink-0 tabular-nums">
              {formatTime(ev.timestamp_seconds)}
            </span>

            {/* Tag */}
            <span
              className={`text-[11px] font-bold rounded-full px-2 py-0.5 shrink-0 uppercase tracking-wider ${tag.bg} ${tag.text}`}
            >
              {tag.label}
            </span>

            {/* Label / player */}
            <span className="text-sm text-[#14181f] flex-1 truncate">
              {ev.label ?? "—"}
            </span>

            {/* Confidence bar */}
            {conf !== null && (
              <div className="flex items-center gap-1.5 shrink-0">
                <div className="w-10 h-1.5 bg-[#eceef1] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[#2f5fe0] rounded-full"
                    style={{ width: `${conf}%` }}
                  />
                </div>
                <span className="text-[11px] text-[#6b7280] font-semibold tabular-nums">
                  {conf}%
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
