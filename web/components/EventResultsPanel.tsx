"use client";

import { AnalysisEvent, EventType, EventTypeConfig, formatTime } from "@/lib/api";

function confColor(conf: number): string {
  if (conf >= 0.8) return "#16a34a"; // zielony — wysoka
  if (conf >= 0.5) return "#e0a72f"; // żółty — średnia
  return "#ef4444"; // czerwony — niska
}

function playerLabel(ev: AnalysisEvent): string {
  const parts: string[] = [];
  if (ev.player_name || ev.player_number) {
    parts.push(
      ev.player_number ? `#${ev.player_number} ${ev.player_name ?? ""}`.trim() : (ev.player_name ?? "")
    );
  }
  if (ev.assist_name || ev.assist_number) {
    const assist = ev.assist_number
      ? `#${ev.assist_number} ${ev.assist_name ?? ""}`.trim()
      : (ev.assist_name ?? "");
    parts.push(`(asysta ${assist})`);
  }
  return parts.join(" ");
}

export function EventResultsPanel({
  events,
  activeFilters,
  eventTypes,
  onSeek,
}: {
  events: AnalysisEvent[];
  activeFilters: Set<EventType>;
  eventTypes: EventTypeConfig[];
  onSeek: (seconds: number) => void;
}) {
  const cfg = new Map(eventTypes.map((t) => [t.key, t]));

  const filtered =
    activeFilters.size === 0
      ? events
      : events.filter((e) => activeFilters.has(e.type));

  // Nagłówek dynamiczny
  let heading = "Wyniki";
  if (activeFilters.size === 1) {
    const only = [...activeFilters][0];
    heading = cfg.get(only)?.label ?? "Wyniki";
  } else if (activeFilters.size > 1) {
    heading = "Wybrane";
  }

  return (
    <div className="px-5 pb-6">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[16px] font-bold text-[#14181f]">
          {heading}{" "}
          <span className="text-[#9aa0a8] font-medium">
            · {filtered.length} {filtered.length === 1 ? "wynik" : "wyniki"}
          </span>
        </p>
        {filtered.length > 0 && (
          <p className="text-[12px] text-[#9aa0a8] font-medium">
            klik wynik → skok w wideo
          </p>
        )}
      </div>

      <div className="border border-[#eaecf0] rounded-xl overflow-hidden bg-white">
        {filtered.length === 0 ? (
          <p className="text-[#9aa0a8] text-sm text-center py-6 px-4">
            {activeFilters.size > 0
              ? "Brak zdarzeń tego typu — wkrótce auto-detekcja."
              : "Brak wyników — uruchom analizę filmu."}
          </p>
        ) : (
          <div className="flex flex-col gap-2 p-2">
            {filtered.map((ev) => {
              const t = cfg.get(ev.type);
              const conf = ev.confidence !== null ? Math.round(ev.confidence * 100) : null;
              const player = playerLabel(ev);
              const desc = ev.note ?? ev.label;

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

                  {/* Tag typu */}
                  <span
                    className="text-[11px] font-bold rounded-full px-2 py-0.5 shrink-0 uppercase tracking-wider"
                    style={{ background: t?.bg ?? "#eef0f3", color: t?.color ?? "#6b7280" }}
                  >
                    {t?.label ?? ev.type}
                  </span>

                  {/* Zawodnik / asysta */}
                  <span className="text-sm text-[#14181f] shrink-0 max-w-[40%] truncate">
                    {player || "—"}
                  </span>

                  {/* Opis */}
                  <span className="text-[13px] text-[#9aa0a8] flex-1 truncate">
                    {desc ?? ""}
                  </span>

                  {/* Pewność */}
                  {conf !== null && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <div className="w-10 h-1.5 bg-[#eceef1] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${conf}%`, background: confColor(ev.confidence!) }}
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
        )}
      </div>
    </div>
  );
}
