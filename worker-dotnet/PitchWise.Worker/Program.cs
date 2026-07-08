using Microsoft.EntityFrameworkCore;
using PitchWise.Api.Config;
using PitchWise.Api.Data;
using PitchWise.Vision;
using PitchWise.Worker;
using StackExchange.Redis;

var builder = Host.CreateApplicationBuilder(args);

// --- AppSettings (DB/Redis/dirs/queues): same ENV names as the API, shared schema. ---
var settings = new AppSettings();
builder.Configuration.GetSection("App").Bind(settings);
settings.StorageDir = Environment.GetEnvironmentVariable("STORAGE_DIR") ?? settings.StorageDir;
settings.DatabaseConnection = Environment.GetEnvironmentVariable("DATABASE_CONNECTION") ?? settings.DatabaseConnection;
settings.RedisUrl = Environment.GetEnvironmentVariable("REDIS_URL") ?? settings.RedisUrl;
settings.VisionQueue = Environment.GetEnvironmentVariable("VISION_QUEUE") ?? settings.VisionQueue;
settings.HighlightQueue = Environment.GetEnvironmentVariable("HIGHLIGHT_QUEUE") ?? settings.HighlightQueue;
settings.EnsureDirs();
builder.Services.AddSingleton(settings);

// --- WorkerSettings (vision knobs): appsettings "Worker" + ENV. ---
var worker = new WorkerSettings();
builder.Configuration.GetSection("Worker").Bind(worker);
worker.YoloModelPath = Environment.GetEnvironmentVariable("YOLO_MODEL_PATH") ?? worker.YoloModelPath;
worker.YoloNamesPath = Environment.GetEnvironmentVariable("YOLO_NAMES_PATH") ?? worker.YoloNamesPath;
if (int.TryParse(Environment.GetEnvironmentVariable("FRAME_STRIDE"), out int fs)) worker.FrameStride = fs;
if (int.TryParse(Environment.GetEnvironmentVariable("LIVE_IMGSZ"), out int isz)) worker.Imgsz = isz;
worker.GenerateClips = (Environment.GetEnvironmentVariable("GENERATE_CLIPS") ?? "") is "1" or "true"
    ? true : worker.GenerateClips;
worker.FfmpegPath = Environment.GetEnvironmentVariable("FFMPEG_PATH") ?? worker.FfmpegPath;
builder.Services.AddSingleton(worker);

// Point the shared ffmpeg wrappers at the configured binaries.
FfmpegTools.FfmpegPath = worker.FfmpegPath;
FfmpegTools.FfprobePath = worker.FfprobePath;

// --- Model class names (loaded once, shared). ---
IReadOnlyDictionary<int, string> classNames =
    ModelClassNames.Load(worker.YoloModelPath, worker.YoloNamesPath);
builder.Services.AddSingleton(classNames);

// --- DB (scoped, short-lived per job phase). ---
builder.Services.AddDbContext<AppDbContext>(
    opt => opt.UseNpgsql(settings.DatabaseConnection));

// --- Redis (accept "host:port" and "redis://host:port"). ---
builder.Services.AddSingleton<IConnectionMultiplexer>(
    _ => ConnectionMultiplexer.Connect(RedisConfig(settings.RedisUrl)));

// --- Runners + the BRPOP background service. ---
builder.Services.AddSingleton<VisionRunner>();
builder.Services.AddSingleton<HighlightRunner>();
builder.Services.AddHostedService<QueueWorker>();

IHost host = builder.Build();
host.Run();

static ConfigurationOptions RedisConfig(string url)
{
    string trimmed = url.Replace("redis://", "").Replace("rediss://", "");
    ConfigurationOptions cfg = ConfigurationOptions.Parse(trimmed);
    // Keep retrying instead of crashing when Redis isn't up yet at worker start.
    cfg.AbortOnConnectFail = false;
    return cfg;
}
