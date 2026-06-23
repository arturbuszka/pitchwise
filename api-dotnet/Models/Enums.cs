namespace PitchWise.Api.Models;

// Enumy odwzorowane 1:1 z worker/app/models.py (str, Enum). W DB zapisywane jako
// string (wartości dokładnie jak w Pythonie), bo na tym schemacie operuje też
// pythonowy worker.

public enum SessionStatus
{
    Draft,
    Processing,
    Done,
}

public enum VisionJobStatus
{
    Pending,
    Running,
    Done,
    Failed,
}

public enum EventType
{
    Goal,
    Shot,
    WaywardPass,    // wayward_pass
    Foul,
    FreeKick,       // free_kick
    Offside,
    Substitution,
    SetPiece,       // set_piece
    Manual,
}

public enum EventSource
{
    Auto,
    Manual,
}
