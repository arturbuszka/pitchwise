namespace PitchWise.Worker;

/// <summary>
/// Vision-specific worker settings (the API's AppSettings covers DB/Redis/dirs).
/// Mirrors the vision knobs from worker/app/config.py.
/// </summary>
public sealed class WorkerSettings
{
    /// <summary>Path to the exported YOLO11 .onnx model (football or yolo11n fallback).</summary>
    public string YoloModelPath { get; set; } = "models/football.onnx";

    /// <summary>Sidecar JSON with {classId: name}. Defaults to "&lt;model&gt;.names.json".
    /// Produced by export_and_golden.py (the golden's "names") or written by hand.</summary>
    public string? YoloNamesPath { get; set; }

    /// <summary>Model input size — must match the export (default 640).</summary>
    public int Imgsz { get; set; } = 640;

    /// <summary>Process every Nth frame (matches Python FRAME_STRIDE).</summary>
    public int FrameStride { get; set; } = 3;

    /// <summary>Per-event clip extraction (Python GENERATE_CLIPS). Off by default.</summary>
    public bool GenerateClips { get; set; }
    public double ClipPreSeconds { get; set; } = 6.0;
    public double ClipPostSeconds { get; set; } = 4.0;

    /// <summary>ffmpeg / ffprobe binaries (PATH lookup by default).</summary>
    public string FfmpegPath { get; set; } = "ffmpeg";
    public string FfprobePath { get; set; } = "ffprobe";

    /// <summary>BRPOP block timeout (server-side), seconds.</summary>
    public int BrpopTimeoutSeconds { get; set; } = 5;
}
