from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.webhooks import router as webhooks_router, search_router
from app.api.rag import router as rag_router
from app.services.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(settings.APP_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifespan handler.
    Initializes PostgreSQL database and pgvector extension on startup.
    """
    logger.info("Starting up Jellyfin AI Sidecar service...")
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Database initialization deferred or failed: {e}")
    yield
    logger.info("Shutting down Jellyfin AI Sidecar service...")


app = FastAPI(
    title="Jellyfin AI Sidecar",
    description="FastAPI backend for Jellyfin Semantic Media Search & LLM RAG pipeline",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for external access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(webhooks_router)
app.include_router(search_router)
app.include_router(rag_router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "embedding_dimension": settings.EMBEDDING_DIMENSION
    }


@app.get("/stats", tags=["Library Stats"])
async def get_stats():
    from app.services.database import get_library_stats
    return get_library_stats()


@app.post("/library/clear", tags=["Library Stats"])
@app.delete("/library/clear", tags=["Library Stats"])
async def clear_library():
    from app.services.database import clear_database
    return clear_database()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

