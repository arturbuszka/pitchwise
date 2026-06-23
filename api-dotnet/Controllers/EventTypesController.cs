using Microsoft.AspNetCore.Mvc;
using PitchWise.Api.Config;
using PitchWise.Api.Dtos;

namespace PitchWise.Api.Controllers;

// Mirror of worker/app/routers/event_types.py. The sport parameter is ignored (as before).
[ApiController]
[Route("api/event-types")]
public class EventTypesController : ControllerBase
{
    [HttpGet]
    public IReadOnlyList<EventTypeConfigOut> List([FromQuery] string? sport) => EventTypeConfig.All;
}
