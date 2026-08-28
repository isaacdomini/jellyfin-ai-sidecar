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
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.AiSidecar.Services;

/// <summary>
/// Hosted service that listens to Jellyfin library events and triggers the AI Sidecar indexing pipeline.
/// </summary>
public class LibraryEventListener : IHostedService, IDisposable
{
    private readonly ILibraryManager _libraryManager;
    private static readonly HttpClient _httpClient = new HttpClient();

    public LibraryEventListener(ILibraryManager libraryManager)
    {
        _libraryManager = libraryManager;
    }

    public Task StartAsync(CancellationToken cancellationToken)
    {
        _libraryManager.ItemAdded += OnItemAdded;
        _libraryManager.ItemUpdated += OnItemUpdated;
        Console.WriteLine("[LibraryEventListener] AI Sidecar Library Event Listener initialized.");
        return Task.CompletedTask;
    }

    public Task StopAsync(CancellationToken cancellationToken)
    {
        _libraryManager.ItemAdded -= OnItemAdded;
        _libraryManager.ItemUpdated -= OnItemUpdated;
        return Task.CompletedTask;
    }

    private void OnItemAdded(object? sender, ItemChangeEventArgs e)
    {
        _ = ProcessItemAsync(e.Item, "ItemAdded");
    }

    private void OnItemUpdated(object? sender, ItemChangeEventArgs e)
    {
        var config = Plugin.Instance?.Configuration;
        if (config != null && config.AutoIndexOnUpdate)
        {
            _ = ProcessItemAsync(e.Item, "ItemUpdated");
        }
    }

    private async Task ProcessItemAsync(BaseItem item, string eventType)
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null)
        {
            return;
        }

        if (eventType == "ItemAdded" && !config.AutoIndexOnAdd)
        {
            return;
        }

        if (eventType == "ItemUpdated" && !config.AutoIndexOnUpdate)
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
            var subPaths = (item as MediaBrowser.Controller.Entities.Video)?.MediaStreams?
                .Where(s => s.Type == MediaBrowser.Model.Entities.MediaStreamType.Subtitle && s.IsExternal && !string.IsNullOrEmpty(s.Path))
                .Select(s => s.Path)
                .ToList() ?? new List<string>();

            var payload = new
            {
                Event = eventType,
                ItemId = item.Id.ToString(),
                ItemName = item.Name,
                ItemType = item.GetType().Name,
                ItemPath = item.Path,
                SubtitlePaths = subPaths,
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

            using var requestMessage = new HttpRequestMessage(HttpMethod.Post, endpoint);
            requestMessage.Content = jsonContent;

            if (!string.IsNullOrWhiteSpace(config.ApiKey))
            {
                requestMessage.Headers.Add("X-API-Key", config.ApiKey);
            }

            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            Console.WriteLine($"[LibraryEventListener] Notifying AI Sidecar of media event ({eventType}): {item.Name} ({item.Path})");
            var response = await _httpClient.SendAsync(requestMessage, cts.Token).ConfigureAwait(false);

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine($"[LibraryEventListener] AI Sidecar accepted indexing for item: {item.Name}");
            }
            else
            {
                Console.WriteLine($"[LibraryEventListener] AI Sidecar responded with status {response.StatusCode} for item: {item.Name}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[LibraryEventListener] Failed to send media event notification to AI Sidecar for item: {item.Name} - {ex.Message}");
        }
    }

    public void Dispose()
    {
        _libraryManager.ItemAdded -= OnItemAdded;
        _libraryManager.ItemUpdated -= OnItemUpdated;
    }
}
