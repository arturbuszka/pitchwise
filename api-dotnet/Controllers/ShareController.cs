using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.StaticFiles;
using Microsoft.EntityFrameworkCore;
using PitchWise.Api.Config;
using PitchWise.Api.Data;
using PitchWise.Api.Dtos;
using PitchWise.Api.Models;

namespace PitchWise.Api.Controllers;

// Public, unauthenticated access to a highlight via a share token. No analysis id
// is exposed. Expired tokens return 410 Gone. The /stream endpoint serves the file
// with HTTP Range so the browser streams it (no download) inside a <video> tag.
[ApiController]
[Route("api/share")]
public class ShareController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly AppSettings _settings;

    public ShareController(AppDbContext db, AppSettings settings)
    {
        _db = db;
        _settings = settings;
    }

    [HttpGet("{token}")]
    public async Task<ActionResult<SharePublicOut>> Meta(string token)
    {
        var (highlight, error) = await Resolve(token);
        if (error is not null) return error;
        return new SharePublicOut(highlight!.Name, highlight.Status, highlight.ShareExpiresAt!.Value);
    }

    [HttpGet("{token}/stream")]
    public async Task<IActionResult> Stream(string token)
    {
        var (highlight, error) = await Resolve(token);
        if (error is not null) return error;

        if (string.IsNullOrEmpty(highlight!.Filename))
            return NotFound(new { detail = "Highlight not ready" });

        var path = Path.Combine(_settings.ClipsDir, highlight.Filename);
        if (!System.IO.File.Exists(path)) return NotFound(new { detail = "Highlight file does not exist" });

        return PhysicalFile(Path.GetFullPath(path), ContentTypeFor(path), enableRangeProcessing: true);
    }

    // Looks up the highlight by token, validating existence and expiry.
    // Returns (highlight, null) on success or (null, errorResult) otherwise.
    private async Task<(Highlight?, ActionResult?)> Resolve(string token)
    {
        var highlight = await _db.Highlights.FirstOrDefaultAsync(h => h.ShareToken == token);
        if (highlight is null || highlight.ShareExpiresAt is null)
            return (null, NotFound(new { detail = "Share link not found" }));
        if (highlight.ShareExpiresAt.Value < DateTime.UtcNow)
            return (null, StatusCode(StatusCodes.Status410Gone, new { detail = "Share link expired" }));
        return (highlight, null);
    }

    private static string ContentTypeFor(string path)
    {
        var provider = new FileExtensionContentTypeProvider();
        return provider.TryGetContentType(path, out var ct) ? ct : "application/octet-stream";
    }
}
