import os
import glob
import subprocess
import tempfile
import logging
from typing import Optional, List
from app.core.config import settings

logger = logging.getLogger(__name__)

# Supported subtitle file extensions
SUBTITLE_EXTENSIONS = [".srt", ".vtt", ".ass", ".ssa", ".sub"]


def find_external_subtitles(media_file_path: str) -> Optional[str]:
    """
    Looks for external subtitle files (.srt, .vtt, .ass, .ssa, .sub) associated with a media file.
    Checks for exact base name matches, language-tagged variations (e.g. .en.srt, .eng.vtt, .default.ass),
    or any subtitle files in the same directory or adjacent Subs/ folders.

    :param media_file_path: Path to the media file
    :return: Path to the best matching external subtitle file if found, else None
    """
    if not os.path.exists(media_file_path):
        return None

    # If the file itself is already a subtitle file
    lower_path = media_file_path.lower()
    for ext in SUBTITLE_EXTENSIONS:
        if lower_path.endswith(ext):
            return media_file_path

    base_dir = os.path.dirname(media_file_path)
    file_stem = os.path.splitext(os.path.basename(media_file_path))[0]

    # Generate patterns for all supported extensions
    candidate_patterns: List[str] = []
    for ext in SUBTITLE_EXTENSIONS:
        candidate_patterns.extend([
            os.path.join(base_dir, f"{file_stem}{ext}"),
            os.path.join(base_dir, f"{file_stem}.en{ext}"),
            os.path.join(base_dir, f"{file_stem}.eng{ext}"),
            os.path.join(base_dir, f"{file_stem}.default{ext}"),
            os.path.join(base_dir, f"{file_stem}.forced{ext}"),
            os.path.join(base_dir, f"{file_stem}*{ext}"),
        ])

    for pattern in candidate_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isfile(match) and os.path.getsize(match) > 0:
                logger.info(f"Found external subtitle file: {match}")
                return match

    # Also check for a 'Subs' or 'Subtitles' subfolder if present
    for subfolder_name in ["Subs", "subs", "subtitles", "Subtitles"]:
        subfolder_path = os.path.join(base_dir, subfolder_name)
        if os.path.isdir(subfolder_path):
            for ext in SUBTITLE_EXTENSIONS:
                sub_matches = (
                    glob.glob(os.path.join(subfolder_path, f"{file_stem}*{ext}")) +
                    glob.glob(os.path.join(subfolder_path, f"*{ext}"))
                )
                for match in sub_matches:
                    if os.path.isfile(match) and os.path.getsize(match) > 0:
                        logger.info(f"Found external subtitle file in subfolder: {match}")
                        return match

    return None


def convert_to_srt(source_file_path: str) -> str:
    """
    Converts any subtitle file (.vtt, .ass, .ssa, etc.) or embedded media stream to SRT format using FFmpeg.
    """
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp_file:
        temp_srt_path = tmp_file.name

    try:
        command = [
            settings.FFMPEG_PATH,
            "-y",
            "-i", source_file_path,
            temp_srt_path
        ]
        logger.info(f"Converting subtitle to SRT via FFmpeg: {' '.join(command)}")
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.returncode != 0:
            logger.warning(f"FFmpeg subtitle conversion warning (exit code {result.returncode}): {result.stderr}")

        if os.path.exists(temp_srt_path) and os.path.getsize(temp_srt_path) > 0:
            with open(temp_srt_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(temp_srt_path):
            os.remove(temp_srt_path)


def extract_subtitles(file_path: str, subtitle_index: int = 0) -> str:
    """
    Extracts subtitle text for a given media file in SRT format:
    1. Checks for external subtitle files (.srt, .vtt, .ass, .ssa, .sub).
       - If .srt, reads directly.
       - If .vtt/.ass/.ssa/.sub, converts to .srt via FFmpeg.
    2. If no external subtitle file is found, extracts the embedded subtitle stream from the video via FFmpeg.

    :param file_path: Path to the media file or subtitle file
    :param subtitle_index: Subtitle stream index for FFmpeg extraction (default 0)
    :return: Extracted SRT string content
    """
    if not os.path.exists(file_path):
        logger.error(f"Media file not found: {file_path}")
        raise FileNotFoundError(f"Media file not found: {file_path}")

    # Check for external subtitle files
    external_sub = find_external_subtitles(file_path)
    if external_sub and os.path.exists(external_sub):
        if external_sub.lower().endswith(".srt"):
            try:
                logger.info(f"Reading directly from external SRT file: {external_sub}")
                with open(external_sub, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if content.strip():
                    return content
            except Exception as err:
                logger.warning(f"Could not read external SRT {external_sub}: {err}. Falling back to FFmpeg.")
        else:
            try:
                logger.info(f"Converting external subtitle format ({external_sub}) to SRT via FFmpeg")
                converted = convert_to_srt(external_sub)
                if converted.strip():
                    return converted
            except Exception as err:
                logger.warning(f"Could not convert external subtitle {external_sub}: {err}. Falling back to FFmpeg.")

    # Fall back to FFmpeg embedded stream extraction from media file
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp_file:
        temp_srt_path = tmp_file.name

    try:
        # ffmpeg -y -i <file> -map 0:s:0 <temp_file.srt>
        command = [
            settings.FFMPEG_PATH,
            "-y",
            "-i", file_path,
            "-map", f"0:s:{subtitle_index}",
            temp_srt_path
        ]

        logger.info(f"Running FFmpeg subtitle extraction: {' '.join(command)}")
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg subtitle extraction failed (exit code {result.returncode}): {result.stderr}")
            raise RuntimeError(f"FFmpeg subtitle extraction failed: {result.stderr.strip()}")

        if not os.path.exists(temp_srt_path) or os.path.getsize(temp_srt_path) == 0:
            logger.warning(f"Extracted subtitle stream is empty for {file_path}")
            return ""

        with open(temp_srt_path, "r", encoding="utf-8", errors="ignore") as f:
            extracted_text = f.read()

        logger.info(f"Successfully extracted {len(extracted_text)} characters from {file_path}")
        return extracted_text

    finally:
        if os.path.exists(temp_srt_path):
            os.remove(temp_srt_path)


class MediaExtractor:
    """
    Service wrapper for media subtitle extraction.
    """
    def __init__(self, ffmpeg_path: Optional[str] = None):
        self.ffmpeg_path = ffmpeg_path or settings.FFMPEG_PATH

    def extract_subtitles(self, file_path: str, subtitle_index: int = 0) -> str:
        return extract_subtitles(file_path, subtitle_index=subtitle_index)
