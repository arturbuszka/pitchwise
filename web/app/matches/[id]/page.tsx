import { api } from "@/lib/api";
import { AnalysisStatus } from "@/components/AnalysisStatus";
import { EventTimeline } from "@/components/EventTimeline";
import { Chat } from "@/components/Chat";
import { notFound } from "next/navigation";

export default async function MatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const matchId = Number(id);

  const match = await api.matches.get(matchId).catch(() => null);
  if (!match || "detail" in (match as object)) notFound();

  const [analysis, events, clips] = await Promise.all([
    api.analysis.get(matchId),
    api.events.list(matchId).catch(() => []),
    api.clips.list(matchId).catch(() => []),
  ]);

  const videoUrl = api.videoUrl(matchId);
  const done = analysis?.status === "done";

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 bg-gray-900 flex items-center justify-between">
        <div>
          <h1 className="text-white font-semibold text-lg">{match.title}</h1>
          <p className="text-gray-500 text-sm">
            {new Date(match.created_at).toLocaleString("pl-PL")}
            {match.duration_seconds
              ? ` · ${Math.round(match.duration_seconds / 60)} min`
              : ""}
            {match.fps ? ` · ${match.fps} fps` : ""}
          </p>
        </div>
        <AnalysisStatus matchId={matchId} initialAnalysis={analysis} />
      </div>

      {/* Body — dwie kolumny */}
      <div className="flex flex-1 overflow-hidden">
        {/* Lewa — video + eventy */}
        <div className="flex flex-col flex-1 overflow-y-auto border-r border-gray-800">
          <div className="p-4">
            <video
              src={videoUrl}
              controls
              className="w-full rounded-lg bg-black max-h-64"
            />
          </div>

          <div className="px-4 pb-4 flex-1">
            {done ? (
              <EventTimeline
                events={events}
                clips={clips}
                matchId={matchId}
              />
            ) : (
              <p className="text-gray-500 text-sm text-center py-8">
                {analysis
                  ? "Analiza w toku — eventy pojawią się po zakończeniu"
                  : "Uruchom analizę aby wykryć eventy"}
              </p>
            )}
          </div>
        </div>

        {/* Prawa — czat */}
        <div className="w-96 flex flex-col overflow-hidden">
          <Chat matchId={matchId} />
        </div>
      </div>
    </div>
  );
}
