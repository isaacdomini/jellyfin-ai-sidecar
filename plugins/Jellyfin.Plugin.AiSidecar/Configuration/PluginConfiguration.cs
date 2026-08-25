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
    /// Gets or sets a value indicating whether modified media items (e.g. newly added subtitles) should be automatically re-indexed.
    /// </summary>
    public bool AutoIndexOnUpdate { get; set; } = true;

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

    /// <summary>
    /// Gets or sets the LLM provider (e.g. OpenAI, Gemini, Anthropic, Groq, Ollama, Custom).
    /// </summary>
    public string LlmProvider { get; set; } = "OpenAI";

    /// <summary>
    /// Gets or sets the API key for the chosen LLM provider.
    /// </summary>
    public string LlmApiKey { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the LLM model name (e.g. gpt-4o-mini, gemini-2.0-flash, claude-3-5-haiku-20241022, llama-3.3-70b-versatile, llama3.2).
    /// </summary>
    public string LlmModel { get; set; } = "gpt-4o-mini";

    /// <summary>
    /// Gets or sets an optional custom base URL for the LLM provider (e.g. for Ollama or custom OpenAI-compatible endpoint).
    /// </summary>
    public string LlmBaseUrl { get; set; } = string.Empty;

    /// <summary>
    /// Gets or sets the number of top context chunks retrieved for RAG queries.
    /// </summary>
    public int LlmTopK { get; set; } = 5;

    /// <summary>
    /// Gets or sets the LLM sampling temperature.
    /// </summary>
    public double LlmTemperature { get; set; } = 0.2;
}
