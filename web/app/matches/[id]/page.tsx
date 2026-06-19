import { api } from "@/lib/api";
import { MatchDetailClient } from "@/components/MatchDetailClient";
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

  return (
    <MatchDetailClient
      match={match}
      initialAnalysis={analysis}
      events={events}
      clips={clips}
      videoUrl={videoUrl}
      matchId={matchId}
    />
  );
}
