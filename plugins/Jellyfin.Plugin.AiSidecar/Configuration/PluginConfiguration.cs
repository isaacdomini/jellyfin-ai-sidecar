using MediaBrowser.Model.Plugins;

namespace Jellyfin.Plugin.AiSidecar.Configuration;

/// <summary>
/// Plugin configuration options for Jellyfin AI Sidecar.
/// </summary>
public class PluginConfiguration : BasePluginConfiguration
{
    /// <summary>
    /// Gets or sets the base URL for the FastAPI AI Sidecar service.
    /// </summary>
    public string SidecarServerUrl { get; set; } = "http://localhost:8000";

    /// <summary>
    /// Gets or sets an optional authentication API key / secret.
    /// </summary>
    public string ApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets a value indicating whether new media items should be automatically indexed.
    /// </summary>
    public bool AutoIndexOnAdd { get; set; } = true;

    /// <summary>
    /// Gets or sets a value indicating whether movie items are indexed.
    /// </summary>
    public bool IndexMovies { get; set; } = true;

    /// <summary>
    /// Gets or sets a value indicating whether TV episode items are indexed.
    /// </summary>
    public bool IndexEpisodes { get; set; } = true;

    /// <summary>
    /// Gets or sets the preferred subtitle language code (e.g., 'eng', 'spa', 'fre').
    /// </summary>
    public string PreferredSubtitleLanguage { get; set; } = "eng";
}
