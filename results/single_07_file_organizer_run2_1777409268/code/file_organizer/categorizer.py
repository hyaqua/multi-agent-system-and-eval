"""Categorizer: assigns a category to each file based on extension, date, or size."""

import os.path
from datetime import datetime
from typing import Callable

from file_organizer.scanner import FileInfo

# ---------------------------------------------------------------------------
# Extension → category mapping
# ---------------------------------------------------------------------------
EXTENSION_MAP: dict[str, str] = {
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images",
    ".gif": "Images", ".bmp": "Images", ".svg": "Images",
    ".webp": "Images", ".tiff": "Images", ".tif": "Images",
    ".ico": "Images", ".heic": "Images", ".heif": "Images",
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".ppt": "Documents",
    ".pptx": "Documents", ".txt": "Documents", ".md": "Documents",
    ".csv": "Documents", ".json": "Documents", ".xml": "Documents",
    ".html": "Documents", ".htm": "Documents", ".css": "Documents",
    ".rtf": "Documents", ".odt": "Documents", ".ods": "Documents",
    ".odp": "Documents",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio",
    ".aac": "Audio", ".ogg": "Audio", ".wma": "Audio",
    ".m4a": "Audio", ".opus": "Audio",
    # Video
    ".mp4": "Video", ".avi": "Video", ".mkv": "Video",
    ".mov": "Video", ".wmv": "Video", ".flv": "Video",
    ".webm": "Video", ".m4v": "Video",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code",
    ".java": "Code", ".cpp": "Code", ".c": "Code",
    ".h": "Code", ".cs": "Code", ".rb": "Code",
    ".go": "Code", ".rs": "Code", ".sh": "Code",
    ".bat": "Code", ".ps1": "Code", ".sql": "Code",
    ".swift": "Code", ".kt": "Code", ".lua": "Code",
    ".r": "Code", ".pl": "Code", ".php": "Code",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".tar": "Archives",
    ".gz": "Archives", ".7z": "Archives", ".bz2": "Archives",
    ".xz": "Archives", ".tgz": "Archives",
}


def by_extension(info: FileInfo) -> str:
    """Return category string based on file extension."""
    return EXTENSION_MAP.get(info.ext, "Other")


# ---------------------------------------------------------------------------
# Date categorizer
# ---------------------------------------------------------------------------
def by_date(info: FileInfo) -> str:
    """Return 'YYYY/MM' based on modification time."""
    return info.mtime.strftime("%Y/%m")


# ---------------------------------------------------------------------------
# Size categorizer
# ---------------------------------------------------------------------------
# Thresholds in bytes
SIZE_SMALL = 1 * 1024 * 1024       # < 1 MB
SIZE_MEDIUM = 100 * 1024 * 1024    # < 100 MB


def by_size(info: FileInfo) -> str:
    """Return 'Small', 'Medium', or 'Large'."""
    if info.size < SIZE_SMALL:
        return "Small"
    if info.size < SIZE_MEDIUM:
        return "Medium"
    return "Large"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_categorizer(
    *,
    by_date_flag: bool = False,
    by_size_flag: bool = False,
) -> Callable[[FileInfo], str]:
    """Return the appropriate categorizer function given CLI flags.

    Only one of the flags is expected to be True.  If both are False the
    default extension-based categorizer is returned.
    """
    if by_date_flag:
        return by_date
    if by_size_flag:
        return by_size
    return by_extension
