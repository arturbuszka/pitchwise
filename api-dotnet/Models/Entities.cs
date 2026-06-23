namespace PitchWise.Api.Models;

// Encje EF Core odwzorowane 1:1 z worker/app/models.py (SQLModel).
// Nazwy tabel/kolumn ustawiane w AppDbContext (snake_case) — wspólny schemat
// z pythonowym workerem jest formalnym kontraktem między .NET a Pythonem.

public class AnalysisSession
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? Subtitle { get; set; }
    public string Sport { get; set; } = "football";
    public SessionStatus Status { get; set; } = SessionStatus.Draft;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}

public class Video
{
    public int Id { get; set; }
    public int AnalysisId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Filename { get; set; } = string.Empty;
    public double? DurationSeconds { get; set; }
    public double? Fps { get; set; }
    public int Order { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

public class VisionJob
{
    public int Id { get; set; }
    public int VideoId { get; set; }
    public VisionJobStatus Status { get; set; } = VisionJobStatus.Pending;
    public double Progress { get; set; }
    public string? Error { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? FinishedAt { get; set; }
}

public class Event
{
    public int Id { get; set; }
    public int AnalysisId { get; set; }
    public int? VideoId { get; set; }
    public EventType Type { get; set; }
    public EventSource Source { get; set; }
    public double TimestampSeconds { get; set; }
    public double? Confidence { get; set; }
    public string? Label { get; set; }
    public string? Note { get; set; }
    public int? PlayerNumber { get; set; }
    public string? PlayerName { get; set; }
    public int? AssistNumber { get; set; }
    public string? AssistName { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}

public class Clip
{
    public int Id { get; set; }
    public int EventId { get; set; }
    public int VideoId { get; set; }
    public string Filename { get; set; } = string.Empty;
    public double StartSeconds { get; set; }
    public double EndSeconds { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
