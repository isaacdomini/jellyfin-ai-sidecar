using System;
using System.Net.Http;
using System.Net.Mime;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
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
    private static readonly HttpClient _httpClient = new HttpClient();

    public AiSidecarController(ILibraryManager libraryManager)
    {
        _libraryManager = libraryManager;
    }

    private void LogError(Exception ex, string message)
    {
        try
        {
            var loggerFactory = HttpContext?.RequestServices?.GetService(typeof(ILoggerFactory)) as ILoggerFactory;
            var logger = loggerFactory?.CreateLogger<AiSidecarController>();
            logger?.LogError(ex, "{Message}", message);
        }
        catch
        {
            Console.WriteLine($"[AiSidecarController] ERROR: {message} - {ex.Message}");
        }
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
            using var cts = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(5));
            string healthUrl = $"{config.SidecarServerUrl.TrimEnd('/')}/health";
            var response = await _httpClient.GetAsync(healthUrl, cts.Token);

            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                return Ok(new { status = "connected", sidecar = JsonSerializer.Deserialize<object>(content) });
            }

            return StatusCode(StatusCodes.Status502BadGateway, new { status = "error", message = $"Sidecar returned {response.StatusCode}" });
        }
        catch (Exception ex)
        {
            LogError(ex, "Failed to connect to AI Sidecar service");
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
            string searchUrl = $"{config.SidecarServerUrl.TrimEnd('/')}/search";

            var jsonContent = new StringContent(
                JsonSerializer.Serialize(new { query = request.Query, top_k = request.TopK, item_id = request.ItemId }),
                Encoding.UTF8,
                "application/json"
            );

            var response = await _httpClient.PostAsync(searchUrl, jsonContent);
            var resultString = await response.Content.ReadAsStringAsync();

            return Content(resultString, MediaTypeNames.Application.Json);
        }
        catch (Exception ex)
        {
            LogError(ex, "Error while executing search on AI Sidecar");
            return StatusCode(StatusCodes.Status502BadGateway, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Manually triggers indexing for a specific Jellyfin library item.
    /// </summary>
    [HttpPost("IndexItem/{itemId}")]
    [Authorize]
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

        string endpoint = $"{config.SidecarServerUrl.TrimEnd('/')}/webhook/item-added";

        var jsonContent = new StringContent(
            JsonSerializer.Serialize(payload),
            Encoding.UTF8,
            "application/json"
        );

        var response = await _httpClient.PostAsync(endpoint, jsonContent);
        if (response.IsSuccessStatusCode)
        {
            return Ok(new { status = "success", message = $"Indexing task queued for {item.Name}." });
        }

        return StatusCode((int)response.StatusCode, new { status = "error", message = "Failed to queue indexing task." });
    }

    /// <summary>
    /// Executes a RAG (Retrieval-Augmented Generation) query with LLM answering and timestamp deep-links.
    /// </summary>
    [HttpPost("Ask")]
    [HttpPost("Rag")]
    [Authorize]
    [ProducesResponseType(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status400BadRequest)]
    public async Task<ActionResult> AskMedia([FromBody] RagRequestDto request)
    {
        if (string.IsNullOrWhiteSpace(request?.Query))
        {
            return BadRequest(new { message = "Query string cannot be empty." });
        }

        var config = Plugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.SidecarServerUrl))
        {
            return StatusCode(StatusCodes.Status500InternalServerError, new { message = "AI Sidecar server URL is not configured." });
        }

        try
        {
            using var cts = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(60));
            string ragUrl = $"{config.SidecarServerUrl.TrimEnd('/')}/rag/query";

            // Fallback to plugin configuration if request didn't override provider settings
            var payload = new
            {
                query = request.Query,
                item_id = request.ItemId,
                top_k = request.TopK ?? config.LlmTopK,
                provider = !string.IsNullOrWhiteSpace(request.Provider) ? request.Provider : config.LlmProvider,
                api_key = !string.IsNullOrWhiteSpace(request.ApiKey) ? request.ApiKey : config.LlmApiKey,
                model = !string.IsNullOrWhiteSpace(request.Model) ? request.Model : config.LlmModel,
                base_url = !string.IsNullOrWhiteSpace(request.BaseUrl) ? request.BaseUrl : config.LlmBaseUrl,
                temperature = request.Temperature ?? config.LlmTemperature
            };

            var jsonContent = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json"
            );

            var response = await _httpClient.PostAsync(ragUrl, jsonContent, cts.Token);
            var resultString = await response.Content.ReadAsStringAsync();

            return Content(resultString, MediaTypeNames.Application.Json);
        }
        catch (Exception ex)
        {
            LogError(ex, "Error while executing RAG query on AI Sidecar");
            return StatusCode(StatusCodes.Status502BadGateway, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Retrieves supported LLM providers from the AI Sidecar.
    /// </summary>
    [HttpGet("Providers")]
    [Authorize]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<ActionResult> GetProviders()
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.SidecarServerUrl))
        {
            return BadRequest(new { message = "AI Sidecar server URL is not configured." });
        }

        try
        {
            using var cts = new System.Threading.CancellationTokenSource(TimeSpan.FromSeconds(10));
            string providersUrl = $"{config.SidecarServerUrl.TrimEnd('/')}/rag/providers";
            var response = await _httpClient.GetAsync(providersUrl, cts.Token);
            var resultString = await response.Content.ReadAsStringAsync();

            return Content(resultString, MediaTypeNames.Application.Json);
        }
        catch (Exception ex)
        {
            LogError(ex, "Failed to retrieve LLM providers from AI Sidecar");
            return StatusCode(StatusCodes.Status502BadGateway, new { error = ex.Message });
        }
    }

    /// <summary>
    /// Triggers indexing across all existing movies and TV episodes in the library.
    /// </summary>
    [HttpPost("SyncLibrary")]
    [Authorize(Policy = "RequiresElevation")]
    public ActionResult SyncLibrary()
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.SidecarServerUrl))
        {
            return BadRequest(new { message = "AI Sidecar server URL is not configured." });
        }

        var task = new Services.LibrarySyncTask(_libraryManager);
        _ = Task.Run(() => task.ExecuteAsync(new Progress<double>(), CancellationToken.None));

        return Ok(new { status = "started", message = "Library synchronization has been started in the background." });
    }

    /// <summary>
    /// Serves the client-side JavaScript injection for the Jellyfin Web UI.
    /// Accessible by all users to enable floating context-aware AI scene search.
    /// </summary>
    [HttpGet("ClientScript")]
    [HttpGet("script.js")]
    [AllowAnonymous]
    [Produces("application/javascript")]
    public ActionResult GetClientScript()
    {
        var assembly = typeof(Plugin).Assembly;
        var resourceName = "Jellyfin.Plugin.AiSidecar.Web.sidecar.js";
        var stream = assembly.GetManifestResourceStream(resourceName);
        if (stream == null)
        {
            return NotFound("Client script resource not found.");
        }

        return File(stream, "application/javascript");
    }
}

public class SearchRequest
{
    [JsonPropertyName("query")]
    public string Query { get; set; } = string.Empty;

    [JsonPropertyName("top_k")]
    public int TopK { get; set; } = 5;

    [JsonPropertyName("topK")]
    public int? TopKCamel { set { if (value.HasValue) TopK = value.Value; } }

    [JsonPropertyName("item_id")]
    public string? ItemId { get; set; }

    [JsonPropertyName("itemId")]
    public string? ItemIdCamel { set { if (!string.IsNullOrWhiteSpace(value)) ItemId = value; } }
}

public class RagRequestDto
{
    [JsonPropertyName("query")]
    public string Query { get; set; } = string.Empty;

    [JsonPropertyName("item_id")]
    public string? ItemId { get; set; }

    [JsonPropertyName("itemId")]
    public string? ItemIdCamel { set { if (!string.IsNullOrWhiteSpace(value)) ItemId = value; } }

    [JsonPropertyName("top_k")]
    public int? TopK { get; set; }

    [JsonPropertyName("topK")]
    public int? TopKCamel { set { if (value.HasValue) TopK = value; } }

    [JsonPropertyName("provider")]
    public string? Provider { get; set; }

    [JsonPropertyName("api_key")]
    public string? ApiKey { get; set; }

    [JsonPropertyName("apiKey")]
    public string? ApiKeyCamel { set { if (!string.IsNullOrWhiteSpace(value)) ApiKey = value; } }

    [JsonPropertyName("model")]
    public string? Model { get; set; }

    [JsonPropertyName("base_url")]
    public string? BaseUrl { get; set; }

    [JsonPropertyName("baseUrl")]
    public string? BaseUrlCamel { set { if (!string.IsNullOrWhiteSpace(value)) BaseUrl = value; } }

    [JsonPropertyName("temperature")]
    public double? Temperature { get; set; }
}
