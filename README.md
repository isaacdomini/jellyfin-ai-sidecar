# 🍿 Jellyfin AI Sidecar

An intelligent Retrieval-Augmented Generation (RAG) backend service for **Jellyfin Media Server**. It indexes video subtitles and dialogue using vector embeddings (`pgvector`) to enable **instant semantic search and scene discovery** across your entire media library.

---

## 🚀 How It Works

```
┌─────────────────┐      1. ItemAdded Webhook        ┌─────────────────────────────┐
│                 ├─────────────────────────────────►│                             │
│ Jellyfin Server │                                  │     Jellyfin AI Sidecar     │
│                 │◄─────────────────────────────────┤          (FastAPI)          │
└─────────────────┘       2. 200 OK (Immediate)      └──────────────┬──────────────┘
                                                                    │
                                                                    │ 3. Background Task
                                                                    ▼
                                                     ┌─────────────────────────────┐
                                                     │ 1. Subtitle Extraction      │
                                                     │    - External .srt Sidecar  │
                                                     │    - or FFmpeg (0:s:0)      │
                                                     │ 2. Sliding Window Chunker   │
                                                     │    (pysrt, ms time windows) │
                                                     │ 3. Vector Embeddings (768d) │
                                                     │ 4. Insert into pgvector DB  │
                                                     └──────────────┬──────────────┘
                                                                    │
                                                                    ▼
                                                     ┌─────────────────────────────┐
                                                     │   PostgreSQL + pgvector     │
                                                     │      (Vector Database)      │
                                                     └─────────────────────────────┘
```

1. **Jellyfin Event**: When a new movie or episode is added or scanned, Jellyfin sends an `ItemAdded` webhook notification to the sidecar (`POST /webhook/item-added`).
2. **Immediate Acknowledgment**: The API responds with `200 OK` instantly so Jellyfin is never blocked or timed out.
3. **Subtitle Extraction**:
   - **External `.srt` Subtitles**: If an `.srt` file exists alongside the video file (e.g. `Movie.en.srt` or inside a `Subs/` folder), the sidecar reads it directly without overhead.
   - **Embedded Subtitles**: If no external `.srt` exists, FFmpeg extracts the primary subtitle stream (`ffmpeg -y -i <video> -map 0:s:0 <temp.srt>`).
   - **Overview Fallback**: If no subtitles are available, it indexes the media description/overview.
4. **Time-Based Sliding Window Chunking**: `pysrt` breaks dialogue into overlapping time intervals (e.g. 30-second windows with 5-second overlap) preserving millisecond-accurate start and end timestamps.
5. **Vector Embedding**: Generates 768-dimensional float embeddings for each chunk.
6. **pgvector Storage & Semantic Search**: Chunks and vectors are stored in PostgreSQL with `pgvector` indexing, allowing cosine similarity search to find exact scenes by quote, dialogue, or description.

---

## 🛠️ Quickstart: How to Run

### Option 1: Docker Compose (Recommended)

The easiest way to run the sidecar along with PostgreSQL and pgvector using either the published GitHub Container Registry image or a local build:

1. **Clone and navigate to repository**:
   ```bash
   git clone https://github.com/isaacdomini/jellyfin-ai-sidecar.git
   cd jellyfin-ai-sidecar
   ```

2. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and adjust your variables:
   ```bash
   cp .env.example .env
   ```
   Or set inline environment variables when running `docker compose`:
   ```bash
   MEDIA_PATH="/path/to/your/jellyfin/media" POSTGRES_PASSWORD="your_secure_password" docker compose up -d
   ```

3. **Start the containers**:
   Using the pre-built GHCR image:
   ```bash
   docker compose up -d
   ```
   Or building from source locally:
   ```bash
   docker compose up --build -d
   ```

4. **Verify Health**:
   ```bash
   curl http://localhost:8000/health
   ```
   Output: `{"status":"healthy","app_name":"jellyfin-ai-sidecar","embedding_dimension":768}`

---

### Option 2: Local Development (Without Docker)

**Prerequisites**:
- Python 3.11+
- FFmpeg installed and available in `PATH` (`brew install ffmpeg` on macOS / `apt-get install ffmpeg` on Linux)
- PostgreSQL 16+ with the `pgvector` extension installed

1. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file (see `.env.example`):
   ```env
   DATABASE_URL=postgresql://jellyfin_user:jellyfin_pass@localhost:5432/jellyfin_ai
   CHUNK_SIZE_SECONDS=30
   CHUNK_OVERLAP_SECONDS=5
   EMBEDDING_DIMENSION=768
   ```

4. **Run the server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## 🎬 How Movies and Media Are Added

Movies and episodes can be indexed in three ways:

### 1. Automatic: Jellyfin Webhook Plugin
1. In Jellyfin, go to **Dashboard** ➔ **Plugins** ➔ **Catalog** and install the official **Webhook** plugin.
2. Restart Jellyfin.
3. In **Dashboard** ➔ **Plugins** ➔ **Webhook**, add a Generic Webhook:
   - **Webhook URL**: `http://<your-sidecar-ip>:8000/webhook/item-added`
   - **Notification Type**: `Item Added`
   - **Item Types**: `Movie`, `Episode`
   - **Send All Properties**: Checked (`true`)

### 2. Automatic: Native Jellyfin C# Plugin
Use the custom C# plugin located in [`plugins/Jellyfin.Plugin.AiSidecar`](./plugins/Jellyfin.Plugin.AiSidecar) which listens directly to internal Jellyfin library events and provides a dashboard interface.

### 3. Manual / API Direct Ingestion
You can manually trigger indexing for any media item or `.srt` file using `curl`:

```bash
curl -X POST "http://localhost:8000/webhook/item-added" \
     -H "Content-Type: application/json" \
     -d '{
       "Event": "ItemAdded",
       "Item": {
         "Id": "movie-12345",
         "Name": "Inception (2010)",
         "Type": "Movie",
         "Path": "/media/Movies/Inception (2010)/Inception.mkv",
         "Overview": "A thief who steals corporate secrets through the use of dream-sharing technology..."
       }
     }'
```

---

## 🔍 Semantic Search API

Search your indexed media library for dialogue, phrases, or scene descriptions:

### Request
`POST /search`

```json
{
  "query": "we need to go deeper",
  "top_k": 5
}
```

### Response
```json
{
  "query": "we need to go deeper",
  "results": [
    {
      "id": 42,
      "item_id": "movie-12345",
      "item_name": "Inception (2010)",
      "text": "Dreams within dreams. We need to go deeper into the subconscious.",
      "start_time": 3215.42,
      "end_time": 3245.18,
      "score": 0.9421
    }
  ]
}
```

---

## 🤖 LLM & RAG Query API (Natural Language & Deep-Links)

Ask complex natural language questions about scenes, plot lines, or quotes. The sidecar searches the vector DB for matching dialogue chunks, prompts the LLM with timestamp-annotated context, and returns both an answer and instant deep-links jumping straight to that exact scene in the Jellyfin video player!

### Example Query Flow

**Prompt:**
> *User Query:* "What was the final puzzle the villain left?"
>
> *Context:* `[Movie: The Enigma, Timestamp: 01:45:10 - 01:46:20] "The combination is hidden in the painting's frame."`
>
> *LLM Answer:* "The villain's final puzzle indicated that the combination is hidden in the painting's frame [The Enigma, 01:45:10 - 01:46:20]."

### Request
`POST /rag/query` (or `POST /rag/ask`)

```json
{
  "query": "What was the final puzzle the villain left?",
  "item_id": null,
  "top_k": 5,
  "provider": "openai",
  "model": "gpt-4o-mini",
  "temperature": 0.2
}
```

### Response
```json
{
  "query": "What was the final puzzle the villain left?",
  "answer": "The villain's final puzzle indicated that the combination is hidden inside the painting's frame [The Enigma, 01:45:10 - 01:46:20].",
  "provider_used": "openai",
  "model_used": "gpt-4o-mini",
  "citations": [
    {
      "item_id": "8e3b4822-1d54-4a2b-9e32-a5e2f7b88931",
      "item_name": "The Enigma",
      "start_time": 6310.0,
      "end_time": 6380.0,
      "timestamp_formatted": "01:45:10 - 01:46:20",
      "start_ticks": 63100000000,
      "deep_link": "http://localhost:8096/web/index.html#!/playback?itemId=8e3b4822-1d54-4a2b-9e32-a5e2f7b88931&startPositionTicks=63100000000",
      "text": "The combination is hidden in the painting's frame.",
      "score": 0.9325
    }
  ],
  "sources": [ ... ]
}
```

---

## 🔌 Supported LLM Providers

| Provider | Default Model | API Key Required? | Base URL Support |
|---|---|---|---|
| **OpenAI** | `gpt-4o-mini` | Yes (`sk-...`) | Yes (`https://api.openai.com/v1`) |
| **Google Gemini** | `gemini-2.0-flash` | Yes (`AIzaSy...`) | No (Google API endpoint) |
| **Anthropic Claude** | `claude-3-5-haiku-20241022` | Yes (`sk-ant-...`) | No (Anthropic API endpoint) |
| **Groq** | `llama-3.3-70b-versatile` | Yes (`gsk_...`) | Yes (`https://api.groq.com/openai/v1`) |
| **Ollama** | `llama3.2` | No | Yes (`http://localhost:11434/v1`) |
| **Custom / OpenAI-Compatible** | `custom-model` | Optional | Yes (OpenRouter, vLLM, DeepSeek, LocalAI) |

---

## ⚙️ Configuration Reference

All environment variables use the `AI_SIDECAR_` prefix so they can be safely added to shared `.env` files across multi-service Docker setups:

| Scoped Variable | Fallback Variable | Default | Description |
|---|---|---|---|
| `AI_SIDECAR_IMAGE_TAG` | `IMAGE_TAG` | `latest` | Docker image tag |
| `AI_SIDECAR_PORT` | `APP_PORT` | `8000` | Host port for FastAPI API |
| `AI_SIDECAR_DB_PORT` | `DB_PORT` | `5432` | Host port for PostgreSQL |
| `AI_SIDECAR_MEDIA_PATH` | `MEDIA_PATH` | `./media` | Host media path mounted to `/data/ext_media:ro` |
| `AI_SIDECAR_DB_USER` | `POSTGRES_USER` | `jellyfin_user` | Database user |
| `AI_SIDECAR_DB_PASSWORD` | `POSTGRES_PASSWORD` | `jellyfin_pass` | Database password |
| `AI_SIDECAR_DB_HOST` | `POSTGRES_HOST` | `db` | Database host |
| `AI_SIDECAR_DB_NAME` | `POSTGRES_DB` | `jellyfin_ai` | Database name |
| `AI_SIDECAR_CHUNK_SIZE_SECONDS` | `CHUNK_SIZE_SECONDS` | `30` | Sliding window chunk duration (seconds) |
| `AI_SIDECAR_CHUNK_OVERLAP_SECONDS` | `CHUNK_OVERLAP_SECONDS` | `5` | Sliding window overlap duration (seconds) |
| `AI_SIDECAR_EMBEDDING_DIMENSION` | `EMBEDDING_DIMENSION` | `768` | Vector embedding dimension size |
| `AI_SIDECAR_LLM_PROVIDER` | `LLM_PROVIDER` | `openai` | LLM provider (`openai`, `gemini`, `anthropic`, `groq`, `ollama`, `custom`) |
| `AI_SIDECAR_LLM_API_KEY` | `LLM_API_KEY` | `""` | API key for selected LLM provider |
| `AI_SIDECAR_LLM_MODEL` | `LLM_MODEL` | `gpt-4o-mini` | LLM model override |
| `AI_SIDECAR_LLM_BASE_URL` | `LLM_BASE_URL` | `""` | Custom LLM base URL endpoint |
| `AI_SIDECAR_LLM_TEMPERATURE` | `LLM_TEMPERATURE` | `0.2` | Sampling temperature |
| `AI_SIDECAR_RAG_TOP_K` | `RAG_TOP_K` | `5` | Number of context chunks for RAG |
| `AI_SIDECAR_JELLYFIN_SERVER_URL` | `JELLYFIN_SERVER_URL` | `""` | Jellyfin Server URL (for deep-links) |
| `AI_SIDECAR_DEBUG` | `DEBUG` | `false` | Enable verbose debugging logs |


