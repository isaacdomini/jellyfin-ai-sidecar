import os
import glob
import subprocess
import tempfile
import logging
from typing import Optional, List
from app.core.config import settings

logger = logging.getLogger(__name__)


def find_external_subtitles(media_file_path: str) -> Optional[str]:
    """
    Looks for external subtitle files (.srt) associated with a media file.
    Checks for exact base name matches, language-tagged variations (e.g. .en.srt, .eng.srt),
    or any .srt files in the same directory.

    :param media_file_path: Path to the media file
    :return: Path to the best matching external SRT file if found, else None
    """
    if not os.path.exists(media_file_path):
        return None

    # If the file itself is already an SRT file
    if media_file_path.lower().endswith(".srt"):
        return media_file_path

    base_dir = os.path.dirname(media_file_path)
    file_stem = os.path.splitext(os.path.basename(media_file_path))[0]

    # Priority candidates: exact stem match, english language extensions, etc.
    candidate_patterns = [
        os.path.join(base_dir, f"{file_stem}.srt"),
        os.path.join(base_dir, f"{file_stem}.en.srt"),
        os.path.join(base_dir, f"{file_stem}.eng.srt"),
        os.path.join(base_dir, f"{file_stem}.default.srt"),
        os.path.join(base_dir, f"{file_stem}.forced.srt"),
        os.path.join(base_dir, f"{file_stem}*.srt"),
    ]

    for pattern in candidate_patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isfile(match) and os.path.getsize(match) > 0:
                logger.info(f"Found external subtitle file: {match}")
                return match

    # Also check for a 'Subs' or 'Subtitles' subfolder if present
    for subfolder_name in ["Subs", "subtitles", "Subtitles"]:
        subfolder_path = os.path.join(base_dir, subfolder_name)
        if os.path.isdir(subfolder_path):
            sub_matches = glob.glob(os.path.join(subfolder_path, f"{file_stem}*.srt")) + glob.glob(os.path.join(subfolder_path, "*.srt"))
            for match in sub_matches:
                if os.path.isfile(match) and os.path.getsize(match) > 0:
                    logger.info(f"Found external subtitle file in subfolder: {match}")
                    return match

    return None


def extract_subtitles(file_path: str, subtitle_index: int = 0) -> str:
    """
    Extracts subtitle text for a given media file.
    1. Checks if the file is already an SRT file or if an external .srt file exists alongside the media.
    2. If no external SRT file is found, runs FFmpeg: ffmpeg -y -i <file> -map 0:s:<subtitle_index> <temp_file.srt>

    :param file_path: Path to the media file or SRT file
    :param subtitle_index: Subtitle stream index for FFmpeg extraction (default 0)
    :return: Extracted SRT string content
    """
    if not os.path.exists(file_path):
        logger.error(f"Media file not found: {file_path}")
        raise FileNotFoundError(f"Media file not found: {file_path}")

    # Check for existing external .srt file first
    external_srt = find_external_subtitles(file_path)
    if external_srt and os.path.exists(external_srt):
        try:
            logger.info(f"Reading directly from external subtitle file: {external_srt}")
            with open(external_srt, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if content.strip():
                return content
        except Exception as err:
            logger.warning(f"Could not read external SRT {external_srt}: {err}. Falling back to FFmpeg.")

    # Fall back to FFmpeg embedded stream extraction
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

        logger.info(f"Running ffmpeg command: {' '.join(command)}")
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
            logger.warning(f"Extracted subtitle file is empty for {file_path}")
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


