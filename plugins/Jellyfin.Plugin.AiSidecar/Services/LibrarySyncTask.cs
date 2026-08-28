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
    private static readonly HttpClient _httpClient = new HttpClient();

    public LibrarySyncTask(ILibraryManager libraryManager)
    {
        _libraryManager = libraryManager;
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
            Console.WriteLine("[LibrarySyncTask] AI Sidecar server URL is not configured. Aborting library sync.");
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
            Console.WriteLine("[LibrarySyncTask] No media items found to index.");
            progress.Report(100.0);
            return;
        }

        Console.WriteLine($"[LibrarySyncTask] Found {items.Count} existing media items to index for AI Sidecar.");

        string sidecarUrl = config.SidecarServerUrl.TrimEnd('/');
        string endpoint = $"{sidecarUrl}/webhook/item-added";

        int processed = 0;
        foreach (var item in items)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                Console.WriteLine("[LibrarySyncTask] AI Sidecar library sync cancelled by user.");
                break;
            }

            try
            {
                var subPaths = (item as MediaBrowser.Controller.Entities.Video)?.MediaStreams?
                    .Where(s => s.Type == MediaBrowser.Model.Entities.MediaStreamType.Subtitle && s.IsExternal && !string.IsNullOrEmpty(s.Path))
                    .Select(s => s.Path)
                    .ToList() ?? new List<string>();

                var payload = new
                {
                    Event = "LibrarySync",
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

                var response = await _httpClient.SendAsync(requestMessage, cancellationToken).ConfigureAwait(false);
                if (response.IsSuccessStatusCode)
                {
                    // Queued
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LibrarySyncTask] Failed to send item {item.Name} to AI Sidecar: {ex.Message}");
            }

            processed++;
            progress.Report((double)processed / items.Count * 100.0);

            // Small throttle to avoid flooding the sidecar queue
            await Task.Delay(50, cancellationToken).ConfigureAwait(false);
        }

        Console.WriteLine($"[LibrarySyncTask] AI Sidecar library sync completed: {processed}/{items.Count} items processed.");
        progress.Report(100.0);
    }
}
