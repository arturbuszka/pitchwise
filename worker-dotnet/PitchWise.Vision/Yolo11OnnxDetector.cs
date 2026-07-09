using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;
using OpenCvSharp;

namespace PitchWise.Vision;

/// <summary>
/// YOLO11 object detector running an ultralytics-exported ONNX model. Reproduces
/// ultralytics' pre/post-processing so the .NET pipeline matches the Python
/// <c>vision/detector.py</c> (ultralytics YOLO11) detection-for-detection.
///
/// Key differences from the YOLOX detector in ByteTrack.NET.Sample:
///   - preprocessing is <c>/255</c> only (NO ImageNet mean/std),
///   - output is <c>[1, 4+numClasses, numAnchors]</c> — TRANSPOSED, NO objectness,
///     boxes already cx,cy,w,h in net-input pixel space (no grid/stride/exp decode),
///   - letterbox pads to a SQUARE (imgsz x imgsz) with grey 114.
/// </summary>
public sealed class Yolo11OnnxDetector : IDisposable
{
    private readonly InferenceSession _session;
    private readonly string _inputName;
    private readonly int _imgsz;
    private readonly float _scoreThresh;
    private readonly float _nmsThresh;
    private readonly IReadOnlyDictionary<int, string> _classNames;
    private readonly Func<string, string?> _mapClass;

    /// <param name="modelPath">Path to the exported YOLO11 .onnx model.</param>
    /// <param name="classNames">model class-id → raw class name (from golden/names).</param>
    /// <param name="mapClass">Maps a raw class name to an <see cref="ObjectClass"/> or null to drop.</param>
    /// <param name="imgsz">Square model input size (default 640, must match export).</param>
    /// <param name="scoreThresh">Min class score to keep (ultralytics conf default 0.25).</param>
    /// <param name="nmsThresh">IoU threshold for NMS (ultralytics iou default 0.7).</param>
    /// <param name="executionProvider">"dml" (DirectML GPU, default) or "cpu". On any DML
    /// failure we transparently fall back to CPU so the worker never crashes.</param>
    /// <param name="deviceId">GPU adapter index for DirectML (default 0).</param>
    public Yolo11OnnxDetector(
        string modelPath,
        IReadOnlyDictionary<int, string> classNames,
        Func<string, string?> mapClass,
        int imgsz = 640,
        float scoreThresh = 0.25f,
        float nmsThresh = 0.7f,
        string executionProvider = "dml",
        int deviceId = 0)
    {
        _session = CreateSession(modelPath, executionProvider, deviceId);
        _inputName = _session.InputMetadata.Keys.First();
        _classNames = classNames;
        _mapClass = mapClass;
        _imgsz = imgsz;
        _scoreThresh = scoreThresh;
        _nmsThresh = nmsThresh;
    }

    // Builds the inference session on the requested provider. DirectML runs on any DX12
    // GPU without CUDA; on ANY failure (no GPU, missing DLL, unsupported op) we fall back
    // to a plain CPU session so the worker keeps running. Every outcome is logged loudly
    // (console banner + a onnx_provider.log file) so it's never a mystery which one ran.
    private static InferenceSession CreateSession(string modelPath, string ep, int deviceId)
    {
        if (string.Equals(ep, "dml", StringComparison.OrdinalIgnoreCase))
        {
            try
            {
                var so = new SessionOptions
                {
                    // Both are required by the DirectML execution provider.
                    EnableMemoryPattern = false,
                    ExecutionMode = ExecutionMode.ORT_SEQUENTIAL,
                };
                so.AppendExecutionProvider_DML(deviceId);
                var session = new InferenceSession(modelPath, so);
                LogProvider($"DirectML GPU (device {deviceId}) — ACTIVE");
                return session;
            }
            catch (Exception ex)
            {
                LogProvider($"DirectML init FAILED ({ex.GetType().Name}: {ex.Message}) — falling back to CPU");
            }
        }
        var cpuSession = new InferenceSession(modelPath);
        LogProvider("CPU execution provider — ACTIVE");
        return cpuSession;
    }

    // Loud, unmissable log of which ONNX provider actually ran: a console banner AND a
    // onnx_provider.log file in the working dir (survives even when the worker runs as a
    // background job whose stdout isn't visible).
    private static void LogProvider(string message)
    {
        // Providers compiled into this ORT build (proves the DirectML DLL is present).
        string available;
        try { available = string.Join(", ", OrtEnv.Instance().GetAvailableProviders()); }
        catch { available = "n/a"; }
        string line = $"[ONNX] {DateTime.Now:HH:mm:ss} {message} | available=[{available}]";
        string banner = new string('=', 60);
        Console.WriteLine($"\n{banner}\n{line}\n{banner}\n");
        try
        {
            File.AppendAllText(
                Path.Combine(AppContext.BaseDirectory, "onnx_provider.log"),
                line + Environment.NewLine);
        }
        catch { /* logging must never break inference */ }
    }

    /// <summary>Runs detection on one BGR frame. Boxes are in original-image coords.</summary>
    public IReadOnlyList<Detection> Detect(Mat frameBgr)
    {
        LetterboxInfo lb = Letterbox(frameBgr, _imgsz);
        try
        {
            DenseTensor<float> input = Preprocess(lb.Padded);
            var inputs = new List<NamedOnnxValue>
            {
                NamedOnnxValue.CreateFromTensor(_inputName, input),
            };
            using IDisposableReadOnlyCollection<DisposableNamedOnnxValue> results = _session.Run(inputs);
            Tensor<float> output = results.First().AsTensor<float>();
            return Postprocess(output, lb);
        }
        finally
        {
            lb.Padded.Dispose();
        }
    }

    private readonly record struct LetterboxInfo(Mat Padded, double Ratio, int PadLeft, int PadTop);

    /// <summary>
    /// Aspect-preserving resize into a square imgsz canvas with CENTERED grey-114
    /// padding — matches ultralytics <c>LetterBox(center=True, auto=False)</c>. To map
    /// a net-space coord back: subtract the pad offset, then divide by ratio.
    /// </summary>
    private static LetterboxInfo Letterbox(Mat src, int imgsz)
    {
        double ratio = Math.Min(imgsz / (double)src.Width, imgsz / (double)src.Height);
        int resizedW = (int)Math.Round(src.Width * ratio);
        int resizedH = (int)Math.Round(src.Height * ratio);

        // Centered padding, same rounding as ultralytics get_params.
        double dw = (imgsz - resizedW) / 2.0;
        double dh = (imgsz - resizedH) / 2.0;
        int left = (int)Math.Round(dw - 0.1);
        int top = (int)Math.Round(dh - 0.1);

        var canvas = new Mat(imgsz, imgsz, src.Type(), Scalar.All(114));
        using var resized = new Mat();
        Cv2.Resize(src, resized, new Size(resizedW, resizedH), interpolation: InterpolationFlags.Linear);
        using (var roi = new Mat(canvas, new Rect(left, top, resizedW, resizedH)))
        {
            resized.CopyTo(roi);
        }
        return new LetterboxInfo(canvas, ratio, left, top);
    }

    /// <summary>BGR Mat → CHW float tensor: BGR→RGB, /255. No mean/std (YOLO11).</summary>
    private DenseTensor<float> Preprocess(Mat padded)
    {
        int h = padded.Height;
        int w = padded.Width;
        var tensor = new DenseTensor<float>(new[] { 1, 3, h, w });

        Vec3b[] pixels = new Vec3b[h * w];
        padded.GetArray(out pixels);

        for (int y = 0; y < h; y++)
        {
            int rowOffset = y * w;
            for (int x = 0; x < w; x++)
            {
                Vec3b p = pixels[rowOffset + x];
                // p.Item0=B, p.Item1=G, p.Item2=R; model expects RGB.
                tensor[0, 0, y, x] = p.Item2 / 255f;
                tensor[0, 1, y, x] = p.Item1 / 255f;
                tensor[0, 2, y, x] = p.Item0 / 255f;
            }
        }
        return tensor;
    }

    /// <summary>
    /// Decodes YOLO11 output <c>[1, 4+numClasses, numAnchors]</c> (transposed, no
    /// objectness) into original-image boxes, applies score threshold + per-class NMS.
    /// </summary>
    private IReadOnlyList<Detection> Postprocess(Tensor<float> output, LetterboxInfo lb)
    {
        double ratio = lb.Ratio;
        int channels = output.Dimensions[1];       // 4 + numClasses
        int numAnchors = output.Dimensions[2];
        int numClasses = channels - 4;

        var candidates = new List<(double[] tlbr, float score, int cls)>();

        for (int i = 0; i < numAnchors; i++)
        {
            // Best class over this anchor (no objectness in YOLO11).
            int bestCls = 0;
            float bestScore = 0f;
            for (int c = 0; c < numClasses; c++)
            {
                float s = output[0, 4 + c, i];
                if (s > bestScore)
                {
                    bestScore = s;
                    bestCls = c;
                }
            }

            if (bestScore < _scoreThresh) continue;

            // Boxes are cx,cy,w,h in net-input pixel space — no grid/stride/exp decode.
            double cx = output[0, 0, i];
            double cy = output[0, 1, i];
            double bw = output[0, 2, i];
            double bh = output[0, 3, i];

            // center→corner in net space, subtract the centered pad, then divide by
            // ratio to map back to the original image.
            double x1 = (cx - bw / 2.0 - lb.PadLeft) / ratio;
            double y1 = (cy - bh / 2.0 - lb.PadTop) / ratio;
            double x2 = (cx + bw / 2.0 - lb.PadLeft) / ratio;
            double y2 = (cy + bh / 2.0 - lb.PadTop) / ratio;

            candidates.Add((new[] { x1, y1, x2, y2 }, bestScore, bestCls));
        }

        return NonMaxSuppression(candidates);
    }

    /// <summary>Greedy per-class NMS; maps surviving classes to our categories.</summary>
    private IReadOnlyList<Detection> NonMaxSuppression(
        List<(double[] tlbr, float score, int cls)> candidates)
    {
        var kept = new List<Detection>();

        foreach (int cls in candidates.Select(c => c.cls).Distinct())
        {
            var byClass = candidates
                .Where(c => c.cls == cls)
                .OrderByDescending(c => c.score)
                .ToList();

            var suppressed = new bool[byClass.Count];
            for (int i = 0; i < byClass.Count; i++)
            {
                if (suppressed[i]) continue;

                (double[] boxI, float scoreI, int clsI) = byClass[i];

                string rawName = _classNames.TryGetValue(clsI, out string? n) ? n : "";
                string? mapped = _mapClass(rawName);
                if (mapped is not null)
                {
                    kept.Add(new Detection(
                        mapped, boxI[0], boxI[1], boxI[2], boxI[3], scoreI));
                }

                for (int j = i + 1; j < byClass.Count; j++)
                {
                    if (suppressed[j]) continue;
                    if (Iou(boxI, byClass[j].tlbr) > _nmsThresh) suppressed[j] = true;
                }
            }
        }

        return kept;
    }

    private static double Iou(double[] a, double[] b)
    {
        double ix1 = Math.Max(a[0], b[0]);
        double iy1 = Math.Max(a[1], b[1]);
        double ix2 = Math.Min(a[2], b[2]);
        double iy2 = Math.Min(a[3], b[3]);
        double iw = Math.Max(0.0, ix2 - ix1);
        double ih = Math.Max(0.0, iy2 - iy1);
        double inter = iw * ih;
        double areaA = Math.Max(0.0, a[2] - a[0]) * Math.Max(0.0, a[3] - a[1]);
        double areaB = Math.Max(0.0, b[2] - b[0]) * Math.Max(0.0, b[3] - b[1]);
        double union = areaA + areaB - inter;
        return union <= 0.0 ? 0.0 : inter / union;
    }

    public void Dispose() => _session.Dispose();
}
