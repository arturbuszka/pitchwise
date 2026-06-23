using Microsoft.AspNetCore.Mvc;
using PitchWise.Api.Config;

namespace PitchWise.Api.Controllers;

// Odpowiednik /api/health z main.py. analysis_inline zawsze false — w architekturze
// .NET+worker analiza zawsze idzie przez Redis (tryb inline był dev-only w Pythonie).
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
