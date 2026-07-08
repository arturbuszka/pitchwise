namespace PitchWise.Vision;

/// <summary>
/// Object classes we expect from a football-specific model (Roboflow sports /
/// football-players-detection). Mapping the model's class indices onto these names
/// happens in <see cref="Yolo11OnnxDetector"/>. Port of vision/types.py.
/// </summary>
public static class ObjectClass
{
    public const string Ball = "ball";
    public const string Player = "player";
    public const string Goalkeeper = "goalkeeper";
    public const string Referee = "referee";
    // Stage 2 hook: goal detection (posts/net). Inactive until the model returns it.
    public const string Goal = "goal";
}

/// <summary>A single detection in original-image pixel coordinates.</summary>
/// <param name="Cls">One of the <see cref="ObjectClass"/> names.</param>
/// <param name="X1">Left.</param>
/// <param name="Y1">Top.</param>
/// <param name="X2">Right.</param>
/// <param name="Y2">Bottom.</param>
/// <param name="Confidence">Detection score.</param>
/// <param name="TrackId">Assigned by the tracker; null before tracking.</param>
public readonly record struct Detection(
    string Cls,
    double X1,
    double Y1,
    double X2,
    double Y2,
    double Confidence,
    int? TrackId = null)
{
    public double CenterX => (X1 + X2) / 2.0;
    public double CenterY => (Y1 + Y2) / 2.0;
}

/// <summary>Detections for a single processed frame.</summary>
public sealed class FrameResult
{
    public int FrameIndex { get; init; }
    public double TimestampSeconds { get; init; }
    public IReadOnlyList<Detection> Detections { get; init; } = Array.Empty<Detection>();

    /// <summary>Highest-confidence ball detection in this frame, or null.</summary>
    public Detection? Ball
    {
        get
        {
            Detection? best = null;
            foreach (Detection d in Detections)
            {
                if (d.Cls != ObjectClass.Ball) continue;
                if (best is null || d.Confidence > best.Value.Confidence) best = d;
            }
            return best;
        }
    }
}

/// <summary>A detected match event (goal / shot). Port of DetectedEvent.</summary>
/// <param name="Type">"goal" | "shot".</param>
public readonly record struct DetectedEvent(
    string Type,
    double TimestampSeconds,
    double Confidence,
    string? Label = null);
