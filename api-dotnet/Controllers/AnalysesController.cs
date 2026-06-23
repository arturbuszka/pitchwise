using System.Text;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using PitchWise.Api.Config;
using PitchWise.Api.Data;
using PitchWise.Api.Dtos;
using PitchWise.Api.Models;
using PitchWise.Api.Services;

namespace PitchWise.Api.Controllers;

// Odpowiednik worker/app/routers/analyses.py: CRUD sesji, zdarzenia, chat (SSE).
[ApiController]
[Route("api/analyses")]
public class AnalysesController : ControllerBase
{
    private const string ChatSystem =
        "Jesteś asystentem analitycznym dla sztabu trenerskiego. " +
        "Odpowiadasz zwięźle i konkretnie po polsku, opierając się na dostarczonym " +
        "kontekście sesji analitycznej (wykryte i otagowane zdarzenia). " +
        "Gdy danych brakuje, mów to wprost.";

    private readonly AppDbContext _db;
    private readonly AppSettings _settings;
    private readonly LlmClient _llm;

    public AnalysesController(AppDbContext db, AppSettings settings, LlmClient llm)
    {
        _db = db;
        _settings = settings;
        _llm = llm;
    }

    // ---- Analyses CRUD ----

    [HttpGet]
    public async Task<List<AnalysisListItem>> ListAnalyses([FromQuery] string? sport, [FromQuery] string? search)
    {
        var q = _db.AnalysisSessions.AsQueryable().OrderByDescending(a => a.UpdatedAt);
        if (!string.IsNullOrEmpty(sport))
            q = (IOrderedQueryable<AnalysisSession>)q.Where(a => a.Sport == sport);
        if (!string.IsNullOrEmpty(search))
            q = (IOrderedQueryable<AnalysisSession>)q.Where(a => EF.Functions.ILike(a.Name, $"%{search}%"));

        var rows = await q.ToListAsync();
        var result = new List<AnalysisListItem>();
        foreach (var row in rows)
        {
            var count = await _db.Videos.CountAsync(v => v.AnalysisId == row.Id);
            result.Add(new AnalysisListItem(
                row.Id, row.Name, row.Subtitle, row.Sport, row.Status,
                row.CreatedAt, row.UpdatedAt, count));
        }
        return result;
    }

    [HttpPost]
    public async Task<AnalysisDetail> CreateAnalysis([FromBody] AnalysisCreate payload)
    {
        var obj = new AnalysisSession
        {
            Name = payload.Name,
            Subtitle = payload.Subtitle,
            Sport = payload.Sport,
        };
        _db.AnalysisSessions.Add(obj);
        await _db.SaveChangesAsync();
        return new AnalysisDetail(
            obj.Id, obj.Name, obj.Subtitle, obj.Sport, obj.Status,
            obj.CreatedAt, obj.UpdatedAt, new List<VideoOut>());
    }

    [HttpGet("{analysisId:int}")]
    public async Task<ActionResult<AnalysisDetail>> GetAnalysis(int analysisId)
    {
        var obj = await _db.AnalysisSessions.FindAsync(analysisId);
        if (obj is null) return NotFound(new { detail = "Analiza nie znaleziona" });

        var videos = await _db.Videos
            .Where(v => v.AnalysisId == analysisId)
            .OrderBy(v => v.Order).ThenBy(v => v.CreatedAt)
            .ToListAsync();

        return new AnalysisDetail(
            obj.Id, obj.Name, obj.Subtitle, obj.Sport, obj.Status,
            obj.CreatedAt, obj.UpdatedAt,
            videos.Select(v => new VideoOut(v.Id, v.AnalysisId, v.Name, v.DurationSeconds, v.Fps, v.Order)).ToList());
    }

    // ---- Events ----

    [HttpGet("{analysisId:int}/events")]
    public async Task<ActionResult<List<EventOut>>> ListEvents(int analysisId, [FromQuery] EventType? type)
    {
        if (!await _db.AnalysisSessions.AnyAsync(a => a.Id == analysisId))
            return NotFound(new { detail = "Analiza nie znaleziona" });

        var q = _db.Events.Where(e => e.AnalysisId == analysisId);
        if (type is not null)
            q = q.Where(e => e.Type == type);
        var events = await q.OrderBy(e => e.TimestampSeconds).ToListAsync();

        var result = new List<EventOut>();
        foreach (var e in events)
            result.Add(await EventToOut(e));
        return result;
    }

    [HttpPost("{analysisId:int}/events")]
    public async Task<ActionResult<EventOut>> CreateEvent(int analysisId, [FromBody] EventCreate payload)
    {
        var session = await _db.AnalysisSessions.FindAsync(analysisId);
        if (session is null) return NotFound(new { detail = "Analiza nie znaleziona" });

        if (payload.VideoId is not null)
        {
            var video = await _db.Videos.FindAsync(payload.VideoId.Value);
            if (video is null || video.AnalysisId != analysisId)
                return BadRequest(new { detail = "video_id nie należy do tej analizy" });
        }

        var ev = new Event
        {
            AnalysisId = analysisId,
            VideoId = payload.VideoId,
            Type = payload.Type,
            Source = EventSource.Manual,
            TimestampSeconds = payload.TimestampSeconds,
            Label = payload.Label,
            Note = payload.Note,
            PlayerNumber = payload.PlayerNumber,
            PlayerName = payload.PlayerName,
            AssistNumber = payload.AssistNumber,
            AssistName = payload.AssistName,
        };
        _db.Events.Add(ev);
        session.UpdatedAt = DateTime.UtcNow;
        await _db.SaveChangesAsync();
        return await EventToOut(ev);
    }

    [HttpDelete("{analysisId:int}/events/{eventId:int}")]
    public async Task<ActionResult> DeleteEvent(int analysisId, int eventId)
    {
        var ev = await _db.Events.FindAsync(eventId);
        if (ev is null || ev.AnalysisId != analysisId)
            return NotFound(new { detail = "Event nie znaleziony" });

        var clips = await _db.Clips.Where(c => c.EventId == eventId).ToListAsync();
        foreach (var clip in clips)
        {
            var path = Path.Combine(_settings.ClipsDir, clip.Filename);
            if (System.IO.File.Exists(path)) System.IO.File.Delete(path);
            _db.Clips.Remove(clip);
        }
        _db.Events.Remove(ev);
        await _db.SaveChangesAsync();
        return Ok(new { ok = true });
    }

    // ---- Chat (SSE streaming) ----

    [HttpPost("{analysisId:int}/chat")]
    public async Task Chat(int analysisId, [FromBody] ChatRequest req)
    {
        var session = await _db.AnalysisSessions.FindAsync(analysisId);
        if (session is null)
        {
            Response.StatusCode = 404;
            await Response.WriteAsJsonAsync(new { detail = "Analiza nie znaleziona" });
            return;
        }

        var context = await BuildAnalysisContext(analysisId);
        var system = string.IsNullOrEmpty(context)
            ? ChatSystem
            : $"{ChatSystem}\n\nKontekst analizy:\n{context}";

        var messages = req.Messages.Select(m => (m.Role, m.Content)).ToList();

        Response.ContentType = "text/event-stream";
        var ct = HttpContext.RequestAborted;

        try
        {
            await foreach (var delta in _llm.StreamChatAsync(messages, system, ct))
            {
                await Response.WriteAsync($"data: {delta}\n\n", ct);
                await Response.Body.FlushAsync(ct);
            }
        }
        catch (Exception exc)
        {
            await Response.WriteAsync($"data: [błąd LLM: {exc.GetType().Name}]\n\n", ct);
        }
        await Response.WriteAsync("data: [DONE]\n\n", ct);
        await Response.Body.FlushAsync(ct);
    }

    // ---- Helpers ----

    private async Task<EventOut> EventToOut(Event ev)
    {
        ClipOut? clip = null;
        var clipRow = await _db.Clips.FirstOrDefaultAsync(c => c.EventId == ev.Id);
        if (clipRow is not null)
            clip = new ClipOut(clipRow.Id, clipRow.EventId, clipRow.VideoId,
                clipRow.Filename, clipRow.StartSeconds, clipRow.EndSeconds);

        return new EventOut(
            ev.Id, ev.AnalysisId, ev.VideoId, ev.Type, ev.Source,
            ev.TimestampSeconds, ev.Confidence, ev.Label, ev.Note,
            ev.PlayerNumber, ev.PlayerName, ev.AssistNumber, ev.AssistName, clip);
    }

    private async Task<string> BuildAnalysisContext(int analysisId)
    {
        var session = await _db.AnalysisSessions.FindAsync(analysisId);
        if (session is null) return "";

        var events = await _db.Events
            .Where(e => e.AnalysisId == analysisId)
            .OrderBy(e => e.TimestampSeconds)
            .ToListAsync();

        var lines = new List<string>();
        var head = $"Analiza: {session.Name} ({session.Sport}).";
        if (!string.IsNullOrEmpty(session.Subtitle)) head += $" {session.Subtitle}";
        lines.Add(head);

        if (events.Count > 0)
        {
            lines.Add($"Zdarzenia ({events.Count}):");
            foreach (var e in events)
            {
                var total = (int)e.TimestampSeconds;
                var mm = total / 60;
                var ss = total % 60;
                var conf = e.Confidence is not null ? $", pewność {e.Confidence.Value:P0}" : "";
                var player = "";
                if (!string.IsNullOrEmpty(e.PlayerName))
                    player = e.PlayerNumber is not null ? $" #{e.PlayerNumber} {e.PlayerName}" : $" {e.PlayerName}";
                var assist = "";
                if (!string.IsNullOrEmpty(e.AssistName))
                    assist = e.AssistNumber is not null ? $" (asysta #{e.AssistNumber} {e.AssistName})" : $" (asysta {e.AssistName})";
                var note = !string.IsNullOrEmpty(e.Note) ? $" — {e.Note}" : "";
                lines.Add($"- {mm:D2}:{ss:D2} {EventTypeMap.ToDb(e.Type)} ({(e.Source == EventSource.Auto ? "auto" : "manual")}{conf}){player}{assist}{note}".TrimEnd());
            }
        }
        else
        {
            lines.Add("Brak wykrytych/otagowanych zdarzeń.");
        }
        return string.Join("\n", lines);
    }
}
