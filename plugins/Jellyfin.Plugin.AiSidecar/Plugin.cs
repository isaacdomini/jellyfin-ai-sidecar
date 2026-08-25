using System;
using System.Collections.Generic;
using Jellyfin.Plugin.AiSidecar.Configuration;
using MediaBrowser.Common.Configuration;
using MediaBrowser.Common.Plugins;
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

    public Plugin(IApplicationPaths applicationPaths, IXmlSerializer xmlSerializer)
        : base(applicationPaths, xmlSerializer)
    {
        Instance = this;
    }

    public IEnumerable<PluginPageInfo> GetPages()
    {
        return new[]
        {
            new PluginPageInfo
            {
                Name = "AiSidecar",
                EmbeddedResourcePath = $"{GetType().Namespace}.Configuration.configPage.html"
            }
        };
    }
}
