"use client";

import { useRef, useState } from "react";
import { Match, Analysis, Event, Clip } from "@/lib/api";
import { Chat } from "./Chat";
import { QuickActions } from "./QuickActions";
import { ResultsTable } from "./ResultsTable";
import { AnalysisStatus } from "./AnalysisStatus";

interface Props {
  match: Match;
  initialAnalysis: Analysis | null;
  events: Event[];
  clips: Clip[];
  videoUrl: string;
  matchId: number;
}

export function MatchDetailClient({
  match,
  initialAnalysis,
  events,
  clips,
  videoUrl,
  matchId,
}: Props) {
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  function seekVideo(seconds: number) {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
    }
  }

  return (
    <div className="h-screen flex overflow-hidden bg-[#eceef1]">
      {/* ===== LEFT SIDEBAR ===== */}
      <aside className="w-[236px] bg-[#14181f] flex flex-col overflow-hidden shrink-0">
        {/* Logo */}
        <div className="px-4 py-[18px] flex items-center gap-2">
          <span className="w-[26px] h-[26px] rounded-[7px] bg-[#2f5fe0] flex items-center justify-center text-[13px]">
            ⚽
          </span>
          <span className="text-[19px] font-black text-white leading-none tracking-tight">
            Pitch<span className="text-[#6f9bff]">Wise</span>
          </span>
        </div>

        {/* ANALIZA label */}
        <div className="px-[10px] mb-2">
          <p className="text-[11px] font-bold uppercase tracking-[.06em] text-[#6b7280] px-1.5">
            ANALIZA
          </p>
        </div>

        {/* Match card */}
        <div className="mx-3 bg-[#22272f] rounded-[9px] px-3 py-2.5 mb-5">
          <p className="text-[14px] font-semibold text-white truncate">{match.title}</p>
          <p className="text-[12px] text-[#8b919b] mt-0.5">
            ⚽ Piłka nożna
            {match.duration_seconds
              ? ` · ${Math.round(match.duration_seconds / 60)} min`
              : ""}
          </p>
        </div>

        {/* FILMY section */}
        <div className="px-[10px] flex-1 overflow-y-auto">
          <div className="flex items-center justify-between mb-2 px-1.5">
            <p className="text-[11px] font-bold uppercase tracking-[.06em] text-[#6b7280]">
              FILMY
            </p>
            <button className="bg-[#22272f] text-[#9aa0a8] rounded-[7px] text-[12px] px-2 py-0.5 font-semibold hover:text-white transition-colors">
              + załącz
            </button>
          </div>

          {/* Current video */}
          <div className="flex items-center gap-2 rounded-[8px] px-[9px] py-2 bg-[#2f5fe0] text-white text-[13px] font-medium mb-1">
            <span className="w-8 h-[22px] shrink-0 bg-[#2b3038] rounded-[4px] flex items-center justify-center text-[10px] text-[#8b919b]">
              ▶
            </span>
            <span className="flex-1 min-w-0 truncate">{match.filename}</span>
          </div>
        </div>

        {/* Bottom: analysis status + back */}
        <div className="px-3 pb-4 pt-3 border-t border-[#22272f] flex flex-col gap-2">
          <AnalysisStatus matchId={matchId} initialAnalysis={initialAnalysis} />
          <a
            href="/"
            className="text-[13px] text-[#8b919b] hover:text-white transition-colors font-medium px-1"
          >
            ↩ Wszystkie analizy
          </a>
          <a
            href="#"
            className="text-[13px] text-[#8b919b] hover:text-white transition-colors font-medium px-1"
          >
            ⚙ Ustawienia
          </a>
        </div>
      </aside>

      {/* ===== CENTER COLUMN ===== */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Center header */}
        <div className="bg-white border-b border-[#eaecf0] px-6 py-3.5 flex items-center justify-between shrink-0">
          <span className="text-[15px] font-semibold text-[#14181f] truncate">
            {match.filename}{" "}
            <span className="text-[#9aa0a8] font-normal">
              {match.duration_seconds
                ? `· ${Math.round(match.duration_seconds / 60)}:00`
                : ""}
            </span>
          </span>
          <div className="flex gap-2">
            <button className="border border-[#e4e7ec] rounded-[8px] px-3 py-1.5 text-[12px] text-[#6b7280] font-semibold hover:border-[#14181f] hover:text-[#14181f] transition-colors">
              ⧉ Odłącz
            </button>
            <button className="border border-[#e4e7ec] rounded-[8px] px-3 py-1.5 text-[12px] text-[#6b7280] font-semibold hover:border-[#14181f] hover:text-[#14181f] transition-colors">
              ⤢ Rozmiar
            </button>
          </div>
        </div>

        {/* Scrollable center body */}
        <div className="flex-1 overflow-y-auto">
          {/* Video */}
          <div className="p-5">
            <div className="relative rounded-xl overflow-hidden bg-[#1a3d2e] shadow-sm">
              <video
                ref={videoRef}
                src={videoUrl}
                controls
                className="w-full max-h-72 object-contain"
              />
            </div>
          </div>

          {/* Quick actions */}
          <div className="px-5 pb-4">
            <p className="text-[12px] font-bold uppercase tracking-[.05em] text-[#9aa0a8] mb-2">
              SZYBKIE AKCJE
            </p>
            <QuickActions onAction={(msg) => setPendingAction(msg)} />
          </div>

          {/* Results */}
          <div className="px-5 pb-6">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[16px] font-bold text-[#14181f]">
                {events.length > 0 ? (
                  <>
                    Wyniki{" "}
                    <span className="text-[#9aa0a8] font-medium">
                      · {events.length} wynik{events.length !== 1 ? "i" : ""}
                    </span>
                  </>
                ) : (
                  "Wyniki"
                )}
              </p>
              {events.length > 0 && (
                <p className="text-[12px] text-[#9aa0a8] font-medium">
                  klik wynik → skok w wideo
                </p>
              )}
            </div>
            <div className="border border-[#eaecf0] rounded-xl overflow-hidden bg-white">
              <ResultsTable
                events={events}
                clips={clips}
                matchId={matchId}
                onSeek={seekVideo}
              />
            </div>
          </div>
        </div>
      </main>

      {/* ===== RIGHT CHAT RAIL ===== */}
      <aside className="w-[316px] shrink-0 flex flex-col overflow-hidden border-l border-[#eaecf0]">
        <Chat
          matchId={matchId}
          pendingMessage={pendingAction}
          onPendingConsumed={() => setPendingAction(null)}
        />
      </aside>
    </div>
  );
}
