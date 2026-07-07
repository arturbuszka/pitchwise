using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using PitchWise.Api.Config;
using PitchWise.Api.Data;
using PitchWise.Api.Models;
using PitchWise.Vision;

namespace PitchWise.Worker;

/// <summary>
/// Runs one vision job: analyses a video and writes Event/Clip/Video + progress/status.
/// Port of worker/app/vision_runner.py run_vision_job. Uses short-lived DbContext scopes
/// (like the Python short-lived sessions) so progress writes don't hold a long transaction.
/// </summary>
public sealed class VisionRunner
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly AppSettings _appSettings;
    private readonly WorkerSettings _worker;
    private readonly IReadOnlyDictionary<int, string> _classNames;

    public VisionRunner(
        IServiceScopeFactory scopeFactory,
        AppSettings appSettings,
        WorkerSettings worker,
        IReadOnlyDictionary<int, string> classNames)
    {
        _scopeFactory = scopeFactory;
        _appSettings = appSettings;
        _worker = worker;
        _classNames = classNames;
    }

    private AppDbContext NewDb(IServiceScope scope) =>
        scope.ServiceProvider.GetRequiredService<AppDbContext>();

    public async Task RunAsync(int jobId, CancellationToken ct)
    {
        // 1. Load job + video, mark running.
        int videoId;
        string videoPath;
        using (IServiceScope scope = _scopeFactory.CreateScope())
        {
            AppDbContext db = NewDb(scope);
            VisionJob? job = await db.VisionJobs.FirstOrDefaultAsync(j => j.Id == jobId, ct);
            if (job is null) return;

            Video? video = await db.Videos.FirstOrDefaultAsync(v => v.Id == job.VideoId, ct);
            if (video is null)
            {
                job.Status = VisionJobStatus.Failed;
                job.Error = "Video not found";
                job.FinishedAt = DateTime.UtcNow;
                await db.SaveChangesAsync(ct);
                return;
            }

            job.Status = VisionJobStatus.Running;
            await db.SaveChangesAsync(ct);

            videoId = video.Id;
            videoPath = Path.Combine(_appSettings.UploadsDir, video.Filename);
        }

        try
        {
            // 2. Run the CPU-bound pipeline off the async path, throttling progress writes.
            double lastSaved = 0.0;
            void OnProgress(double p)
            {
                if (p - lastSaved < 0.02 && p < 1.0) return;
                lastSaved = p;
                // fire-and-forget short write; failures here must not kill the job.
                _ = SaveProgressAsync(jobId, p);
            }

            PipelineResult result = await Task.Run(() => Pipeline.AnalyzeVideo(
                videoPath,
                _worker.YoloModelPath,
                _classNames,
                frameStride: _worker.FrameStride,
                imgsz: _worker.Imgsz,
                onProgress: OnProgress), ct);

            // 3. Persist results in one scope.
            using IServiceScope scope = _scopeFactory.CreateScope();
            AppDbContext db = NewDb(scope);

            Video? video = await db.Videos.FirstOrDefaultAsync(v => v.Id == videoId, ct);
            VisionJob? job = await db.VisionJobs.FirstOrDefaultAsync(j => j.Id == jobId, ct);
            if (video is null || job is null) return;

            video.DurationSeconds = result.DurationSeconds;
            video.Fps = result.Fps;

            foreach (DetectedEvent det in result.Events)
            {
                var ev = new Event
                {
                    AnalysisId = video.AnalysisId,
                    VideoId = video.Id,
                    Type = EventTypeMap.FromDb(det.Type),
                    Source = EventSource.Auto,
                    TimestampSeconds = det.TimestampSeconds,
                    Confidence = det.Confidence,
                    Label = det.Label,
                };
                db.Events.Add(ev);
                await db.SaveChangesAsync(ct);   // flush to get ev.Id (mirrors Python flush)

                if (_worker.GenerateClips)
                {
                    double start = Math.Max(0.0, det.TimestampSeconds - _worker.ClipPreSeconds);
                    double end = det.TimestampSeconds + _worker.ClipPostSeconds;
                    string clipName = $"video{video.Id}_event{ev.Id}.mp4";
                    string clipPath = Path.Combine(_appSettings.ClipsDir, clipName);
                    if (FfmpegTools.ExtractClip(videoPath, clipPath, start, end))
                    {
                        db.Clips.Add(new Clip
                        {
                            EventId = ev.Id,
                            VideoId = video.Id,
                            Filename = clipName,
                            StartSeconds = start,
                            EndSeconds = end,
                        });
                    }
                }
            }

            job.Status = VisionJobStatus.Done;
            job.Progress = 1.0;
            job.FinishedAt = DateTime.UtcNow;

            // 4. Flip the session to "done" when every job in it is finished.
            var siblingJobs = await db.VisionJobs
                .Join(db.Videos, j => j.VideoId, v => v.Id, (j, v) => new { j, v.AnalysisId })
                .Where(x => x.AnalysisId == video.AnalysisId && x.j.Id != jobId)
                .Select(x => x.j.Status)
                .ToListAsync(ct);
            bool allDone = siblingJobs.All(s => s == VisionJobStatus.Done);
            if (allDone)
            {
                AnalysisSession? session = await db.AnalysisSessions
                    .FirstOrDefaultAsync(s => s.Id == video.AnalysisId, ct);
                if (session is not null)
                {
                    session.Status = SessionStatus.Done;
                    session.UpdatedAt = DateTime.UtcNow;
                }
            }

            await db.SaveChangesAsync(ct);
        }
        catch (Exception exc)
        {
            using IServiceScope scope = _scopeFactory.CreateScope();
            AppDbContext db = NewDb(scope);
            VisionJob? job = await db.VisionJobs.FirstOrDefaultAsync(j => j.Id == jobId, ct);
            if (job is not null)
            {
                job.Status = VisionJobStatus.Failed;
                job.Error = $"{exc.GetType().Name}: {exc.Message}";
                job.FinishedAt = DateTime.UtcNow;
                await db.SaveChangesAsync(ct);
            }
        }
    }

    private async Task SaveProgressAsync(int jobId, double progress)
    {
        try
        {
            using IServiceScope scope = _scopeFactory.CreateScope();
            AppDbContext db = NewDb(scope);
            VisionJob? job = await db.VisionJobs.FirstOrDefaultAsync(j => j.Id == jobId);
            if (job is not null && job.Status == VisionJobStatus.Running)
            {
                job.Progress = progress;
                await db.SaveChangesAsync();
            }
        }
        catch { /* progress write is best-effort */ }
    }
}
