using PitchWise.Api.Models;

namespace PitchWise.Api.Dtos;

// DTO odwzorowane 1:1 z worker/app/schemas.py. Nazwy pól w JSON ustawione globalnie na
// snake_case (JsonNamingPolicy w Program.cs), więc property w PascalCase mapują się
// na video_count, timestamp_seconds itd. — tak jak oczekuje istniejący frontend.

public record AnalysisCreate(string Name, string? Subtitle = null, string Sport = "football");

public record VideoOut(
    int Id,
    int AnalysisId,
    string Name,
    double? DurationSeconds,
    double? Fps,
    int Order);

public record AnalysisListItem(
    int Id,
    string Name,
    string? Subtitle,
    string Sport,
    SessionStatus Status,
    DateTime CreatedAt,
    DateTime UpdatedAt,
    int VideoCount);

public record AnalysisDetail(
    int Id,
    string Name,
    string? Subtitle,
    string Sport,
    SessionStatus Status,
    DateTime CreatedAt,
    DateTime UpdatedAt,
    List<VideoOut> Videos);

public record VisionJobOut(
    int Id,
    int VideoId,
    VisionJobStatus Status,
    double Progress,
    string? Error,
    DateTime CreatedAt,
    DateTime? FinishedAt);

public record ClipOut(
    int Id,
    int EventId,
    int VideoId,
    string Filename,
    double StartSeconds,
    double EndSeconds);

public record EventOut(
    int Id,
    int AnalysisId,
    int? VideoId,
    EventType Type,
    EventSource Source,
    double TimestampSeconds,
    double? Confidence,
    string? Label,
    string? Note,
    int? PlayerNumber,
    string? PlayerName,
    int? AssistNumber,
    string? AssistName,
    ClipOut? Clip = null);

public record EventCreate(
    double TimestampSeconds,
    EventType Type = EventType.Manual,
    string? Label = null,
    string? Note = null,
    int? VideoId = null,
    int? PlayerNumber = null,
    string? PlayerName = null,
    int? AssistNumber = null,
    string? AssistName = null);

public record EventTypeConfigOut(
    string Key,
    string Label,
    string Icon,
    string Color,
    string Bg);

public record ChatMessage(string Role, string Content);

public record ChatRequest(List<ChatMessage> Messages, int? AnalysisId = null);
