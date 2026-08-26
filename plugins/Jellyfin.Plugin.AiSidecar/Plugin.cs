using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using Jellyfin.Plugin.AiSidecar.Configuration;
using Jellyfin.Plugin.AiSidecar.Services;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Controller.Library;
using MediaBrowser.Model.Plugins;
using MediaBrowser.Model.Serialization;

namespace Jellyfin.Plugin.AiSidecar;

/// <summary>
/// Main plugin class for Jellyfin AI Sidecar Semantic Search.
/// </summary>
public class Plugin : BasePlugin<PluginConfiguration>, IHasWebPages
{
    public override string Name => "AI Sidecar";

    public override Guid Id => Guid.Parse("7c9e3f22-1d54-4a2b-9e32-a5e2f7b88931");

    public override string Description => "Enables AI-powered semantic scene and dialogue search using the Jellyfin AI Sidecar service.";

    public static Plugin? Instance { get; private set; }

    private readonly LibraryEventListener? _eventListener;

    public Plugin(IApplicationPaths applicationPaths, IXmlSerializer xmlSerializer, ILibraryManager libraryManager)
        : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
        TryInjectClientScript(applicationPaths);
        try
        {
            _eventListener = new LibraryEventListener(libraryManager);
            _ = _eventListener.StartAsync(CancellationToken.None);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[AiSidecar] Warning: Could not initialize LibraryEventListener: {ex.Message}");
        }
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing)
        {
            _eventListener?.Dispose();
        }

        base.Dispose(disposing);
    }

    /// <summary>
    /// Automatically injects the AI Sidecar client script tag into Jellyfin Web's index.html
    /// so that the floating search button is available to all users without manual web edits.
    /// </summary>
    private void TryInjectClientScript(IApplicationPaths applicationPaths)
    {
        try
        {
            var webPath = applicationPaths.WebPath;
            if (string.IsNullOrWhiteSpace(webPath))
            {
                return;
            }

            var indexPath = System.IO.Path.Combine(webPath, "index.html");
            if (!System.IO.File.Exists(indexPath))
            {
                return;
            }

            var content = System.IO.File.ReadAllText(indexPath);
            const string scriptTag = "<script src=\"/Plugins/AiSidecar/ClientScript\" defer></script>";

            if (!content.Contains("/Plugins/AiSidecar/ClientScript", StringComparison.OrdinalIgnoreCase))
            {
                string updated;
                if (content.Contains("</body>", StringComparison.OrdinalIgnoreCase))
                {
                    updated = content.Replace("</body>", $"{scriptTag}\n</body>", StringComparison.OrdinalIgnoreCase);
                }
                else
                {
                    updated = content + "\n" + scriptTag;
                }

                System.IO.File.WriteAllText(indexPath, updated);
                Console.WriteLine("[AiSidecar] Successfully injected client script tag into Jellyfin Web index.html");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[AiSidecar] Notice: Could not auto-inject into index.html: {ex.Message}");
        }
    }

    public IEnumerable<PluginPageInfo> GetPages()
    {
        var resourcePath = string.Format(CultureInfo.InvariantCulture, "{0}.Configuration.configPage.html", GetType().Namespace);
        return new[]
        {
            new PluginPageInfo
            {
                Name = "AiSidecar",
                EmbeddedResourcePath = resourcePath
            },
            new PluginPageInfo
            {
                Name = this.Name,
                EmbeddedResourcePath = resourcePath
            }
        };
    }
}
