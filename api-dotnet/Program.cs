using Microsoft.EntityFrameworkCore;
using PitchWise.Api.Config;
using PitchWise.Api.Data;
using PitchWise.Api.Dtos;
using PitchWise.Api.Services;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);

// --- Configuration: appsettings.json + ENV (same names as before, to keep deploys unchanged) ---
var settings = new AppSettings();
builder.Configuration.GetSection("App").Bind(settings);
// ENV overrides (1:1 with worker/app/config.py).
settings.StorageDir = Environment.GetEnvironmentVariable("STORAGE_DIR") ?? settings.StorageDir;
settings.DatabaseConnection = Environment.GetEnvironmentVariable("DATABASE_CONNECTION") ?? settings.DatabaseConnection;
settings.RedisUrl = Environment.GetEnvironmentVariable("REDIS_URL") ?? settings.RedisUrl;
settings.LlmProvider = Environment.GetEnvironmentVariable("LLM_PROVIDER") ?? settings.LlmProvider;
settings.LlmBaseUrl = Environment.GetEnvironmentVariable("LLM_BASE_URL") ?? settings.LlmBaseUrl;
settings.LlmApiKey = Environment.GetEnvironmentVariable("LLM_API_KEY") ?? settings.LlmApiKey;
settings.LlmModel = Environment.GetEnvironmentVariable("LLM_MODEL") ?? settings.LlmModel;
settings.WebOrigin = Environment.GetEnvironmentVariable("WEB_ORIGIN") ?? settings.WebOrigin;
settings.WebOriginAlt = Environment.GetEnvironmentVariable("WEB_ORIGIN_ALT") ?? settings.WebOriginAlt;
settings.VisionQueue = Environment.GetEnvironmentVariable("VISION_QUEUE") ?? settings.VisionQueue;
settings.HighlightQueue = Environment.GetEnvironmentVariable("HIGHLIGHT_QUEUE") ?? settings.HighlightQueue;
settings.HlsBaseUrl = Environment.GetEnvironmentVariable("HLS_BASE_URL") ?? settings.HlsBaseUrl;
settings.HlsSigningSecret = Environment.GetEnvironmentVariable("HLS_SIGNING_SECRET") ?? settings.HlsSigningSecret;
if (int.TryParse(Environment.GetEnvironmentVariable("HLS_LINK_TTL_SECONDS"), out var hlsTtl))
    settings.HlsLinkTtlSeconds = hlsTtl;
settings.LiveWorkerUrl = Environment.GetEnvironmentVariable("LIVE_WORKER_URL") ?? settings.LiveWorkerUrl;
settings.EnsureDirs();
builder.Services.AddSingleton(settings);

// --- DB ---
builder.Services.AddDbContext<AppDbContext>(opt => opt.UseNpgsql(settings.DatabaseConnection));

// --- Redis ---
builder.Services.AddSingleton<IConnectionMultiplexer>(
    _ => ConnectionMultiplexer.Connect(RedisConfig(settings.RedisUrl)));
builder.Services.AddSingleton<VisionQueue>();
builder.Services.AddSingleton<HighlightQueue>();
builder.Services.AddSingleton<HlsSigner>();

// --- LLM ---
builder.Services.AddHttpClient<LlmClient>(c => c.Timeout = TimeSpan.FromSeconds(120));

// --- Large video file uploads (FastAPI had no limit; we lift it here too) ---
builder.Services.Configure<Microsoft.AspNetCore.Http.Features.FormOptions>(o =>
{
    o.MultipartBodyLengthLimit = long.MaxValue;
    o.ValueLengthLimit = int.MaxValue;
});
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = null);

// --- JSON: snake_case + enums with the same values as in Python ---
builder.Services.AddControllers().AddJsonOptions(o =>
{
    o.JsonSerializerOptions.PropertyNamingPolicy = System.Text.Json.JsonNamingPolicy.SnakeCaseLower;
    o.JsonSerializerOptions.Converters.Add(new EventTypeJsonConverter());
    o.JsonSerializerOptions.Converters.Add(new EventSourceJsonConverter());
    o.JsonSerializerOptions.Converters.Add(new SessionStatusJsonConverter());
    o.JsonSerializerOptions.Converters.Add(new VisionJobStatusJsonConverter());
    o.JsonSerializerOptions.Converters.Add(new HighlightStatusJsonConverter());
});

// --- CORS (1:1 with main.py) ---
builder.Services.AddCors(o => o.AddDefaultPolicy(p => p
    .WithOrigins(settings.WebOrigin, settings.WebOriginAlt)
    .AllowCredentials()
    .AllowAnyMethod()
    .AllowAnyHeader()));

var app = builder.Build();

// .NET owns the schema (source of truth); the Python worker only reads/writes.
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.EnsureCreated();
    // EnsureCreated only runs when the DB is brand-new; for tables added after initial
    // deployment we apply a manual CREATE TABLE IF NOT EXISTS so existing deployments
    // get the new table without a full migration framework.
    db.Database.ExecuteSqlRaw("""
        CREATE TABLE IF NOT EXISTS livesession (
            id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'idle',
            ws_url TEXT NOT NULL DEFAULT '',
            hls_url TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            stopped_at TIMESTAMPTZ NULL
        )
    """);
    // Annotated (boxes burned-in) playback: added after initial deployment, so ALTER the
    // existing table (EnsureCreated only builds brand-new DBs). See
    // Migrations/003_annotated_video.sql.
    db.Database.ExecuteSqlRaw(
        "ALTER TABLE video ADD COLUMN IF NOT EXISTS annotated_filename TEXT NULL;");
    // Whole-match aggregate stats (possession, passing). Added after initial deployment; one row
    // per video (unique video_id). See Migrations/004_match_stats.sql.
    db.Database.ExecuteSqlRaw("""
        CREATE TABLE IF NOT EXISTS matchstats (
            id SERIAL PRIMARY KEY,
            video_id INTEGER NOT NULL UNIQUE,
            analysis_id INTEGER NOT NULL,
            possession_pct_a DOUBLE PRECISION NOT NULL DEFAULT 0,
            possession_pct_b DOUBLE PRECISION NOT NULL DEFAULT 0,
            controlled_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
            loose_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
            passes_a INTEGER NOT NULL DEFAULT 0,
            passes_b INTEGER NOT NULL DEFAULT 0,
            turnovers_a INTEGER NOT NULL DEFAULT 0,
            turnovers_b INTEGER NOT NULL DEFAULT 0,
            pass_accuracy_pct_a DOUBLE PRECISION NOT NULL DEFAULT 0,
            pass_accuracy_pct_b DOUBLE PRECISION NOT NULL DEFAULT 0,
            time_on_pitch_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """);
}

app.UseCors();
app.MapGet("/health", () => Results.Ok(new { status = "ok" }));
app.MapControllers();
app.Run();


static ConfigurationOptions RedisConfig(string url)
{
    // Accept both "host:port" and "redis://host:port".
    var trimmed = url.Replace("redis://", "").Replace("rediss://", "");
    return ConfigurationOptions.Parse(trimmed);
}
