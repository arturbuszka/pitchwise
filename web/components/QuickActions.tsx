"use client";

const ACTIONS = [
  { icon: "⚽", label: "Znajdź bramki", query: "Znajdź wszystkie bramki w tym meczu", primary: true },
  { icon: "🎯", label: "Strzały na bramkę", query: "Pokaż wszystkie strzały na bramkę", primary: false },
  { icon: "↗", label: "Nieskuteczne podania", query: "Znajdź nieskuteczne podania", primary: false },
  { icon: "🟨", label: "Faule i kartki", query: "Pokaż faule i kartki", primary: false },
  { icon: "⛳", label: "Rzuty wolne", query: "Znajdź rzuty wolne", primary: false },
  { icon: "🚩", label: "Spalone", query: "Pokaż sytuacje spalonych", primary: false },
  { icon: "🔄", label: "Zmiany", query: "Pokaż zmiany zawodników", primary: false },
  { icon: "📐", label: "Stałe fragmenty", query: "Znajdź stałe fragmenty gry", primary: false },
];

export function QuickActions({
  onAction,
  disabled,
}: {
  onAction: (query: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {ACTIONS.map((a) => (
        <button
          key={a.label}
          onClick={() => onAction(a.query)}
          disabled={disabled}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-[9px] text-[13px] font-semibold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
            a.primary
              ? "border-[#2f5fe0] text-[#2f5fe0] bg-[#eef3ff] hover:bg-[#dde8ff]"
              : "border-[#e4e7ec] text-[#374151] bg-white hover:border-[#2f5fe0] hover:text-[#2f5fe0]"
          }`}
        >
          <span>{a.icon}</span>
          {a.label}
        </button>
      ))}
    </div>
  );
}
