using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.StaticFiles;
using Microsoft.EntityFrameworkCore;
using PitchWise.Api.Config;
using PitchWise.Api.Data;
using PitchWise.Api.Dtos;
using PitchWise.Api.Models;
using PitchWise.Api.Services;

namespace PitchWise.Api.Controllers;

// Odpowiednik worker/app/routers/videos.py: upload, streaming (Range), analyze→enqueue, status.
[ApiController]
[Route("api/analyses")]
public class VideosController : ControllerBase
{
    private static readonly HashSet<string> AllowedExt = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4", ".mov", ".mkv", ".avi",
    };

    private readonly AppDbContext _db;
    private readonly AppSettings _settings;
    private readonly VisionQueue _queue;

    public VideosController(AppDbContext db, AppSettings settings, VisionQueue queue)
    {
        _db = db;
        _settings = settings;
        _queue = queue;
    }

    [HttpGet("{analysisId:int}/videos")]
    public async Task<ActionResult<List<VideoOut>>> ListVideos(int analysisId)
    {
        if (!await _db.AnalysisSessions.AnyAsync(a => a.Id == analysisId))
            return NotFound(new { detail = "Analiza nie znaleziona" });

        var rows = await _db.Videos
            .Where(v => v.AnalysisId == analysisId)
            .OrderBy(v => v.Order).ThenBy(v => v.CreatedAt)
            .ToListAsync();
        return rows.Select(v => new VideoOut(v.Id, v.AnalysisId, v.Name, v.DurationSeconds, v.Fps, v.Order)).ToList();
    }

    [HttpPost("{analysisId:int}/videos")]
    public async Task<ActionResult<VideoOut>> UploadVideo(int analysisId, [FromForm] string name, IFormFile file)
    {
        var session = await _db.AnalysisSessions.FindAsync(analysisId);
        if (session is null) return NotFound(new { detail = "Analiza nie znaleziona" });

        var ext = Path.GetExtension(file.FileName ?? "").ToLowerInvariant();
        if (!AllowedExt.Contains(ext))
            return BadRequest(new { detail = $"Nieobsługiwany format: {ext}. Dozwolone: {string.Join(", ", AllowedExt.OrderBy(x => x))}" });

        var storedName = $"{Guid.NewGuid():N}{ext}";
        var dest = Path.Combine(_settings.UploadsDir, storedName);
        await using (var outStream = System.IO.File.Create(dest))
            await file.CopyToAsync(outStream);

        var order = await _db.Videos.CountAsync(v => v.AnalysisId == analysisId);

        var video = new Video
        {
            AnalysisId = analysisId,
            Name = name,
            Filename = storedName,
            Order = order,
        };
        _db.Videos.Add(video);
        session.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();

        return new VideoOut(video.Id, video.AnalysisId, video.Name, video.DurationSeconds, video.Fps, video.Order);
    }

    [HttpGet("{analysisId:int}/videos/{videoId:int}/stream")]
    public async Task<IActionResult> StreamVideo(int analysisId, int videoId)
    {
        var video = await GetVideoOr404(analysisId, videoId);
        if (video is null) return NotFound(new { detail = "Wideo nie znalezione" });

        var path = Path.Combine(_settings.UploadsDir, video.Filename);
        if (!System.IO.File.Exists(path)) return NotFound(new { detail = "Plik wideo nie istnieje" });

        // enableRangeProcessing => przewijanie wideo w przeglądarce (HTTP Range).
        return PhysicalFile(Path.GetFullPath(path), ContentTypeFor(path), enableRangeProcessing: true);
    }

    // ---- Pipeline YOLO ----

    [HttpPost("{analysisId:int}/videos/{videoId:int}/analyze")]
    public async Task<ActionResult<VisionJobOut>> StartAnalysis(int analysisId, int videoId)
    {
        var video = await GetVideoOr404(analysisId, videoId);
        if (video is null) return NotFound(new { detail = "Wideo nie znalezione" });

        // nie startuj drugiego joba, jeśli jeden jest aktywny
        var existing = await _db.VisionJobs
            .Where(j => j.VideoId == videoId &&
                        (j.Status == VisionJobStatus.Pending || j.Status == VisionJobStatus.Running))
            .FirstOrDefaultAsync();
        if (existing is not null)
            return JobToOut(existing);

        var job = new VisionJob { VideoId = videoId };
        _db.VisionJobs.Add(job);

        var session = await _db.AnalysisSessions.FindAsync(analysisId);
        if (session is not null)
        {
            session.Status = SessionStatus.Processing;
            session.UpdatedAt = DateTime.UtcNow;
        }
        await _db.SaveChangesAsync();

        await _queue.EnqueueAsync(job.Id);

        return JobToOut(job);
    }

    [HttpGet("{analysisId:int}/videos/{videoId:int}/status")]
    public async Task<ActionResult<VisionJobOut?>> GetStatus(int analysisId, int videoId)
    {
        var video = await GetVideoOr404(analysisId, videoId);
        if (video is null) return NotFound(new { detail = "Wideo nie znalezione" });

        var job = await _db.VisionJobs
            .Where(j => j.VideoId == videoId)
            .OrderByDescending(j => j.CreatedAt)
            .FirstOrDefaultAsync();
        if (job is null) return Ok((VisionJobOut?)null);
        return JobToOut(job);
    }

    // ---- Klipy ----

    [HttpGet("{analysisId:int}/clips/{clipId:int}/stream")]
    public async Task<IActionResult> StreamClip(int analysisId, int clipId)
    {
        var clip = await _db.Clips.FindAsync(clipId);
        if (clip is null) return NotFound(new { detail = "Klip nie znaleziony" });

        var video = await _db.Videos.FindAsync(clip.VideoId);
        if (video is null || video.AnalysisId != analysisId)
            return NotFound(new { detail = "Klip nie znaleziony" });

        var path = Path.Combine(_settings.ClipsDir, clip.Filename);
        if (!System.IO.File.Exists(path)) return NotFound(new { detail = "Plik klipu nie istnieje" });

        return PhysicalFile(Path.GetFullPath(path), ContentTypeFor(path), enableRangeProcessing: true);
    }

    // ---- Helpers ----

    private async Task<Video?> GetVideoOr404(int analysisId, int videoId)
    {
        var video = await _db.Videos.FindAsync(videoId);
        if (video is null || video.AnalysisId != analysisId) return null;
        return video;
    }

    private static VisionJobOut JobToOut(VisionJob j) =>
        new(j.Id, j.VideoId, j.Status, j.Progress, j.Error, j.CreatedAt, j.FinishedAt);

    private static string ContentTypeFor(string path)
    {
        var provider = new FileExtensionContentTypeProvider();
        return provider.TryGetContentType(path, out var ct) ? ct : "application/octet-stream";
    }
}
