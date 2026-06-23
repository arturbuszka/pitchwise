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
settings.EnsureDirs();
builder.Services.AddSingleton(settings);

// --- DB ---
builder.Services.AddDbContext<AppDbContext>(opt => opt.UseNpgsql(settings.DatabaseConnection));

// --- Redis ---
builder.Services.AddSingleton<IConnectionMultiplexer>(
    _ => ConnectionMultiplexer.Connect(RedisConfig(settings.RedisUrl)));
builder.Services.AddSingleton<VisionQueue>();
builder.Services.AddSingleton<HighlightQueue>();

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
}

app.UseCors();
app.MapControllers();
app.Run();


static ConfigurationOptions RedisConfig(string url)
{
    // Accept both "host:port" and "redis://host:port".
    var trimmed = url.Replace("redis://", "").Replace("rediss://", "");
    return ConfigurationOptions.Parse(trimmed);
}
