from typing import List, Dict, Any, Union
import os
import pysrt
from app.core.config import settings


def chunk_subtitles(
    srt_data: Union[str, pysrt.SubRipFile],
    chunk_size_seconds: float = None,
    overlap_seconds: float = None
) -> List[Dict[str, Any]]:
    """
    Time-based sliding window chunking using pysrt.
    Converts seconds to milliseconds and outputs overlapping chunks.

    :param srt_data: SRT content string, file path, or pysrt.SubRipFile instance
    :param chunk_size_seconds: Window duration in seconds (default: settings.CHUNK_SIZE_SECONDS)
    :param overlap_seconds: Window overlap in seconds (default: settings.CHUNK_OVERLAP_SECONDS)
    :return: List of overlapping chunk dictionaries with text, start_time, end_time (in seconds)
    """
    if chunk_size_seconds is None:
        chunk_size_seconds = float(settings.CHUNK_SIZE_SECONDS)
    if overlap_seconds is None:
        overlap_seconds = float(settings.CHUNK_OVERLAP_SECONDS)

    # Load subtitles with pysrt
    if isinstance(srt_data, pysrt.SubRipFile):
        subs = srt_data
    elif os.path.exists(str(srt_data)):
        subs = pysrt.open(str(srt_data), encoding="utf-8")
    else:
        subs = pysrt.from_string(str(srt_data))

    if not subs:
        return []

    # Convert seconds to milliseconds
    chunk_size_ms: int = int(chunk_size_seconds * 1000)
    overlap_ms: int = int(overlap_seconds * 1000)
    step_size_ms: int = max(100, chunk_size_ms - overlap_ms)

    # Sort subtitles by start timestamp in milliseconds
    sorted_items = sorted(subs, key=lambda s: s.start.ordinal)
    if not sorted_items:
        return []

    max_timestamp_ms: int = max(s.end.ordinal for s in sorted_items)
    current_start_ms: int = sorted_items[0].start.ordinal

    chunks: List[Dict[str, Any]] = []

    while current_start_ms <= max_timestamp_ms:
        current_end_ms: int = current_start_ms + chunk_size_ms

        # Collect subtitle items that overlap with the current time window in ms
        window_items = [
            item for item in sorted_items
            if item.start.ordinal < current_end_ms and item.end.ordinal > current_start_ms
        ]

        if window_items:
            combined_text = " ".join(
                item.text.replace("\n", " ").strip()
                for item in window_items
                if item.text.strip()
            )
            if combined_text:
                chunk_start_sec = window_items[0].start.ordinal / 1000.0
                chunk_end_sec = window_items[-1].end.ordinal / 1000.0
                
                chunks.append({
                    "text": combined_text,
                    "start_time": round(chunk_start_sec, 3),
                    "end_time": round(chunk_end_sec, 3),
                    "start_time_ms": window_items[0].start.ordinal,
                    "end_time_ms": window_items[-1].end.ordinal,
                    "item_count": len(window_items)
                })

        current_start_ms += step_size_ms

    # Deduplicate consecutive chunks with identical text content
    deduped_chunks: List[Dict[str, Any]] = []
    for chunk in chunks:
        if not deduped_chunks or deduped_chunks[-1]["text"] != chunk["text"]:
            deduped_chunks.append(chunk)

    return deduped_chunks


class SubtitleChunker:
    """
    Sliding window chunking helper using pysrt.
    """
    def __init__(self, chunk_size_seconds: float = None, overlap_seconds: float = None):
        self.chunk_size_seconds = chunk_size_seconds or float(settings.CHUNK_SIZE_SECONDS)
        self.overlap_seconds = overlap_seconds or float(settings.CHUNK_OVERLAP_SECONDS)

    def chunk_subtitles(self, srt_data: Union[str, pysrt.SubRipFile]) -> List[Dict[str, Any]]:
        return chunk_subtitles(
            srt_data,
            chunk_size_seconds=self.chunk_size_seconds,
            overlap_seconds=self.overlap_seconds
        )

