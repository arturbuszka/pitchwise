"use client";

import { useLocalRuntime, AssistantRuntimeProvider } from "@assistant-ui/react";
import { Thread } from "@assistant-ui/react";
import type { ChatModelAdapter, ChatModelRunOptions } from "@assistant-ui/react";
import { CHAT_API } from "@/lib/api";

function makeAdapter(matchId: number): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }: ChatModelRunOptions) {
      const serialized = messages.map((m) => ({
        role: m.role,
        content: m.content
          .map((p) => ("text" in p ? p.text : ""))
          .join(""),
      }));

      const res = await fetch(CHAT_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ match_id: matchId, messages: serialized }),
        signal: abortSignal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let text = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop()!;
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const token = line.slice(5).trim();
          if (token === "[DONE]") return;
          text += token;
          yield { content: [{ type: "text" as const, text }] };
        }
      }
    },
  };
}

export function Chat({ matchId }: { matchId: number }) {
  const runtime = useLocalRuntime(makeAdapter(matchId));

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread />
    </AssistantRuntimeProvider>
  );
}
