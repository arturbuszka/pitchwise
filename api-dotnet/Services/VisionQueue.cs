using System.Text.Json;
using PitchWise.Api.Config;
using StackExchange.Redis;

namespace PitchWise.Api.Services;

// Zastępuje worker/app/queue.py (ścieżka produkcyjna). .NET tylko wrzuca job_id jako
// JSON do listy Redis; pythonowy worker zdejmuje go przez BRPOP. To cały kontrakt.
public class VisionQueue
{
    private readonly IConnectionMultiplexer _redis;
    private readonly AppSettings _settings;

    public VisionQueue(IConnectionMultiplexer redis, AppSettings settings)
    {
        _redis = redis;
        _settings = settings;
    }

    public async Task EnqueueAsync(int jobId)
    {
        var db = _redis.GetDatabase();
        var payload = JsonSerializer.Serialize(new { job_id = jobId });
        // LPUSH + (worker) BRPOP => kolejka FIFO.
        await db.ListLeftPushAsync(_settings.VisionQueue, payload);
    }
}
