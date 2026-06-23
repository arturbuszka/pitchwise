using Microsoft.AspNetCore.Mvc;
using PitchWise.Api.Config;
using PitchWise.Api.Dtos;

namespace PitchWise.Api.Controllers;

// Odpowiednik worker/app/routers/event_types.py. Parametr sport jest ignorowany (jak dziś).
[ApiController]
[Route("api/event-types")]
public class EventTypesController : ControllerBase
{
    [HttpGet]
    public IReadOnlyList<EventTypeConfigOut> List([FromQuery] string? sport) => EventTypeConfig.All;
}
