"use client";

import { useState } from "react";
import { api, Clip } from "@/lib/api";

export function ClipPlayer({
  clip,
  matchId,
}: {
  clip: Clip;
  matchId: number;
}) {
  const [open, setOpen] = useState(false);
  const url = api.clips.url(matchId, clip.id);

  return (
    <div>
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-blue-400 hover:text-blue-300 underline"
      >
        {open ? "Ukryj klip" : "Odtwórz klip"}
      </button>
      {open && (
        <video
          src={url}
          controls
          autoPlay
          className="mt-2 w-full rounded-lg bg-black max-h-48"
        />
      )}
    </div>
  );
}
