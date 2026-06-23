namespace PitchWise.Api.Config;

// Odpowiednik worker/app/config.py. Wczytywane z ENV (te same nazwy co dziś) oraz
// appsettings.json. Domyślne wartości zgodne z Pythonem.
public class AppSettings
{
    public string StorageDir { get; set; } = "./storage";

    // .NET łączy się do Postgresa standardowym connection stringiem Npgsql.
    // (Worker pythonowy używa postgresql+asyncpg://... do tej samej bazy.)
    public string DatabaseConnection { get; set; } =
        "Host=localhost;Port=5432;Database=pitchwise;Username=pitchwise;Password=pitchwise";

    public string RedisUrl { get; set; } = "localhost:6379";

    public string LlmProvider { get; set; } = "openai";
    public string LlmBaseUrl { get; set; } = "https://api.openai.com/v1";
    public string LlmApiKey { get; set; } = "";
    public string LlmModel { get; set; } = "gpt-4o-mini";

    public string WebOrigin { get; set; } = "http://localhost:3000";
    public string WebOriginAlt { get; set; } = "http://localhost:3001";

    // Nazwa listy Redis, z której zdejmuje pythonowy worker (kontrakt z worker.py).
    public string VisionQueue { get; set; } = "vision_jobs";

    public string UploadsDir => Path.Combine(StorageDir, "uploads");
    public string ClipsDir => Path.Combine(StorageDir, "clips");

    public void EnsureDirs()
    {
        Directory.CreateDirectory(StorageDir);
        Directory.CreateDirectory(UploadsDir);
        Directory.CreateDirectory(ClipsDir);
    }
}
