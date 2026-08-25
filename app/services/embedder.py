from typing import List
import hashlib
import math
import random
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 768


def generate_dummy_vector(text: str, dimension: int = EMBEDDING_DIMENSION) -> List[float]:
    """
    Generates a deterministic, unit-normalized 768-dimensional float vector for a given text string.
    """
    if not text:
        return [0.0] * dimension

    # Derive seed deterministically from text hash for consistent embeddings
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    seed = int(text_hash[:16], 16)
    rng = random.Random(seed)

    raw_vector = [rng.gauss(0.0, 1.0) for _ in range(dimension)]
    
    # Normalize to unit vector for cosine similarity
    norm = math.sqrt(sum(x * x for x in raw_vector))
    if norm > 0.0:
        return [round(x / norm, 6) for x in raw_vector]
    return raw_vector


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Accepts text chunks and returns 768-dimensional vector embeddings.

    :param texts: List of text strings
    :return: List of 768-dimensional float vectors
    """
    if not texts:
        return []
    return [generate_dummy_vector(t, dimension=EMBEDDING_DIMENSION) for t in texts]


def get_embedding(text: str) -> List[float]:
    """
    Accepts a single text chunk and returns its 768-dimensional vector embedding.

    :param text: Text string
    :return: 768-dimensional float vector
    """
    return generate_dummy_vector(text, dimension=EMBEDDING_DIMENSION)


class EmbeddingService:
    """
    Embedding service generating 768-dimensional vectors for media chunks.
    """
    def __init__(self, dimension: int = EMBEDDING_DIMENSION):
        self.dimension = dimension

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return get_embeddings(texts)

    def get_embedding(self, text: str) -> List[float]:
        return get_embedding(text)


embedder = EmbeddingService()
