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

The easiest way to run the sidecar along with PostgreSQL and pgvector:

1. **Clone and navigate to repository**:
   ```bash
   git clone <repo-url>
   cd jellyfin-ai-sidecar
   ```

2. **Configure Media Volume** in `docker-compose.yml`:
   Ensure the `app` service can access your Jellyfin media path so it can read video/subtitle files:
   ```yaml
   volumes:
     - ./app:/app/app
     - /path/to/your/jellyfin/media:/media:ro  # Mount your media directory
   ```

3. **Start the containers**:
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

## 📂 Subtitle Format Support

The sidecar automatically detects and supports:
- **External Sidecar Subtitles**:
  - `MovieName.srt`
  - `MovieName.en.srt`, `MovieName.eng.srt`, `MovieName.default.srt`
  - Subtitles located in adjacent `Subs/` or `Subtitles/` directories
- **Embedded Subtitle Streams**: `.mkv`, `.mp4`, `.m4v`, `.webm`, `.avi` with embedded subtitle tracks (extracted on-the-fly with FFmpeg).
- **Direct SRT Indexing**: Pass the path directly to an `.srt` file in the webhook payload.

---

## ⚙️ Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection URI |
| `POSTGRES_USER` | `jellyfin_user` | Database user |
| `POSTGRES_PASSWORD` | `jellyfin_pass` | Database password |
| `POSTGRES_HOST` | `db` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_DB` | `jellyfin_ai` | Database name |
| `CHUNK_SIZE_SECONDS` | `30` | Sliding window chunk duration |
| `CHUNK_OVERLAP_SECONDS` | `5` | Sliding window overlap duration |
| `EMBEDDING_DIMENSION` | `768` | Vector embedding dimension size |
| `FFMPEG_PATH` | `ffmpeg` | Path to FFmpeg executable |
