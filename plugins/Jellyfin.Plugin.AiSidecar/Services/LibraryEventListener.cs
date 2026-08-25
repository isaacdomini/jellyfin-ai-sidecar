using System;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Controller.Plugins;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.AiSidecar.Services;

/// <summary>
/// Server entry point that listens to Jellyfin library events and triggers the AI Sidecar indexing pipeline.
/// </summary>
public class LibraryEventListener : IServerEntryPoint
{
    private readonly ILibraryManager _libraryManager;
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<LibraryEventListener> _logger;

    public LibraryEventListener(
        ILibraryManager libraryManager,
        IHttpClientFactory httpClientFactory,
        ILogger<LibraryEventListener> logger)
    {
        _libraryManager = libraryManager;
        _httpClientFactory = httpClientFactory;
        _logger = logger;
    }

    public Task RunAsync()
    {
        _libraryManager.ItemAdded += OnItemAdded;
        _libraryManager.ItemUpdated += OnItemUpdated;
        _logger.LogInformation("AI Sidecar Library Event Listener initialized.");
        return Task.CompletedTask;
    }

    private void OnItemAdded(object? sender, ItemChangeEventArgs e)
    {
        _ = ProcessItemAsync(e.Item, "ItemAdded");
    }

    private void OnItemUpdated(object? sender, ItemChangeEventArgs e)
    {
        // Optional: re-index when item metadata is significantly refreshed
        if (e.Item is Movie || e.Item is Episode)
        {
            _logger.LogDebug("Media item updated: {Name}", e.Item.Name);
        }
    }

    private async Task ProcessItemAsync(BaseItem item, string eventType)
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null || !config.AutoIndexOnAdd)
        {
            return;
        }

        bool isMovie = item is Movie;
        bool isEpisode = item is Episode;

        if ((isMovie && !config.IndexMovies) || (isEpisode && !config.IndexEpisodes))
        {
            return;
        }

        if (!isMovie && !isEpisode && !(item is Video))
        {
            return;
        }

        try
        {
            var payload = new
            {
                Event = eventType,
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
                    Overview = item.Overview,
                    SeriesName = (item as Episode)?.SeriesName,
                    SeasonName = (item as Episode)?.SeasonName,
                    IndexNumber = (item as Episode)?.IndexNumber,
                    ParentIndexNumber = (item as Episode)?.ParentIndexNumber,
                    RunTimeTicks = item.RunTimeTicks
                }
            };

            string sidecarUrl = config.SidecarServerUrl.TrimEnd('/');
            string endpoint = $"{sidecarUrl}/webhook/item-added";

            var jsonContent = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json"
            );

            var httpClient = _httpClientFactory.CreateClient();
            httpClient.Timeout = TimeSpan.FromSeconds(15);

            if (!string.IsNullOrWhiteSpace(config.ApiKey))
            {
                httpClient.DefaultRequestHeaders.Add("X-API-Key", config.ApiKey);
            }

            _logger.LogInformation("Notifying AI Sidecar of new media: {Name} ({Path})", item.Name, item.Path);
            var response = await httpClient.PostAsync(endpoint, jsonContent).ConfigureAwait(false);

            if (response.IsSuccessStatusCode)
            {
                _logger.LogInformation("AI Sidecar accepted indexing for item: {Name}", item.Name);
            }
            else
            {
                _logger.LogWarning("AI Sidecar responded with status {StatusCode} for item: {Name}", response.StatusCode, item.Name);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to send item-added notification to AI Sidecar for item: {Name}", item.Name);
        }
    }

    public void Dispose()
    {
        _libraryManager.ItemAdded -= OnItemAdded;
        _libraryManager.ItemUpdated -= OnItemUpdated;
    }
}
