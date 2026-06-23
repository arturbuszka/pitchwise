namespace PitchWise.Api.Models;

// Enums mirrored 1:1 from worker/app/models.py (str, Enum). Stored in the DB as
// strings (values exactly as in Python), because the Python worker operates on the
// same schema.

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

public enum HighlightStatus
{
    Pending,
    Running,
    Done,
    Failed,
}
