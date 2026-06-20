import { OldEvent as Event, OldClip as Clip, formatTime } from "@/lib/api";
import { ClipPlayer } from "@/components/ClipPlayer";

const TYPE_ICON: Record<string, string> = {
  goal: "⚽",
  shot: "🎯",
  manual: "📌",
};

const TYPE_LABEL: Record<string, string> = {
  goal: "Gol",
  shot: "Strzał",
  manual: "Tag ręczny",
};

export function EventTimeline({
  events,
  clips,
  matchId,
}: {
  events: Event[];
  clips: Clip[];
  matchId: number;
}) {
  const clipsByEvent = clips.reduce<Record<number, Clip>>((acc, c) => {
    acc[c.event_id] = c;
    return acc;
  }, {});

  if (events.length === 0) {
    return (
      <p className="text-gray-500 text-sm text-center py-8">
        Brak wykrytych eventów.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-widest mb-3">
        Eventy ({events.length})
      </h2>
      {events.map((ev) => {
        const clip = clipsByEvent[ev.id];
        return (
          <div
            key={ev.id}
            className="bg-gray-800 rounded-lg px-4 py-3 flex flex-col gap-2"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg">{TYPE_ICON[ev.type]}</span>
              <div className="flex-1">
                <span className="text-white text-sm font-medium">
                  {TYPE_LABEL[ev.type]}
                </span>
                {ev.label && (
                  <span className="text-gray-500 text-xs ml-2">{ev.label}</span>
                )}
              </div>
              <span className="text-gray-400 text-sm font-mono">
                {formatTime(ev.timestamp_seconds)}
              </span>
              {ev.confidence !== null && (
                <span className="text-gray-600 text-xs">
                  {Math.round(ev.confidence * 100)}%
                </span>
              )}
            </div>
            {clip && <ClipPlayer clip={clip} matchId={matchId} />}
          </div>
        );
      })}
    </div>
  );
}
