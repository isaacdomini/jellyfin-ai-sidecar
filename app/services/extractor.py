import os
import glob
import json
import subprocess
import tempfile
import logging
from typing import Optional, List, Dict, Any, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

# Supported subtitle file extensions
SUBTITLE_EXTENSIONS = [".srt", ".vtt", ".ass", ".ssa", ".sub"]
ENGLISH_LANG_CODES = {"eng", "en", "english", "en-us", "en-gb", "en-ca"}


def is_english_identifier(lang_or_title: Optional[str]) -> bool:
    """
    Determines if a language tag or title string indicates English.
    """
    if not lang_or_title:
        return False
    val = lang_or_title.lower().strip()
    return val in ENGLISH_LANG_CODES or "english" in val or val.startswith("en-") or val.startswith("en_")


def probe_subtitle_streams(file_path: str) -> List[Dict[str, Any]]:
    """
    Probes embedded subtitle streams in a media file using ffprobe.
    Returns list of dicts with stream index, relative subtitle index, language tag, title, and flags.
    """
    if not os.path.exists(file_path):
        return []

    try:
        cmd = [
            settings.FFPROBE_PATH,
            "-v", "error",
            "-select_streams", "s",
            "-show_entries", "stream=index:stream_tags=language,title:stream_disposition=forced,hearing_impaired",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result.returncode != 0:
            logger.warning(f"ffprobe failed on {file_path}: {result.stderr}")
            return []

        data = json.loads(result.stdout)
        streams = data.get("streams", [])

        classified = []
        for rel_idx, stream in enumerate(streams):
            tags = stream.get("tags") or {}
            disposition = stream.get("disposition") or {}
            lang = tags.get("language", "und").lower()
            title = tags.get("title", "")
            is_forced = bool(disposition.get("forced", 0))
            is_sdh = bool(disposition.get("hearing_impaired", 0))

            classified.append({
                "stream_index": stream.get("index"),
                "relative_index": rel_idx,
                "language": lang,
                "title": title,
                "is_english": is_english_identifier(lang) or is_english_identifier(title),
                "is_forced": is_forced,
                "is_sdh": is_sdh
            })

        return classified
    except Exception as e:
        logger.warning(f"Failed to probe subtitle streams with ffprobe for {file_path}: {e}")
        return []


def find_external_subtitles_classified(media_file_path: str) -> List[Dict[str, Any]]:
    """
    Discovers all external subtitle files and classifies their language.
    """
    if not os.path.exists(media_file_path):
        return []

    base_dir = os.path.dirname(media_file_path)
    file_stem = os.path.splitext(os.path.basename(media_file_path))[0]

    all_files = []

    # Check same directory
    for ext in SUBTITLE_EXTENSIONS:
        all_files.extend(glob.glob(os.path.join(base_dir, f"{file_stem}*{ext}")))

    # Check Subs / Subtitles directories
    for sub_dir_name in ["Subs", "subs", "subtitles", "Subtitles"]:
        sub_dir = os.path.join(base_dir, sub_dir_name)
        if os.path.isdir(sub_dir):
            for ext in SUBTITLE_EXTENSIONS:
                all_files.extend(glob.glob(os.path.join(sub_dir, f"*{ext}")))

    classified = []
    seen = set()
    for f in all_files:
        if not os.path.isfile(f) or f in seen or os.path.getsize(f) == 0:
            continue
        seen.add(f)
        fname = os.path.basename(f).lower()
        parts = fname.replace(file_stem.lower(), "").split(".")
        
        is_eng = any(is_english_identifier(p) for p in parts)
        is_forced = "forced" in fname
        
        # Extract potential language code
        detected_lang = "eng" if is_eng else "und"
        for p in parts:
            if len(p) in (2, 3) and p.isalpha() and p != "srt":
                detected_lang = p
                if is_english_identifier(p):
                    is_eng = True
                break

        classified.append({
            "file_path": f,
            "filename": os.path.basename(f),
            "language": detected_lang,
            "is_english": is_eng,
            "is_forced": is_forced
        })

    return classified


def convert_to_srt(source_file_path: str) -> str:
    """
    Converts any subtitle file (.vtt, .ass, .ssa, etc.) to SRT format using FFmpeg.
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
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result.returncode != 0:
            logger.warning(f"FFmpeg subtitle conversion warning: {result.stderr}")

        if os.path.exists(temp_srt_path) and os.path.getsize(temp_srt_path) > 0:
            with open(temp_srt_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(temp_srt_path):
            os.remove(temp_srt_path)


def extract_embedded_stream_to_srt(file_path: str, relative_index: int = 0) -> str:
    """
    Extracts a specific embedded subtitle stream from a video container to SRT using FFmpeg.
    """
    with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp_file:
        temp_srt_path = tmp_file.name

    try:
        command = [
            settings.FFMPEG_PATH,
            "-y",
            "-i", file_path,
            "-map", f"0:s:{relative_index}",
            temp_srt_path
        ]
        logger.info(f"Extracting embedded subtitle stream 0:s:{relative_index} via FFmpeg: {' '.join(command)}")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result.returncode != 0:
            logger.warning(f"FFmpeg subtitle stream extraction warning: {result.stderr}")

        if os.path.exists(temp_srt_path) and os.path.getsize(temp_srt_path) > 0:
            with open(temp_srt_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""
    finally:
        if os.path.exists(temp_srt_path):
            os.remove(temp_srt_path)


def extract_best_single_subtitle(file_path: str) -> Tuple[str, str, bool]:
    """
    Extracts exactly ONE subtitle track per movie following the user requirements:
    1. Only ONE English subtitle track is used (picking standard full English dialogue, avoiding duplicate tracks).
    2. If no English subtitles exist at all, selects the best available foreign subtitle track so it can be translated.

    :param file_path: Path to the media video file or external subtitle file
    :return: (srt_content: str, language_code: str, is_english: bool)
    """
    if not os.path.exists(file_path):
        logger.error(f"Media file not found: {file_path}")
        return "", "none", False

    # If the file given is directly a subtitle file
    lower_path = file_path.lower()
    for ext in SUBTITLE_EXTENSIONS:
        if lower_path.endswith(ext):
            is_eng = is_english_identifier(os.path.basename(lower_path)) or "eng" in lower_path
            if lower_path.endswith(".srt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(), "eng" if is_eng else "und", is_eng
            return convert_to_srt(file_path), "eng" if is_eng else "und", is_eng

    # 1. Inspect External Subtitles
    external_subs = find_external_subtitles_classified(file_path)

    # Check for English external subtitles
    eng_externals = [s for s in external_subs if s["is_english"] and not s["is_forced"]]
    if not eng_externals:
        # Fallback to any English external (even if forced)
        eng_externals = [s for s in external_subs if s["is_english"]]

    if eng_externals:
        best_ext = eng_externals[0]["file_path"]
        logger.info(f"Selected single English external subtitle for {file_path}: {best_ext}")
        if best_ext.lower().endswith(".srt"):
            with open(best_ext, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), "eng", True
            return convert_to_srt(best_ext), "eng", True

    # 2. Inspect Embedded Subtitle Streams
    embedded_streams = probe_subtitle_streams(file_path)

    # Check for English embedded streams (prefer non-forced dialogue)
    eng_streams = [s for s in embedded_streams if s["is_english"] and not s["is_forced"]]
    if not eng_streams:
        eng_streams = [s for s in embedded_streams if s["is_english"]]

    if eng_streams:
        best_stream = eng_streams[0]
        logger.info(f"Selected single English embedded subtitle stream for {file_path} (relative index: 0:s:{best_stream['relative_index']})")
        content = extract_embedded_stream_to_srt(file_path, best_stream["relative_index"])
        if content.strip():
            return content, "eng", True

    # 3. If NO English subtitles exist, look for foreign external or embedded subtitles
    logger.info(f"No English subtitles found for {file_path}. Searching for foreign subtitles to translate...")

    # Check foreign external subtitles
    foreign_externals = [s for s in external_subs if not s["is_forced"]] or external_subs
    if foreign_externals:
        best_foreign = foreign_externals[0]
        logger.info(f"Found foreign external subtitle ({best_foreign['language']}) for {file_path}: {best_foreign['file_path']}")
        if best_foreign["file_path"].lower().endswith(".srt"):
            with open(best_foreign["file_path"], "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), best_foreign["language"], False
        return convert_to_srt(best_foreign["file_path"]), best_foreign["language"], False

    # Check foreign embedded streams
    foreign_streams = [s for s in embedded_streams if not s["is_forced"]] or embedded_streams
    if foreign_streams:
        best_foreign_stream = foreign_streams[0]
        logger.info(f"Found foreign embedded subtitle stream ({best_foreign_stream['language']}) at 0:s:{best_foreign_stream['relative_index']}")
        content = extract_embedded_stream_to_srt(file_path, best_foreign_stream["relative_index"])
        if content.strip():
            return content, best_foreign_stream["language"], False

    # Fallback to default 0:s:0 if ffprobe found nothing but ffmpeg might extract something
    logger.info(f"Attempting default 0:s:0 fallback extraction for {file_path}")
    content = extract_embedded_stream_to_srt(file_path, 0)
    return content, "und", False


def extract_subtitles(file_path: str, subtitle_index: int = 0) -> str:
    """
    Backward-compatible subtitle extraction helper.
    """
    content, _, _ = extract_best_single_subtitle(file_path)
    return content

