using Jellyfin.Plugin.AiSidecar.Services;
using MediaBrowser.Common.Plugins;
using MediaBrowser.Controller;
using Microsoft.Extensions.DependencyInjection;

namespace Jellyfin.Plugin.AiSidecar;

/// <summary>
/// Registers AI Sidecar plugin services into Jellyfin's dependency injection container.
/// </summary>
public class PluginServiceRegistrator : IPluginServiceRegistrator
{
    /// <inheritdoc />
    public void RegisterServices(IServiceCollection serviceCollection, IServerApplicationHost applicationHost)
    {
        serviceCollection.AddHostedService<LibraryEventListener>();
    }
}
