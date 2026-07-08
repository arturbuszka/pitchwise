using OpenCvSharp;
using BT = ByteTrack;

namespace PitchWise.Vision;

/// <summary>
/// Object detection + tracking on video frames. Port of vision/detector.py:
/// YOLO11 (ONNX) for detection + ByteTrack.NET for tracking. Emits
/// <see cref="FrameResult"/> with per-detection track ids and our class names.
///
/// ByteTrack.NET's tracker takes only box+score and returns box+id (it drops the
/// class), so after <c>Update</c> we re-attach each track id to the originating
/// classed detection by best-IoU match — the same information supervision.ByteTrack
/// carries through natively on the Python side.
/// </summary>
public sealed class Detector : IDisposable
{
    /// <summary>Maps a model class name onto our categories (port of _CLASS_ALIASES).
    /// Covers football-specific models and the default COCO (person/sports ball).</summary>
    public static readonly IReadOnlyDictionary<string, string> ClassAliases =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["ball"] = ObjectClass.Ball,
            ["sports ball"] = ObjectClass.Ball,
            ["football"] = ObjectClass.Ball,
            ["soccer ball"] = ObjectClass.Ball,
            ["player"] = ObjectClass.Player,
            ["person"] = ObjectClass.Player,
            ["referee"] = ObjectClass.Referee,
            ["main referee"] = ObjectClass.Referee,
            ["side referee"] = ObjectClass.Referee,
            ["goalkeeper"] = ObjectClass.Goalkeeper,
            ["goal keeper"] = ObjectClass.Goalkeeper,
            // Stage 2 hook: active only when a football model returns a goal class.
            ["goal"] = ObjectClass.Goal,
            ["goalpost"] = ObjectClass.Goal,
        };

    /// <summary>Default class map: alias lookup, drops unknown classes (returns null).</summary>
    public static string? MapClass(string raw) =>
        ClassAliases.TryGetValue(raw, out string? mapped) ? mapped : null;

    private readonly Yolo11OnnxDetector _detector;
    private readonly BT.ByteTracker _tracker;
    private readonly int _frameStride;

    /// <param name="modelPath">Exported YOLO11 .onnx.</param>
    /// <param name="classNames">model class-id → raw name (from the exported model / golden).</param>
    /// <param name="frameRate">Source fps; scales the tracker's lost-track buffer.</param>
    /// <param name="frameStride">Process every Nth frame (matches Python frame_stride).</param>
    /// <param name="imgsz">Model input size (must match the export).</param>
    /// <param name="mapClass">Class-name mapper; defaults to <see cref="MapClass"/>.</param>
    public Detector(
        string modelPath,
        IReadOnlyDictionary<int, string> classNames,
        int frameRate = 25,
        int frameStride = 5,
        int imgsz = 640,
        Func<string, string?>? mapClass = null)
    {
        _detector = new Yolo11OnnxDetector(
            modelPath, classNames, mapClass ?? MapClass, imgsz);
        var config = new BT.ByteTrackerConfig
        {
            TrackThresh = 0.5f,
            TrackBuffer = 30,
            MatchThresh = 0.8f,
            Mot20 = false,
        };
        // Deterministic track ids across runs (see ByteTrack README).
        BT.BaseTrack.ResetCount();
        _tracker = new BT.ByteTracker(config, frameRate);
        _frameStride = Math.Max(1, frameStride);
    }

    /// <summary>Detect + track on a single BGR frame.</summary>
    public FrameResult DetectFrame(Mat frame, int frameIndex, double timestampSeconds)
    {
        IReadOnlyList<Detection> classed = _detector.Detect(frame);

        // Feed boxes+scores to the tracker; it returns boxes+ids (no class).
        var btDets = new List<BT.Detection>(classed.Count);
        foreach (Detection d in classed)
            btDets.Add(BT.Detection.FromTlbr(new[] { d.X1, d.Y1, d.X2, d.Y2 }, (float)d.Confidence));

        IReadOnlyList<BT.STrack> tracks = _tracker.Update(btDets);

        // Re-attach track ids to classed detections by best IoU (tracker dropped class).
        var withIds = new List<Detection>(classed.Count);
        var used = new bool[tracks.Count];
        foreach (Detection d in classed)
        {
            double[] box = { d.X1, d.Y1, d.X2, d.Y2 };
            int bestJ = -1;
            double bestIou = 0.5;
            for (int j = 0; j < tracks.Count; j++)
            {
                if (used[j]) continue;
                double iou = Iou(box, tracks[j].Tlbr);
                if (iou > bestIou) { bestIou = iou; bestJ = j; }
            }
            int? id = null;
            if (bestJ >= 0) { used[bestJ] = true; id = tracks[bestJ].TrackId; }
            withIds.Add(d with { TrackId = id });
        }

        return new FrameResult
        {
            FrameIndex = frameIndex,
            TimestampSeconds = timestampSeconds,
            Detections = withIds,
        };
    }

    /// <summary>Iterates frames (every frame_stride) yielding detections with track ids.
    /// Port of Detector.run(). fps is read from the video for timestamps.</summary>
    public IEnumerable<FrameResult> Run(string videoPath)
    {
        using var cap = new VideoCapture(videoPath);
        if (!cap.IsOpened())
            throw new InvalidOperationException($"Cannot open video: {videoPath}");

        double fps = cap.Get(VideoCaptureProperties.Fps);
        if (fps <= 0 || double.IsNaN(fps)) fps = 25.0;

        using var frame = new Mat();
        int i = 0;              // stride-step counter
        int srcIndex = 0;       // absolute source frame index
        while (cap.Read(frame) && !frame.Empty())
        {
            if (srcIndex % _frameStride == 0)
            {
                int frameIndex = i * _frameStride;
                double ts = frameIndex / fps;
                yield return DetectFrame(frame, frameIndex, ts);
                i++;
            }
            srcIndex++;
        }
    }

    private static double Iou(double[] a, double[] b)
    {
        double ix1 = Math.Max(a[0], b[0]), iy1 = Math.Max(a[1], b[1]);
        double ix2 = Math.Min(a[2], b[2]), iy2 = Math.Min(a[3], b[3]);
        double iw = Math.Max(0.0, ix2 - ix1), ih = Math.Max(0.0, iy2 - iy1);
        double inter = iw * ih;
        double areaA = Math.Max(0.0, a[2] - a[0]) * Math.Max(0.0, a[3] - a[1]);
        double areaB = Math.Max(0.0, b[2] - b[0]) * Math.Max(0.0, b[3] - b[1]);
        double union = areaA + areaB - inter;
        return union <= 0.0 ? 0.0 : inter / union;
    }

    public void Dispose() => _detector.Dispose();
}
