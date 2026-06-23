using Microsoft.AspNetCore.Mvc;
using PitchWise.Api.Config;

namespace PitchWise.Api.Controllers;

// Mirror of /api/health from main.py. analysis_inline is always false — in the
// .NET+worker architecture analysis always goes through Redis (inline mode was dev-only in Python).
[ApiController]
[Route("api/health")]
public class HealthController : ControllerBase
{
    private readonly AppSettings _settings;

    public HealthController(AppSettings settings) => _settings = settings;

    [HttpGet]
    public object Health() => new
    {
        status = "ok",
        llm_provider = _settings.LlmProvider,
        analysis_inline = false,
    };
}
