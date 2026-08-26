# 🔌 Jellyfin AI Sidecar Plugin

A native Jellyfin server plugin that automatically notifies the **Jellyfin AI Sidecar** when media is added or updated, enabling seamless subtitle extraction, vectorization, and semantic scene search.

---

## ✨ Features

- **Automatic Event Dispatch**: Listens to Jellyfin's internal `ILibraryManager.ItemAdded` events and forwards media metadata directly to the Sidecar without requiring manual webhook configuration.
- **Admin Dashboard Settings**: Configure Sidecar URL, authentication, and indexing preferences directly inside Jellyfin Server Dashboard under **Plugins** ➔ **AI Sidecar**.
- **Connection Diagnostics**: Built-in "Test Connection" button to verify communication with the AI Sidecar.
- **Jellyfin API Extensions**: Exposes `/Plugins/AiSidecar/Search`, `/Plugins/AiSidecar/Rag`, and `/Plugins/AiSidecar/ClientScript` for clients and scripts.
- **Client-Side Floating Search Widget**: Bundles a context-aware floating button (`✨ Ask AI Scene`) and modal for all web users (admin & non-admin).

---

## 🛠️ Build & Installation

### Prerequisites
- [.NET 8.0 or .NET 9.0 SDK](https://dotnet.microsoft.com/download)
- Jellyfin Media Server 10.9+ or 10.11+

### 1. Build the Plugin

From the repository root or the plugin directory:

```bash
cd plugins/Jellyfin.Plugin.AiSidecar
dotnet publish -c Release -o ./publish
```

### 2. Install to Jellyfin Server

1. Locate your Jellyfin server configuration directory (e.g. `/var/lib/jellyfin/plugins` on Linux, `%ProgramData%\Jellyfin\Server\plugins` on Windows, or your docker mapped volume for `/config/plugins`).
2. Create a folder named `AiSidecar`:
   ```bash
   mkdir -p /path/to/jellyfin/plugins/AiSidecar
   ```
3. Copy the compiled DLLs from `./publish/` into `/path/to/jellyfin/plugins/AiSidecar/`:
   ```bash
   cp ./publish/Jellyfin.Plugin.AiSidecar.dll /path/to/jellyfin/plugins/AiSidecar/
   ```
4. Restart Jellyfin Server.

---

## ⚙️ Configuration in Jellyfin

1. Log into your Jellyfin Server as an administrator.
2. Go to **Dashboard** ➔ **Plugins** ➔ **AI Sidecar**.
3. Set **Sidecar Server URL** to your running FastAPI sidecar (e.g. `http://ai-sidecar:8000` in Docker networks, or `http://localhost:8000`).
4. Click **Test Connection** to ensure the green checkmark appears.
5. Click **Save Settings**.

---

## 🌐 Floating AI Search for All Users (Non-Admins)

The plugin bundles a version-controlled client script (`sidecar.js`) that provides a floating **"✨ Ask AI Scene"** button and search modal:
- **Active Video Playback**: Automatically scopes questions to the currently playing movie/episode and seeks inside the player when a scene is clicked.
- **Details Pages**: Scopes questions to the active Movie, Series, Season, or Episode.
- **Library / Home**: Defaults to a global search across all indexed media.

### Automatic Injection:
On Jellyfin server startup, the plugin automatically checks Jellyfin Web's `index.html` and injects the client script reference (`<script src="/Plugins/AiSidecar/ClientScript" defer></script>`).

**No manual UI configuration is needed.** Once you install the plugin and restart Jellyfin, the floating search button appears automatically for all users.
