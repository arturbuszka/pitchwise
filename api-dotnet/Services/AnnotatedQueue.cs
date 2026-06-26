using System.Text.Json;
using PitchWise.Api.Config;
using StackExchange.Redis;

namespace PitchWise.Api.Services;

public class AnnotatedQueue
{
    private readonly IConnectionMultiplexer _redis;
    private readonly AppSettings _settings;

    public AnnotatedQueue(IConnectionMultiplexer redis, AppSettings settings)
    {
        _redis = redis;
        _settings = settings;
    }

    public async Task EnqueueAsync(int jobId)
    {
        var db = _redis.GetDatabase();
        var payload = JsonSerializer.Serialize(new { job_id = jobId });
        await db.ListLeftPushAsync(_settings.AnnotatedQueue, payload);
    }
}
