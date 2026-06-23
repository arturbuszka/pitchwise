using PitchWise.Api.Dtos;

namespace PitchWise.Api.Config;

// Odpowiednik EVENT_TYPE_CONFIG z worker/app/models.py. Kolejność zachowana 1:1.
public static class EventTypeConfig
{
    public static readonly IReadOnlyList<EventTypeConfigOut> All = new List<EventTypeConfigOut>
    {
        new("goal",         "Bramka",         "⚽", "#16a34a", "#e6f5ec"),
        new("shot",         "Strzał",         "🎯", "#2f5fe0", "#e8edff"),
        new("wayward_pass", "Strata",         "↗",  "#e0732f", "#fff0e6"),
        new("foul",         "Faul",           "🟨", "#ef4444", "#fee2e2"),
        new("free_kick",    "Rzut wolny",     "⛳", "#2f5fe0", "#e8edff"),
        new("offside",      "Spalony",        "🚩", "#8b5cf6", "#f3e8ff"),
        new("substitution", "Zmiana",         "🔄", "#06b6d4", "#e0f7fa"),
        new("set_piece",    "Stały fragment", "📐", "#64748b", "#f1f5f9"),
        new("manual",       "Ręczny",         "✏️",  "#6b7280", "#f9fafb"),
    };
}
