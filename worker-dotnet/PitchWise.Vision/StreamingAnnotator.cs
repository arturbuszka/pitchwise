using OpenCvSharp;

namespace PitchWise.Vision;

/// <summary>
/// Single-pass streaming analysis: one walk over the video that BOTH (a) burns detection
/// boxes onto every frame and pipes them into a growing HLS VOD playlist (watchable while
/// still encoding, fully seekable, nothing deleted) AND (b) detects goal/shot events in
/// rolling time windows and hands them back as they are found.
///
/// Replaces the old two-pass approach (separate analysis + annotated render) — one YOLO
/// pass instead of two. Reuses Detector.DetectFrame, Overlay.Draw, Events.Detect and the
/// HLS encoder from FfmpegTools.
/// </summary>
public static class StreamingAnnotator
{
    /// <summary>Result of a streaming run (probe metadata; events are delivered via callback).</summary>
    public sealed class Result
    {
        public double? DurationSeconds { get; init; }
        public double? Fps { get; init; }
        public int FramesProcessed { get; init; }
        public bool EncodeOk { get; init; }
    }

    /// <param name="videoPath">Source recording.</param>
    /// <param name="hlsDir">Output dir for index.m3u8 + seg_*.ts.</param>
    /// <param name="onFirstSegment">Fired once, as soon as the first HLS segment lands, so the
    /// caller can flag playback-ready while analysis continues.</param>
    /// <param name="onEvents">Fired per window with newly detected events (absolute timestamps).</param>
    /// <param name="windowSeconds">Rolling event-detection window length (default 30s).</param>
    public static Result Run(
        string videoPath,
        string hlsDir,
        string modelPath,
        IReadOnlyDictionary<int, string> classNames,
        int frameStride = 5,
        int imgsz = 640,
        EventConfig? eventConfig = null,
        Action<double>? onProgress = null,
        Action? onFirstSegment = null,
        Action<IReadOnlyList<DetectedEvent>>? onEvents = null,
        double windowSeconds = 30.0)
    {
        (double? probeDuration, double? probeFps) = FfmpegTools.ProbeVideo(videoPath);

        using var cap = new VideoCapture(videoPath);
        if (!cap.IsOpened())
            throw new InvalidOperationException($"Cannot open video: {videoPath}");

        double fps = cap.Get(VideoCaptureProperties.Fps);
        if (fps <= 0 || double.IsNaN(fps)) fps = probeFps is > 0 ? probeFps!.Value : 25.0;
        int width = (int)cap.Get(VideoCaptureProperties.FrameWidth);
        int height = (int)cap.Get(VideoCaptureProperties.FrameHeight);
        if (width <= 0 || height <= 0)
            return new Result { DurationSeconds = probeDuration, Fps = fps, EncodeOk = false };

        int stride = Math.Max(1, frameStride);
        double duration = probeDuration ?? (cap.Get(VideoCaptureProperties.FrameCount) / fps);

        using var detector = new Detector(
            modelPath, classNames, frameRate: (int)Math.Round(fps),
            frameStride: stride, imgsz: imgsz);

        var ffmpeg = FfmpegTools.StartEncodeHls(hlsDir, width, height, fps);
        if (ffmpeg is null)
            return new Result { DurationSeconds = duration, Fps = fps, EncodeOk = false };

        var flags = new OverlayFlags { Boxes = true, Labels = true, Traces = false };
        FrameResult? lastResult = null;
        bool firstSegmentSeen = false;
        int framesProcessed = 0;

        // Rolling window of detected frames; on each window boundary we run Events.Detect on
        // it and emit. A small overlap (kept tail) avoids losing an event straddling the edge.
        var window = new List<FrameResult>();
        double windowStart = 0.0;
        var emittedKeys = new HashSet<string>();   // dedup across overlap (type|rounded-ts)

        void FlushWindow()
        {
            if (window.Count == 0) return;
            List<DetectedEvent> found = Events.Detect(window, eventConfig);
            var fresh = new List<DetectedEvent>();
            foreach (DetectedEvent e in found)
            {
                string key = $"{e.Type}|{Math.Round(e.TimestampSeconds, 1)}";
                if (emittedKeys.Add(key)) fresh.Add(e);
            }
            if (fresh.Count > 0) onEvents?.Invoke(fresh);
        }

        try
        {
            using var frame = new Mat();
            int srcIndex = 0;
            while (cap.Read(frame) && !frame.Empty())
            {
                double ts = srcIndex / fps;

                // Detect on stride-frames; reuse the last result on in-between frames so every
                // emitted frame carries boxes.
                if (srcIndex % stride == 0)
                {
                    lastResult = detector.DetectFrame(frame, srcIndex, ts);
                    window.Add(lastResult);
                    framesProcessed++;

                    // Window boundary: analyse & emit, then keep a short overlap tail.
                    if (ts - windowStart >= windowSeconds)
                    {
                        FlushWindow();
                        // keep last ~2s of frames as overlap context for the next window
                        int keepFrom = window.FindIndex(f => f.TimestampSeconds >= ts - 2.0);
                        if (keepFrom > 0) window.RemoveRange(0, keepFrom);
                        windowStart = window.Count > 0 ? window[0].TimestampSeconds : ts;
                    }
                }

                if (lastResult is not null)
                    Overlay.Draw(frame, lastResult, flags);

                if (!WriteFrame(ffmpeg, frame)) break;

                if (!firstSegmentSeen && File.Exists(Path.Combine(hlsDir, "index.m3u8")))
                {
                    firstSegmentSeen = true;
                    onFirstSegment?.Invoke();
                }

                if (onProgress is not null && duration > 0)
                    onProgress(Math.Min(0.99, ts / duration));

                srcIndex++;
            }

            // Final (partial) window.
            FlushWindow();

            ffmpeg.StandardInput.Close();
            ffmpeg.WaitForExit();
            onProgress?.Invoke(1.0);

            return new Result
            {
                DurationSeconds = duration > 0 ? duration : probeDuration,
                Fps = fps,
                FramesProcessed = framesProcessed,
                EncodeOk = ffmpeg.ExitCode == 0 && File.Exists(Path.Combine(hlsDir, "index.m3u8")),
            };
        }
        finally
        {
            try { if (!ffmpeg.HasExited) ffmpeg.Kill(); } catch { /* best effort */ }
            ffmpeg.Dispose();
        }
    }

    private static bool WriteFrame(System.Diagnostics.Process ffmpeg, Mat frame)
    {
        // IMPORTANT: only dispose a clone we own. When the frame is already continuous we
        // write it directly — wrapping it in `using` would dispose the caller's reused Mat
        // and the next cap.Read() throws ObjectDisposedException.
        Mat? clone = null;
        try
        {
            Mat cont = frame.IsContinuous() ? frame : (clone = frame.Clone());
            ffmpeg.StandardInput.BaseStream.Write(cont.AsSpan<byte>());
            return true;
        }
        catch (IOException) { return false; }
        catch (ObjectDisposedException) { return false; }
        finally { clone?.Dispose(); }
    }
}
