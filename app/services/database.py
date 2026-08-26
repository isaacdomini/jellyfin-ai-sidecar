from typing import List, Dict, Any, Optional, Union
import logging
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Text,
    DateTime,
    func,
    text,
    select
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pgvector.sqlalchemy import Vector
from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class SubtitleChunk(Base):
    """
    SQLAlchemy model for subtitle chunks with a 768-dimensional pgvector column.
    """
    __tablename__ = "subtitle_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(255), index=True, nullable=False)
    item_name = Column(String(512), nullable=True)
    chunk_text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    embedding = Column(Vector(768), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Engine and Session factory using psycopg2
engine = create_engine(
    settings.get_database_url(),
    echo=settings.DEBUG,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Initializes PostgreSQL database: creates vector extension and tables.
    """
    logger.info("Initializing database and pgvector extension...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")


def get_db():
    """
    Dependency generator for database sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def insert_chunks(
    item_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
    item_name: Optional[str] = None
) -> int:
    """
    Inserts new subtitle chunks with pgvector embeddings into PostgreSQL.

    :param item_id: Unique identifier for the media item
    :param chunks: List of chunk dictionaries containing 'text', 'start_time', 'end_time'
    :param embeddings: List of 768-dimensional float vectors matching each chunk
    :param item_name: Optional display name for the media item
    :return: Number of chunks inserted
    """
    if not chunks or not embeddings or len(chunks) != len(embeddings):
        logger.warning(f"No chunks or embeddings to insert for item {item_id}, or length mismatch.")
        return 0

    session: Session = SessionLocal()
    try:
        # Remove any previous chunks for this media item when re-indexing
        session.query(SubtitleChunk).filter(SubtitleChunk.item_id == item_id).delete()

        records = [
            SubtitleChunk(
                item_id=item_id,
                item_name=item_name,
                chunk_text=chunk["text"],
                start_time=float(chunk["start_time"]),
                end_time=float(chunk["end_time"]),
                embedding=embedding
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        session.bulk_save_objects(records)
        session.commit()
        logger.info(f"Successfully inserted {len(records)} subtitle chunks for item '{item_id}'")
        return len(records)
    except Exception as e:
        session.rollback()
        logger.error(f"Error inserting chunks for item {item_id}: {e}", exc_info=True)
        raise
    finally:
        session.close()


def search_similar_chunks(
    query_embedding: List[float],
    top_k: int = 15,
    item_id: Optional[Union[str, List[str]]] = None,
    query_text: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Searches for the most relevant subtitle chunks using Hybrid Search:
    combining pgvector cosine semantic similarity and exact keyword/entity matching.

    :param query_embedding: 768-dimensional query vector
    :param top_k: Maximum number of results to return (default: 15)
    :param item_id: Optional filter for a specific media item ID or list of IDs
    :param query_text: Optional raw text query for keyword boosting/filtering
    :return: List of result dictionaries with similarity score and timestamp info
    """
    session: Session = SessionLocal()
    try:
        from sqlalchemy import or_
        seen_ids = set()
        formatted_results = []

        # Resolve filter IDs
        filter_ids = []
        if item_id:
            if isinstance(item_id, list):
                filter_ids = [str(x).strip() for x in item_id if str(x).strip()]
            elif isinstance(item_id, str):
                filter_ids = [x.strip() for x in item_id.split(",") if x.strip()]

        # 1. Keyword search boost if specific query phrases/words exist
        if query_text and len(query_text.strip()) > 2:
            cleaned_query = query_text.strip()
            # Search for full phrase or prominent keywords
            keyword_filters = [SubtitleChunk.chunk_text.ilike(f"%{cleaned_query}%")]
            # Also check individual words if phrase is longer
            words = [w for w in cleaned_query.split() if len(w) >= 4 and w.lower() not in {"what", "when", "where", "which", "about", "could", "would", "their", "there"}]
            for w in words[:3]:
                keyword_filters.append(SubtitleChunk.chunk_text.ilike(f"%{w}%"))

            kw_stmt = select(SubtitleChunk).where(or_(*keyword_filters))
            if filter_ids:
                if len(filter_ids) == 1:
                    kw_stmt = kw_stmt.where(SubtitleChunk.item_id == filter_ids[0])
                else:
                    kw_stmt = kw_stmt.where(SubtitleChunk.item_id.in_(filter_ids))
            kw_stmt = kw_stmt.limit(top_k)
            kw_results = session.execute(kw_stmt).scalars().all()

            for chunk in kw_results:
                seen_ids.add(chunk.id)
                formatted_results.append({
                    "id": chunk.id,
                    "item_id": chunk.item_id,
                    "item_name": chunk.item_name,
                    "text": chunk.chunk_text,
                    "start_time": chunk.start_time,
                    "end_time": chunk.end_time,
                    "score": 0.99  # Direct keyword hit
                })

        # 2. Semantic vector search
        distance_expr = SubtitleChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = select(SubtitleChunk, distance_expr)
        if filter_ids:
            if len(filter_ids) == 1:
                stmt = stmt.where(SubtitleChunk.item_id == filter_ids[0])
            else:
                stmt = stmt.where(SubtitleChunk.item_id.in_(filter_ids))

        stmt = stmt.order_by(distance_expr.asc()).limit(top_k * 2)
        results = session.execute(stmt).all()

        for chunk, distance in results:
            if chunk.id in seen_ids:
                continue
            seen_ids.add(chunk.id)
            similarity = 1.0 - float(distance) if distance is not None else 0.0
            formatted_results.append({
                "id": chunk.id,
                "item_id": chunk.item_id,
                "item_name": chunk.item_name,
                "text": chunk.chunk_text,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "score": round(similarity, 4)
            })

            if len(formatted_results) >= top_k:
                break

        return formatted_results[:top_k]
    finally:
        session.close()


def get_library_stats() -> Dict[str, Any]:
    """
    Returns statistics about indexed media items and chunks in the vector database.
    """
    session: Session = SessionLocal()
    try:
        total_chunks = session.query(func.count(SubtitleChunk.id)).scalar() or 0
        total_items = session.query(func.count(func.distinct(SubtitleChunk.item_id))).scalar() or 0

        # Query items with chunk counts
        items_query = (
            session.query(
                SubtitleChunk.item_id,
                SubtitleChunk.item_name,
                func.count(SubtitleChunk.id).label("chunk_count"),
                func.max(SubtitleChunk.created_at).label("indexed_at")
            )
            .group_by(SubtitleChunk.item_id, SubtitleChunk.item_name)
            .order_by(func.max(SubtitleChunk.created_at).desc())
            .limit(100)
            .all()
        )

        items_list = [
            {
                "item_id": item.item_id,
                "item_name": item.item_name or "Unknown",
                "chunk_count": item.chunk_count,
                "indexed_at": item.indexed_at.isoformat() if item.indexed_at else None
            }
            for item in items_query
        ]

        return {
            "total_items": total_items,
            "total_chunks": total_chunks,
            "items": items_list
        }
    finally:
        session.close()


def clear_database() -> Dict[str, Any]:
    """
    Clears all indexed subtitle chunks and resets the database.
    """
    session: Session = SessionLocal()
    try:
        deleted_rows = session.query(SubtitleChunk).delete()
        session.commit()
        logger.info(f"Database cleared: removed {deleted_rows} chunks.")
        return {
            "status": "success",
            "message": f"Successfully cleared {deleted_rows} subtitle chunks from database.",
            "deleted_chunks": deleted_rows
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Error clearing database: {e}", exc_info=True)
        raise
    finally:
        session.close()


