from typing import Optional
import os
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.models.schemas import (
    JellyfinItemEvent,
    SearchQuery,
    SearchResponse,
    SearchResultItem
)
from app.services.extractor import extract_best_single_subtitle, extract_subtitles
from app.core.chunker import chunk_subtitles
from app.services.embedder import get_embeddings, get_embedding
from app.services.database import insert_chunks, search_similar_chunks
from app.services.llm import llm_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["Jellyfin Webhooks"])
search_router = APIRouter(prefix="/search", tags=["Semantic Search"])


async def process_media_item_background(
    item_id: str,
    item_name: Optional[str] = None,
    file_path: Optional[str] = None,
    overview: Optional[str] = None
) -> None:
    """
    Asynchronous background pipeline:
    1. Extracts the single best English subtitle track (or single foreign subtitle track if no English exists).
    2. If subtitles are in a foreign language, translates dialogue chunks to English.
    3. Segments subtitle text into overlapping chunks using pysrt.
    4. Generates 768-dimensional vector embeddings for each chunk.
    5. Inserts chunks with pgvector embeddings into PostgreSQL.
    """
    logger.info(f"Starting background processing for item: id={item_id}, name='{item_name}'")
    chunks = []

    # Attempt subtitle extraction if file exists
    if file_path and os.path.exists(file_path):
        try:
            srt_content, detected_lang, is_english = extract_best_single_subtitle(file_path)
            if srt_content.strip():
                raw_chunks = chunk_subtitles(
                    srt_content,
                    chunk_size_seconds=settings.CHUNK_SIZE_SECONDS,
                    overlap_seconds=settings.CHUNK_OVERLAP_SECONDS
                )
                chunks = raw_chunks
                logger.info(f"Ready to index {len(chunks)} chunks for '{item_name}' (lang='{detected_lang}').")
        except Exception as exc:
            logger.error(f"Failed to extract or chunk subtitles for item {item_id}: {exc}", exc_info=True)

    # Include overview plot synopsis chunk if available for plot-level and thematic searches
    if overview and overview.strip():
        overview_chunk = {
            "text": f"Plot Summary: {overview.strip()}",
            "start_time": 0.0,
            "end_time": 0.0,
            "start_time_ms": 0,
            "end_time_ms": 0,
            "item_count": 1
        }
        chunks.insert(0, overview_chunk)

    if not chunks:
        logger.warning(f"No subtitle or overview content available to index for item {item_id}")
        return

    try:
        # Generate 768-dimensional vector embeddings
        texts = [chunk["text"] for chunk in chunks]
        logger.info(f"Generating 768-dim embeddings for {len(texts)} chunks...")
        embeddings = get_embeddings(texts)

        # Insert chunks and vectors into pgvector database
        inserted_count = insert_chunks(
            item_id=item_id,
            chunks=chunks,
            embeddings=embeddings,
            item_name=item_name
        )
        logger.info(f"Successfully indexed {inserted_count} chunks into PostgreSQL for item {item_id}")
    except Exception as exc:
        logger.error(f"Error persisting chunks/embeddings for item {item_id}: {exc}", exc_info=True)


@router.post("/item-added", status_code=status.HTTP_200_OK)
@router.post("/item-updated", status_code=status.HTTP_200_OK)
async def item_event_webhook(
    payload: JellyfinItemEvent,
    background_tasks: BackgroundTasks
):
    """
    Accepts Jellyfin ItemAdded and ItemUpdated webhook events, returns 200 OK immediately,
    and triggers extraction, chunking, and database insertion asynchronously.
    """
    item_id = payload.get_item_id() or "unknown_item"
    item_name = payload.get_item_name() or "Untitled Media"
    file_path = payload.get_file_path()
    overview = payload.get_overview()
    event_name = payload.Event or payload.NotificationType or "ItemEvent"
    logger.info(f"Received webhook for media item: event='{event_name}', id='{item_id}', name='{item_name}', path='{file_path}'")

    # Queue extraction, chunking, and vector insertion in the background
    background_tasks.add_task(
        process_media_item_background,
        item_id=item_id,
        item_name=item_name,
        file_path=file_path,
        overview=overview
    )

    return {
        "status": "success",
        "message": "Media indexing pipeline triggered successfully",
        "item_id": item_id,
        "item_name": item_name
    }


@search_router.post("", response_model=SearchResponse)
async def search_media(query: SearchQuery):
    """
    Performs semantic vector similarity search across indexed media subtitle chunks.
    """
    if not query.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    query_embedding = get_embedding(query.query)
    results = search_similar_chunks(
        query_embedding=query_embedding,
        top_k=query.top_k,
        item_id=query.item_id,
        query_text=query.query
    )

    formatted_results = [
        SearchResultItem(
            id=r.get("id"),
            item_id=r["item_id"],
            item_name=r.get("item_name"),
            text=r["text"],
            start_time=r["start_time"],
            end_time=r["end_time"],
            score=r["score"]
        )
        for r in results
    ]

    return SearchResponse(query=query.query, results=formatted_results)

