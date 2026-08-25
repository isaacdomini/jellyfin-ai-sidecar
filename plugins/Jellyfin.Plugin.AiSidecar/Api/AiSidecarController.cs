using System;
using System.Net.Http;
using System.Net.Mime;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Library;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.AiSidecar.Api;

/// <summary>
/// API Controller exposing AI Sidecar functionality through Jellyfin's REST API.
/// </summary>
[ApiController]
[Route("Plugins/AiSidecar")]
[Produces(MediaTypeNames.Application.Json)]
public class AiSidecarController : ControllerBase
{
    private readonly ILibraryManager _libraryManager;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<AiSidecarController> _logger;

    public AiSidecarController(
        ILibraryManager libraryManager,
        IHttpClientFactory httpClientFactory,
        ILogger<AiSidecarController> logger)
    {
        _libraryManager = libraryManager;
        _httpClientFactory = httpClientFactory;
        _logger = logger;
    }

    /// <summary>
    /// Tests connection between Jellyfin and the AI Sidecar service.
    /// </summary>
    [HttpGet("Status")]
    [Authorize]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status502BadGateway)]
    public async Task<ActionResult> GetSidecarStatus()
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.SidecarServerUrl))
        {
            return BadRequest(new { status = "error", message = "AI Sidecar server URL is not configured." });
        }

        try
        {
            var httpClient = _httpClientFactory.CreateClient();
            httpClient.Timeout = TimeSpan.FromSeconds(5);

            string healthUrl = $"{config.SidecarServerUrl.TrimEnd('/')}/health";
            var response = await httpClient.GetAsync(healthUrl);

            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                return Ok(new { status = "connected", sidecar = JsonSerializer.Deserialize<object>(content) });
            }

            return StatusCode(StatusCodes.Status502BadGateway, new { status = "error", message = $"Sidecar returned {response.StatusCode}" });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to connect to AI Sidecar service");
            return StatusCode(StatusCodes.Status502BadGateway, new { status = "disconnected", error = ex.Message });
        }
    }

    /// <summary>
    /// Executes a semantic query search through the AI Sidecar.
    /// </summary>
    [HttpPost("Search")]
    [Authorize]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult> SearchMedia([FromBody] SearchRequest request)
    {
        if (string.IsNullOrWhiteSpace(request?.Query))
        {
            return BadRequest(new { message = "Query string cannot be empty." });
        }

        var config = Plugin.Instance?.Configuration;
        if (config == null)
        {
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "Plugin configuration not loaded." });
        }

        try
        {
            var httpClient = _httpClientFactory.CreateClient();
            string searchUrl = $"{config.SidecarServerUrl.TrimEnd('/')}/search";

            var jsonContent = new StringContent(
                JsonSerializer.Serialize(new { query = request.Query, top_k = request.TopK, item_id = request.ItemId }),
                Encoding.UTF8,
                "application/json"
            );

            var response = await httpClient.PostAsync(searchUrl, jsonContent);
            var resultString = await response.Content.ReadAsStringAsync();

            return Content(resultString, MediaTypeNames.Application.Json);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error while executing search on AI Sidecar");
            return StatusCode(StatusCodes.Status502BadGateway, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Manually triggers indexing for a specific Jellyfin library item.
    /// </summary>
    [HttpPost("IndexItem/{itemId}")]
    [Authorize(Policy = "RequiresElevation")]
    public async Task<ActionResult> IndexItem([FromRoute] Guid itemId)
    {
        var item = _libraryManager.GetItemById(itemId);
        if (item == null)
        {
            return NotFound(new { message = $"Item with ID {itemId} not found." });
        }

        var config = Plugin.Instance?.Configuration;
        if (config == null)
        {
            return BadRequest(new { message = "Plugin configuration missing." });
        }

        var payload = new
        {
            Event = "ManualIndex",
            ItemId = item.Id.ToString(),
            ItemName = item.Name,
            ItemType = item.GetType().Name,
            ItemPath = item.Path,
            Item = new
            {
                Id = item.Id.ToString(),
                Name = item.Name,
                Type = item.GetType().Name,
                Path = item.Path,
                Overview = item.Overview
            }
        };

        var httpClient = _httpClientFactory.CreateClient();
        string endpoint = $"{config.SidecarServerUrl.TrimEnd('/')}/webhook/item-added";

        var jsonContent = new StringContent(
            JsonSerializer.Serialize(payload),
            Encoding.UTF8,
            "application/json"
        );

        var response = await httpClient.PostAsync(endpoint, jsonContent);
        if (response.IsSuccessStatusCode)
        {
            return Ok(new { status = "success", message = $"Indexing task queued for {item.Name}." });
        }

        return StatusCode((int)response.StatusCode, new { status = "error", message = "Failed to queue indexing task." });
    }
}

public class SearchRequest
{
    public string Query { get; set; } = string.Empty;
    public int TopK { get; set; } = 5;
    public string? ItemId { get; set; }
}
