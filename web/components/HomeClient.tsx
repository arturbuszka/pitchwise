"use client";

import { useState } from "react";
import Link from "next/link";
import { Match } from "@/lib/api";
import { NewAnalysisModal } from "./NewAnalysisModal";

const SPORT_OPTIONS = [
  "Wszystkie sporty",
  "Piłka nożna",
  "Koszykówka",
  "Ręczna",
];

function StatusBadge({ title }: { title: string }) {
  const lower = title.toLowerCase();
  if (lower.includes("analiz")) {
    return (
      <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-700">
        Analiza…
      </span>
    );
  }
  return (
    <span className="inline-block px-3 py-1 rounded-full text-xs font-semibold bg-[#eef0f3] text-[#6b7280]">
      Szkic
    </span>
  );
}

export function HomeClient({ matches }: { matches: Match[] }) {
  const [modalOpen, setModalOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [sport, setSport] = useState("Wszystkie sporty");

  const filtered = matches.filter((m) =>
    m.title.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <nav className="bg-white border-b border-[#eaecf0] px-6 h-[58px] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="w-[30px] h-[30px] rounded-[8px] bg-[#14181f] text-white flex items-center justify-center text-[15px]">
            ⚽
          </span>
          <span className="text-[21px] font-black tracking-tight leading-none">
            Pitch<span className="text-[#2f5fe0]">Wise</span>
          </span>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setModalOpen(true)}
            className="bg-[#2f5fe0] hover:bg-[#2451c7] text-white text-[14px] font-semibold rounded-[10px] px-4 py-2.5 flex items-center gap-1.5 shadow-sm transition-colors"
          >
            <span className="text-[17px] leading-none">+</span>
            Nowa analiza
          </button>
          <div className="w-9 h-9 rounded-full bg-[#eceef1] flex items-center justify-center text-[13px] font-bold text-[#6b7280]">
            TK
          </div>
        </div>
      </nav>

      {/* Main */}
      <main className="flex-1 px-6 py-8" style={{ maxWidth: 1380, margin: "0 auto", width: "100%" }}>
        {/* Heading row */}
        <div className="flex items-end justify-between mb-6">
          <div>
            <h1 className="text-[26px] font-black tracking-tight">Twoje analizy</h1>
            <p className="text-[14px] text-[#9aa0a8] mt-1 font-medium">
              Kliknij wiersz, aby otworzyć panel analizy
            </p>
          </div>
          <div className="flex gap-2">
            <select
              value={sport}
              onChange={(e) => setSport(e.target.value)}
              className="border border-[#e4e7ec] rounded-[9px] px-3 py-2 text-[13px] text-[#6b7280] font-medium bg-white focus:outline-none focus:border-[#2f5fe0]"
            >
              {SPORT_OPTIONS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="🔍 Szukaj"
              className="border border-[#e4e7ec] rounded-[9px] px-3 py-2 text-[13px] text-[#6b7280] font-medium bg-white focus:outline-none focus:border-[#2f5fe0] w-48"
            />
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border border-[#eaecf0] overflow-hidden shadow-sm">
          {/* Column headers */}
          <div className="flex items-center gap-4 px-[18px] py-3 text-[12px] font-semibold uppercase tracking-wider text-[#9aa0a8] border-b border-[#eaecf0]">
            <div className="flex-[1.7]">Nazwa</div>
            <div className="flex-1">Sport</div>
            <div className="w-[120px]">Zaktualizowano</div>
            <div className="w-[80px] text-center">Filmy</div>
            <div className="w-[130px]">Status</div>
            <div className="w-6" />
          </div>

          {filtered.length === 0 ? (
            <p className="text-[#9aa0a8] text-sm text-center py-12">
              {matches.length === 0
                ? 'Brak analiz. Kliknij "Nowa analiza" aby rozpocząć.'
                : "Brak wyników dla podanej frazy."}
            </p>
          ) : (
            filtered.map((m) => (
              <Link
                key={m.id}
                href={`/matches/${m.id}`}
                className="flex items-center gap-4 px-[18px] py-4 border-b border-[#f1f3f5] cursor-pointer hover:bg-[#f7f8fa] transition-colors last:border-b-0"
              >
                <div className="flex-[1.7] flex items-center gap-3 min-w-0">
                  <span className="w-[38px] h-[38px] rounded-[9px] bg-[#f1f3f5] flex items-center justify-center text-base shrink-0">
                    ⚽
                  </span>
                  <div className="min-w-0">
                    <p className="text-[15px] font-semibold truncate">{m.title}</p>
                    <p className="text-[12px] text-[#9aa0a8] font-medium">
                      {m.duration_seconds
                        ? `${Math.round(m.duration_seconds / 60)} min`
                        : "—"}
                    </p>
                  </div>
                </div>
                <div className="flex-1 text-[14px] text-[#6b7280] font-medium">
                  Piłka nożna
                </div>
                <div className="w-[120px] text-[14px] text-[#6b7280] font-medium tabular-nums">
                  {new Date(m.created_at).toLocaleDateString("pl-PL")}
                </div>
                <div className="w-[80px] text-center">
                  <span className="inline-flex items-center justify-center min-w-[26px] h-6 px-2 rounded-[7px] bg-[#f1f3f5] text-[13px] font-semibold text-[#6b7280] tabular-nums">
                    1
                  </span>
                </div>
                <div className="w-[130px]">
                  <StatusBadge title={m.title} />
                </div>
                <div className="w-6 text-center text-[20px] text-[#cbd0d6]">›</div>
              </Link>
            ))
          )}
        </div>
      </main>

      {modalOpen && <NewAnalysisModal onClose={() => setModalOpen(false)} />}
    </div>
  );
}
