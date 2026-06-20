import { api } from "@/lib/api";
import { notFound } from "next/navigation";
import Link from "next/link";

const SPORT_LABELS: Record<string, string> = {
  football: "⚽ Piłka nożna",
  basketball: "🏀 Koszykówka",
  handball: "🤾 Ręczna",
};

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  draft: { label: "Szkic", cls: "bg-[#eef0f3] text-[#6b7280]" },
  processing: { label: "Analiza…", cls: "bg-orange-100 text-orange-700" },
  done: { label: "Gotowa", cls: "bg-green-100 text-green-700" },
};

export default async function AnalysisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const analysisId = Number(id);

  const analysis = await api.analyses.get(analysisId).catch(() => null);
  if (!analysis || "detail" in (analysis as object)) notFound();

  const status = STATUS_LABELS[analysis.status] ?? STATUS_LABELS.draft;

  return (
    <div className="h-screen flex overflow-hidden bg-[#eceef1]">
      {/* Sidebar */}
      <aside className="w-[236px] bg-[#14181f] flex flex-col overflow-hidden shrink-0">
        <div className="px-4 py-[18px] flex items-center gap-2">
          <span className="w-[26px] h-[26px] rounded-[7px] bg-[#2f5fe0] flex items-center justify-center text-[13px]">
            ⚽
          </span>
          <span className="text-[19px] font-black text-white leading-none tracking-tight">
            Pitch<span className="text-[#6f9bff]">Wise</span>
          </span>
        </div>

        <div className="px-[10px] mb-2">
          <p className="text-[11px] font-bold uppercase tracking-[.06em] text-[#6b7280] px-1.5">
            ANALIZA
          </p>
        </div>

        <div className="mx-3 bg-[#22272f] rounded-[9px] px-3 py-2.5 mb-5">
          <p className="text-[14px] font-semibold text-white truncate">{analysis.name}</p>
          <p className="text-[12px] text-[#8b919b] mt-0.5">
            {SPORT_LABELS[analysis.sport] ?? analysis.sport}
          </p>
        </div>

        <div className="px-[10px] flex-1 overflow-y-auto">
          <div className="flex items-center justify-between mb-2 px-1.5">
            <p className="text-[11px] font-bold uppercase tracking-[.06em] text-[#6b7280]">
              FILMY
            </p>
          </div>
          {analysis.videos.length === 0 ? (
            <p className="text-[12px] text-[#6b7280] px-1.5">Brak filmów</p>
          ) : (
            analysis.videos.map((v) => (
              <div
                key={v.id}
                className="flex items-center gap-2 rounded-[8px] px-[9px] py-2 bg-[#22272f] text-white text-[13px] font-medium mb-1"
              >
                <span className="w-8 h-[22px] shrink-0 bg-[#2b3038] rounded-[4px] flex items-center justify-center text-[10px] text-[#8b919b]">
                  ▶
                </span>
                <span className="flex-1 min-w-0 truncate">{v.name}</span>
              </div>
            ))
          )}
        </div>

        <div className="px-3 pb-4 pt-3 border-t border-[#22272f] flex flex-col gap-2">
          <Link
            href="/"
            className="text-[13px] text-[#8b919b] hover:text-white transition-colors font-medium px-1"
          >
            ↩ Wszystkie analizy
          </Link>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        <div className="bg-white border-b border-[#eaecf0] px-6 py-3.5 flex items-center justify-between shrink-0">
          <span className="text-[15px] font-semibold text-[#14181f]">
            {analysis.name}
          </span>
          <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${status.cls}`}>
            {status.label}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-xl border border-[#eaecf0] p-6 shadow-sm">
              <h2 className="text-[18px] font-bold mb-4">Szczegóły analizy</h2>
              <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-[14px]">
                <dt className="text-[#9aa0a8] font-medium">Nazwa</dt>
                <dd className="font-semibold text-[#14181f]">{analysis.name}</dd>
                <dt className="text-[#9aa0a8] font-medium">Dyscyplina</dt>
                <dd className="font-semibold text-[#14181f]">{SPORT_LABELS[analysis.sport] ?? analysis.sport}</dd>
                <dt className="text-[#9aa0a8] font-medium">Status</dt>
                <dd>
                  <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${status.cls}`}>
                    {status.label}
                  </span>
                </dd>
                <dt className="text-[#9aa0a8] font-medium">Filmy</dt>
                <dd className="font-semibold text-[#14181f]">{analysis.video_count}</dd>
                <dt className="text-[#9aa0a8] font-medium">Utworzono</dt>
                <dd className="font-semibold text-[#14181f] tabular-nums">
                  {new Date(analysis.created_at).toLocaleString("pl-PL")}
                </dd>
                <dt className="text-[#9aa0a8] font-medium">Zaktualizowano</dt>
                <dd className="font-semibold text-[#14181f] tabular-nums">
                  {new Date(analysis.updated_at).toLocaleString("pl-PL")}
                </dd>
              </dl>
            </div>

            {analysis.videos.length > 0 && (
              <div className="bg-white rounded-xl border border-[#eaecf0] p-6 shadow-sm mt-4">
                <h2 className="text-[18px] font-bold mb-4">Filmy</h2>
                <div className="flex flex-col gap-2">
                  {analysis.videos.map((v) => (
                    <div
                      key={v.id}
                      className="flex items-center gap-3 rounded-[10px] border border-[#eaecf0] px-4 py-3"
                    >
                      <span className="text-[20px]">🎬</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-[14px] font-semibold truncate">{v.name}</p>
                        <p className="text-[12px] text-[#9aa0a8]">
                          {v.duration_seconds
                            ? `${Math.round(v.duration_seconds / 60)} min`
                            : "—"}
                          {v.fps ? ` · ${v.fps} fps` : ""}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
