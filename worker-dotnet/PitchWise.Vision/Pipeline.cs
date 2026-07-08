namespace PitchWise.Vision;

/// <summary>Result of a full recording analysis. Port of vision/pipeline.py PipelineResult.</summary>
public sealed class PipelineResult
{
    public double? DurationSeconds { get; init; }
    public double? Fps { get; init; }
    public IReadOnlyList<DetectedEvent> Events { get; init; } = Array.Empty<DetectedEvent>();
    public int FramesProcessed { get; init; }
}

/// <summary>
/// Vision orchestration: detection → tracking → events. Port of vision/pipeline.py
/// analyze_video. Pure domain function — no DB/HTTP dependencies.
/// </summary>
public static class Pipeline
{
    /// <param name="videoPath">Path to the recording.</param>
    /// <param name="modelPath">Exported YOLO11 .onnx.</param>
    /// <param name="classNames">model class-id → raw name.</param>
    /// <param name="frameStride">Process every Nth frame.</param>
    /// <param name="imgsz">Model input size (must match the export).</param>
    /// <param name="eventConfig">Event heuristics tuning (defaults if null).</param>
    /// <param name="onProgress">Progress callback (0..1) for UI/queue.</param>
    public static PipelineResult AnalyzeVideo(
        string videoPath,
        string modelPath,
        IReadOnlyDictionary<int, string> classNames,
        int frameStride = 5,
        int imgsz = 640,
        EventConfig? eventConfig = null,
        Action<double>? onProgress = null)
    {
        (double? duration, double? fps) = FfmpegTools.ProbeVideo(videoPath);

        int frameRate = (int)Math.Round(fps is > 0 ? fps.Value : 25.0);
        using var detector = new Detector(
            modelPath, classNames, frameRate: frameRate,
            frameStride: frameStride, imgsz: imgsz);

        var frames = new List<FrameResult>();
        foreach (FrameResult fr in detector.Run(videoPath))
        {
            frames.Add(fr);
            if (onProgress is not null && duration is > 0 && fr.TimestampSeconds > 0)
                onProgress(Math.Min(0.95, fr.TimestampSeconds / duration.Value));
        }

        List<DetectedEvent> events = Events.Detect(frames, eventConfig);

        onProgress?.Invoke(1.0);

        return new PipelineResult
        {
            DurationSeconds = duration,
            Fps = fps,
            Events = events,
            FramesProcessed = frames.Count,
        };
    }
}
