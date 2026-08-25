using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Jellyfin.Data.Enums;
using MediaBrowser.Controller.Entities;
using MediaBrowser.Controller.Entities.Movies;
using MediaBrowser.Controller.Entities.TV;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Entities;
using MediaBrowser.Model.Tasks;
using Microsoft.Extensions.Logging;

namespace Jellyfin.Plugin.AiSidecar.Services;

/// <summary>
/// Scheduled task that iterates over existing media library items and sends them to AI Sidecar for indexing.
/// </summary>
public class LibrarySyncTask : IScheduledTask
{
    private readonly ILibraryManager _libraryManager;
    private readonly IHttpClientFactory? _httpClientFactory;
    private readonly ILogger<LibrarySyncTask> _logger;

    public LibrarySyncTask(
        ILibraryManager libraryManager,
        ILoggerFactory loggerFactory,
        IHttpClientFactory? httpClientFactory = null)
    {
        _libraryManager = libraryManager;
        _httpClientFactory = httpClientFactory;
        _logger = loggerFactory.CreateLogger<LibrarySyncTask>();
    }

    private HttpClient CreateHttpClient()
    {
        return _httpClientFactory?.CreateClient() ?? new HttpClient();
    }

    public string Name => "Index Media for AI Sidecar";

    public string Key => "AiSidecarLibrarySync";

    public string Description => "Scans existing movies and TV episodes in your library and sends them to the AI Sidecar service for subtitle extraction and vector search indexing.";

    public string Category => "AI Sidecar";

    public IEnumerable<TaskTriggerInfo> GetDefaultTriggers()
    {
        return new[]
        {
            new TaskTriggerInfo
            {
                Type = TaskTriggerInfoType.WeeklyTrigger,
                DayOfWeek = DayOfWeek.Sunday,
                TimeOfDayTicks = TimeSpan.FromHours(3).Ticks
            }
        };
    }

    public async Task ExecuteAsync(IProgress<double> progress, CancellationToken cancellationToken)
    {
        var config = Plugin.Instance?.Configuration;
        if (config == null || string.IsNullOrWhiteSpace(config.SidecarServerUrl))
        {
            _logger.LogWarning("AI Sidecar server URL is not configured. Aborting library sync.");
            return;
        }

        var query = new InternalItemsQuery
        {
            IncludeItemTypes = new[] { BaseItemKind.Movie, BaseItemKind.Episode },
            IsVirtualItem = false,
            Recursive = true
        };

        var items = _libraryManager.GetItemList(query)
            .Where(i => !string.IsNullOrEmpty(i.Path))
            .ToList();

        if (items.Count == 0)
        {
            _logger.LogInformation("No media items found to index.");
            progress.Report(100.0);
            return;
        }

        _logger.LogInformation("Found {Count} existing media items to index for AI Sidecar.", items.Count);

        var httpClient = CreateHttpClient();
        httpClient.Timeout = TimeSpan.FromSeconds(30);

        if (!string.IsNullOrWhiteSpace(config.ApiKey))
        {
            httpClient.DefaultRequestHeaders.Add("X-API-Key", config.ApiKey);
        }

        string sidecarUrl = config.SidecarServerUrl.TrimEnd('/');
        string endpoint = $"{sidecarUrl}/webhook/item-added";

        int processed = 0;
        foreach (var item in items)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                _logger.LogInformation("AI Sidecar library sync cancelled by user.");
                break;
            }

            try
            {
                var payload = new
                {
                    Event = "LibrarySync",
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

                var jsonContent = new StringContent(
                    JsonSerializer.Serialize(payload),
                    Encoding.UTF8,
                    "application/json"
                );

                var response = await httpClient.PostAsync(endpoint, jsonContent, cancellationToken).ConfigureAwait(false);
                if (response.IsSuccessStatusCode)
                {
                    _logger.LogDebug("Queued {Name} for indexing.", item.Name);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to send item {Name} to AI Sidecar during library sync", item.Name);
            }

            processed++;
            progress.Report((double)processed / items.Count * 100.0);

            // Small throttle to avoid flooding the sidecar queue
            await Task.Delay(50, cancellationToken).ConfigureAwait(false);
        }

        _logger.LogInformation("AI Sidecar library sync completed: {Processed}/{Total} items processed.", processed, items.Count);
        progress.Report(100.0);
    }
}
