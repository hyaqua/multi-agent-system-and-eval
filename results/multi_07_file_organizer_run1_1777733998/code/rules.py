"""Rule functions returning a relative destination sub-path.

- ``get_ext_category(ext)``   → category name like 'Images'
- ``get_date_path(mtime)``    → 'YYYY/MM'
- ``get_size_category(size)`` → 'Small' / 'Medium' / 'Large'
"""

import datetime

# ---------------------------------------------------------------------------
# Extension → category mapping
# ---------------------------------------------------------------------------
_EXT_MAP = {
    # Images
    ".jpg": "Images",
    ".jpeg": "Images",
    ".png": "Images",
    ".gif": "Images",
    ".bmp": "Images",
    ".tiff": "Images",
    ".tif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".ico": "Images",
    ".heic": "Images",
    ".heif": "Images",
    ".raw": "Images",
    # Documents
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".odt": "Documents",
    ".ods": "Documents",
    ".odp": "Documents",
    ".txt": "Documents",
    ".md": "Documents",
    ".rst": "Documents",
    ".csv": "Documents",
    ".rtf": "Documents",
    ".pages": "Documents",
    ".numbers": "Documents",
    ".key": "Documents",
    # Audio
    ".mp3": "Audio",
    ".wav": "Audio",
    ".flac": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".wma": "Audio",
    ".m4a": "Audio",
    ".opus": "Audio",
    ".mid": "Audio",
    ".midi": "Audio",
    # Video
    ".mp4": "Video",
    ".mkv": "Video",
    ".avi": "Video",
    ".mov": "Video",
    ".wmv": "Video",
    ".flv": "Video",
    ".webm": "Video",
    ".m4v": "Video",
    ".mpg": "Video",
    ".mpeg": "Video",
    ".3gp": "Video",
    # Code
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".jsx": "Code",
    ".tsx": "Code",
    ".html": "Code",
    ".css": "Code",
    ".scss": "Code",
    ".less": "Code",
    ".json": "Code",
    ".xml": "Code",
    ".yaml": "Code",
    ".yml": "Code",
    ".toml": "Code",
    ".ini": "Code",
    ".cfg": "Code",
    ".c": "Code",
    ".cpp": "Code",
    ".cxx": "Code",
    ".h": "Code",
    ".hpp": "Code",
    ".java": "Code",
    ".kt": "Code",
    ".swift": "Code",
    ".go": "Code",
    ".rs": "Code",
    ".rb": "Code",
    ".php": "Code",
    ".sh": "Code",
    ".bash": "Code",
    ".zsh": "Code",
    ".ps1": "Code",
    ".bat": "Code",
    ".sql": "Code",
    ".r": "Code",
    ".lua": "Code",
    ".pl": "Code",
    ".dart": "Code",
    ".asm": "Code",
    ".s": "Code",
}


def get_ext_category(ext: str) -> str:
    """Return a human-readable category for the given lower-cased extension.

    Parameters
    ----------
    ext : str
        Lower-case extension including the leading dot, e.g. ``".jpg"``.

    Returns
    -------
    str
        One of ``Images``, ``Documents``, ``Audio``, ``Video``, ``Code``,
        or ``Other``.
    """
    return _EXT_MAP.get(ext, "Other")


def get_date_path(timestamp: float) -> str:
    """Return a ``YYYY/MM`` relative path derived from a modification timestamp.

    Parameters
    ----------
    timestamp : float
        ``os.stat_result.st_mtime`` value.

    Returns
    -------
    str
        Relative path like ``2025/03``.
    """
    dt = datetime.datetime.fromtimestamp(timestamp)
    return f"{dt.year:04d}/{dt.month:02d}"


def get_size_category(size: int) -> str:
    """Return a size category for the given file size in bytes.

    Thresholds
    ----------
    * Small  –  < 1 MB   (1 048 576 bytes)
    * Medium –  1 MB – 100 MB
    * Large  –  > 100 MB

    Parameters
    ----------
    size : int
        File size in bytes.

    Returns
    -------
    str
        ``Small``, ``Medium``, or ``Large``.
    """
    mb = size / (1024 * 1024)
    if mb < 1:
        return "Small"
    elif mb <= 100:
        return "Medium"
    else:
        return "Large"
