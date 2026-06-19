"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Analysis } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  pending: "Oczekuje…",
  running: "Analiza…",
  done: "Gotowe",
  failed: "Błąd",
};

const STATUS_COLOR: Record<string, string> = {
  pending: "text-orange-500",
  running: "text-[#2f5fe0]",
  done: "text-green-600",
  failed: "text-red-500",
};

export function AnalysisStatus({
  matchId,
  initialAnalysis,
}: {
  matchId: number;
  initialAnalysis: Analysis | null;
}) {
  const [analysis, setAnalysis] = useState<Analysis | null>(initialAnalysis);
  const [starting, setStarting] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!analysis || analysis.status === "done" || analysis.status === "failed")
      return;

    const interval = setInterval(async () => {
      const updated = await api.analysis.get(matchId);
      setAnalysis(updated);
      if (updated?.status === "done" || updated?.status === "failed") {
        clearInterval(interval);
        router.refresh();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [analysis, matchId, router]);

  async function startAnalysis() {
    setStarting(true);
    const a = await api.analysis.start(matchId);
    setAnalysis(a);
    setStarting(false);
  }

  if (!analysis) {
    return (
      <button
        onClick={startAnalysis}
        disabled={starting}
        className="bg-[#2f5fe0] hover:bg-[#2451c7] disabled:opacity-50 text-white text-xs font-semibold rounded-lg px-3 py-2 transition-colors w-full"
      >
        {starting ? "Startowanie…" : "Uruchom analizę"}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className={`text-xs font-semibold ${STATUS_COLOR[analysis.status]}`}>
        {STATUS_LABEL[analysis.status]}
        {analysis.status === "running" &&
          analysis.progress > 0 &&
          ` ${Math.round(analysis.progress * 100)}%`}
      </span>
      {analysis.status === "failed" && (
        <button
          onClick={startAnalysis}
          disabled={starting}
          className="text-xs text-[#2f5fe0] underline hover:text-[#2451c7] text-left"
        >
          Ponów
        </button>
      )}
      {analysis.status === "done" && (
        <button
          onClick={startAnalysis}
          disabled={starting}
          className="text-xs text-[#6b7280] hover:text-[#14181f] border border-[#ffffff1a] rounded px-2 py-1 transition-colors text-left"
        >
          Ponów analizę
        </button>
      )}
    </div>
  );
}
