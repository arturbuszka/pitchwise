"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export function UploadForm() {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const match = await api.matches.upload(file, title || file.name);
      router.push(`/matches/${match.id}`);
    } catch {
      setError("Błąd podczas uploadu. Sprawdź czy backend działa.");
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-gray-900 border border-gray-800 rounded-xl p-6 flex flex-col gap-4"
    >
      <div className="flex flex-col gap-2">
        <label className="text-sm text-gray-400">Nazwa meczu</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="np. Legia – Wisła 2024"
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-gray-500"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-sm text-gray-400">Plik wideo</label>
        <div
          onClick={() => inputRef.current?.click()}
          className="border-2 border-dashed border-gray-700 rounded-lg px-4 py-8 text-center cursor-pointer hover:border-gray-500 transition-colors"
        >
          {file ? (
            <p className="text-white text-sm">{file.name}</p>
          ) : (
            <p className="text-gray-500 text-sm">
              Kliknij aby wybrać plik (.mp4, .mov, .mkv, .avi)
            </p>
          )}
          <input
            ref={inputRef}
            type="file"
            accept=".mp4,.mov,.mkv,.avi"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={!file || loading}
        className="bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg px-4 py-2.5 transition-colors"
      >
        {loading ? "Wysyłanie…" : "Wgraj mecz"}
      </button>
    </form>
  );
}
