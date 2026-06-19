"use client";

import { useEffect, useRef, useState } from "react";
import { CHAT_API } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function Chat({ matchId }: { matchId: number }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || running) return;

    const next: Message[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setRunning(true);

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setMessages((m) => [...m, { role: "assistant", content: "" }]);

    try {
      const res = await fetch(CHAT_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          match_id: matchId,
          messages: next.map((m) => ({ role: m.role, content: m.content })),
        }),
        signal: ctrl.signal,
      });

      const reader = res.body!.getReader();
      const dec = new TextDecoder();
      let buf = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop()!;
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const token = line.slice(5).trim();
          if (token === "[DONE]") break;
          setMessages((m) => {
            const copy = [...m];
            copy[copy.length - 1] = {
              role: "assistant",
              content: copy[copy.length - 1].content + token,
            };
            return copy;
          });
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: "Błąd połączenia z LLM.",
          };
          return copy;
        });
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 text-sm font-medium text-gray-400">
        Czat o meczu
      </div>

      {/* Wiadomości */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        {messages.length === 0 && (
          <p className="text-gray-600 text-sm text-center mt-8">
            Zapytaj o mecz — eventy, statystyki, momenty…
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-green-700 text-white"
                  : "bg-gray-800 text-gray-100"
              }`}
            >
              {m.content || (
                <span className="text-gray-500 animate-pulse">…</span>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-3 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Napisz pytanie…"
          disabled={running}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-gray-500 disabled:opacity-50"
        />
        <button
          onClick={running ? () => abortRef.current?.abort() : send}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            running
              ? "bg-red-700 hover:bg-red-600 text-white"
              : "bg-green-600 hover:bg-green-500 text-white disabled:bg-gray-700"
          }`}
          disabled={!running && !input.trim()}
        >
          {running ? "Stop" : "Wyślij"}
        </button>
      </div>
    </div>
  );
}
