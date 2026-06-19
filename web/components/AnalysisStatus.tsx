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
  pending: "text-yellow-400",
  running: "text-blue-400",
  done: "text-green-400",
  failed: "text-red-400",
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
        className="bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
      >
        {starting ? "Startowanie…" : "Uruchom analizę"}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className={`text-sm font-medium ${STATUS_COLOR[analysis.status]}`}>
        {STATUS_LABEL[analysis.status]}
        {analysis.status === "running" &&
          analysis.progress > 0 &&
          ` ${Math.round(analysis.progress * 100)}%`}
      </span>
      {analysis.status === "failed" && (
        <button
          onClick={startAnalysis}
          disabled={starting}
          className="text-xs text-gray-400 underline hover:text-white"
        >
          Ponów
        </button>
      )}
      {analysis.status === "done" && (
        <button
          onClick={startAnalysis}
          disabled={starting}
          className="text-xs text-gray-500 hover:text-white border border-gray-700 rounded px-2 py-1"
        >
          Ponów analizę
        </button>
      )}
    </div>
  );
}
