"use client";

import { EventType } from "@/lib/api";

const ACTIONS: { icon: string; label: string; type: EventType }[] = [
  { icon: "⚽", label: "Bramki", type: "goal" },
  { icon: "🎯", label: "Strzały na bramkę", type: "shot" },
  { icon: "↗", label: "Nieskuteczne podania", type: "wayward_pass" },
  { icon: "🟨", label: "Faule i kartki", type: "foul" },
  { icon: "⛳", label: "Rzuty wolne", type: "free_kick" },
  { icon: "🚩", label: "Spalone", type: "offside" },
  { icon: "🔄", label: "Zmiany", type: "substitution" },
  { icon: "📐", label: "Stałe fragmenty", type: "set_piece" },
];

/**
 * Pasek szybkich akcji = multi-select filtry panelu wyników.
 * Domyślnie nic nie zaznaczone => panel pokazuje wszystkie zdarzenia.
 * Toggle typu zawęża listę (suma zaznaczonych typów, OR).
 */
export function QuickActions({
  active,
  onToggle,
}: {
  active: Set<EventType>;
  onToggle: (type: EventType) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {ACTIONS.map((a) => {
        const isActive = active.has(a.type);
        return (
          <button
            key={a.type}
            onClick={() => onToggle(a.type)}
            aria-pressed={isActive}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-[9px] text-[13px] font-semibold border transition-colors ${
              isActive
                ? "border-[#2f5fe0] text-[#2f5fe0] bg-[#eef3ff] hover:bg-[#dde8ff]"
                : "border-[#e4e7ec] text-[#374151] bg-white hover:border-[#2f5fe0] hover:text-[#2f5fe0]"
            }`}
          >
            <span>{a.icon}</span>
            {a.label}
          </button>
        );
      })}
    </div>
  );
}
