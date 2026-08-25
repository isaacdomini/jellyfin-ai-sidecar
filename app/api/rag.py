from typing import List
import logging
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import (
    RagQueryRequest,
    RagQueryResponse,
    SearchResultItem,
    ProviderModelInfo
)
from app.services.embedder import get_embedding
from app.services.database import search_similar_chunks
from app.services.llm import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG & LLM"])


@router.post("/query", response_model=RagQueryResponse, status_code=status.HTTP_200_OK)
@router.post("/ask", response_model=RagQueryResponse, status_code=status.HTTP_200_OK)
async def query_rag(request: RagQueryRequest):
    """
    RAG Query Endpoint:
    1. Retrieves the top semantically matching subtitle chunks from the vector database.
    2. Formats retrieved media dialogues with exact timestamps.
    3. Prompts the configured LLM (OpenAI, Gemini, Claude, Groq, Ollama, Custom).
    4. Returns the AI response, exact timestamp citations, and player deep-links.
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty"
        )

    logger.info(
        f"Processing RAG query: '{request.query}' "
        f"(item_id={request.item_id}, top_k={request.top_k}, provider={request.provider})"
    )

    try:
        # Retrieve vector similarity search results with Hybrid Search
        query_embedding = get_embedding(request.query)
        raw_chunks = search_similar_chunks(
            query_embedding=query_embedding,
            top_k=request.top_k,
            item_id=request.item_id,
            query_text=request.query
        )

        formatted_chunks = [
            SearchResultItem(
                id=c.get("id"),
                item_id=c["item_id"],
                item_name=c.get("item_name"),
                text=c["text"],
                start_time=c["start_time"],
                end_time=c["end_time"],
                score=c["score"]
            )
            for c in raw_chunks
        ]
    except Exception as exc:
        logger.warning(f"Vector search warning (falling back to empty chunks): {exc}")
        formatted_chunks = []

    # Generate LLM response with timestamp citations
    rag_response = await llm_service.generate_rag_response(
        query=request.query,
        retrieved_chunks=formatted_chunks,
        provider=request.provider,
        api_key=request.api_key,
        model=request.model,
        base_url=request.base_url,
        temperature=request.temperature
    )

    return rag_response


@router.get("/providers", response_model=List[ProviderModelInfo], status_code=status.HTTP_200_OK)
async def get_providers():
    """
    Returns list of supported LLM providers, default models, and capability flags.
    """
    return llm_service.get_providers_info()
