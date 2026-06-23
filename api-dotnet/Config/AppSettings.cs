namespace PitchWise.Api.Config;

// Mirror of worker/app/config.py. Loaded from ENV (same names as before) and
// appsettings.json. Defaults match the Python side.
public class AppSettings
{
    public string StorageDir { get; set; } = "./storage";

    // .NET connects to Postgres with a standard Npgsql connection string.
    // (The Python worker uses postgresql+asyncpg://... against the same database.)
    public string DatabaseConnection { get; set; } =
        "Host=localhost;Port=5432;Database=pitchwise;Username=pitchwise;Password=pitchwise";

    public string RedisUrl { get; set; } = "localhost:6379";

    public string LlmProvider { get; set; } = "openai";
    public string LlmBaseUrl { get; set; } = "https://api.openai.com/v1";
    public string LlmApiKey { get; set; } = "";
    public string LlmModel { get; set; } = "gpt-4o-mini";

    public string WebOrigin { get; set; } = "http://localhost:3000";
    public string WebOriginAlt { get; set; } = "http://localhost:3001";

    // Name of the Redis list the Python worker pops from (contract with worker.py).
    public string VisionQueue { get; set; } = "vision_jobs";

    // Name of the Redis list the highlight worker loop pops from.
    public string HighlightQueue { get; set; } = "highlight_jobs";

    // How long a generated share link stays valid.
    public int ShareLinkTtlHours { get; set; } = 24;

    public string UploadsDir => Path.Combine(StorageDir, "uploads");
    public string ClipsDir => Path.Combine(StorageDir, "clips");

    public void EnsureDirs()
    {
        Directory.CreateDirectory(StorageDir);
        Directory.CreateDirectory(UploadsDir);
        Directory.CreateDirectory(ClipsDir);
    }
}
