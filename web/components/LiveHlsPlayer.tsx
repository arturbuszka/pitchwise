"use client";

import { useEffect, useRef } from "react";
import Hls from "hls.js";

export function LiveHlsPlayer({
  hlsUrl,
  className,
}: {
  hlsUrl: string;
  className?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !hlsUrl) return;

    // Native HLS (Safari/iOS)
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = hlsUrl;
      video.play().catch(() => {});
      return;
    }

    if (!Hls.isSupported()) return;

    const hls = new Hls({
      liveSyncDurationCount: 3,
      liveMaxLatencyDurationCount: 6,
      maxBufferLength: 10,
      maxMaxBufferLength: 20,
      // Retry aggressively on 404 (segment not yet available)
      manifestLoadingRetryDelay: 500,
      manifestLoadingMaxRetry: 20,
      levelLoadingRetryDelay: 500,
      levelLoadingMaxRetry: 20,
    });

    hlsRef.current = hls;
    hls.loadSource(hlsUrl);
    hls.attachMedia(video);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.play().catch(() => {});
    });

    hls.on(Hls.Events.ERROR, (_evt, data) => {
      if (data.fatal) {
        // For live streams, try to recover instead of giving up
        if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
          hls.startLoad();
        } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          hls.recoverMediaError();
        }
      }
    });

    return () => {
      hls.destroy();
      hlsRef.current = null;
    };
  }, [hlsUrl]);

  return (
    <video
      ref={videoRef}
      autoPlay
      muted
      playsInline
      controls
      className={className}
    />
  );
}
