"""File extension and size category definitions."""

# Mapping of category names to sets of lowercase file extensions
EXTENSION_CATEGORIES: dict[str, set[str]] = {
    'Images': {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
        '.tiff', '.tif', '.ico', '.raw', '.heic', '.heif', '.psd',
        '.ai', '.eps', '.nef', '.cr2', '.dng',
    },
    'Documents': {
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.txt', '.md', '.rtf', '.csv', '.odt', '.ods', '.odp',
        '.pages', '.numbers', '.key', '.tex', '.log', '.rst',
    },
    'Audio': {
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
        '.opus', '.mid', '.midi', '.aiff', '.alac', '.ape',
    },
    'Video': {
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',
        '.mpg', '.mpeg', '.m4v', '.3gp', '.ogv', '.ts', '.vob',
    },
    'Code': {
        '.py', '.js', '.html', '.css', '.java', '.cpp', '.c',
        '.h', '.hpp', '.rs', '.go', '.ts', '.tsx', '.jsx',
        '.json', '.xml', '.yaml', '.yml', '.toml', '.ini',
        '.cfg', '.sh', '.bash', '.zsh', '.rb', '.php', '.swift',
        '.kt', '.scala', '.lua', '.r', '.sql', '.pl', '.pm',
        '.dockerfile', '.makefile', '.cmake', '.nim', '.zig',
        '.vue', '.svelte',
    },
    'Archives': {
        '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2', '.xz',
        '.tgz', '.tbz2', '.txz', '.lz', '.lz4', '.zst',
        '.tar.gz', '.tar.bz2', '.tar.xz',
    },
}

# Size thresholds in bytes
SIZE_CATEGORIES: list[tuple[str, int]] = [
    ('Small', 0),
    ('Medium', 1024 * 1024),       # 1 MB
    ('Large', 100 * 1024 * 1024),  # 100 MB
]


def get_category_by_extension(ext: str) -> str:
    """Return the category name for a given file extension.

    Checks compound extensions like .tar.gz first, then simple ones.
    Falls back to 'Other' if no match.
    """
    ext_lower = ext.lower()
    for category, extensions in EXTENSION_CATEGORIES.items():
        if ext_lower in extensions:
            return category
    # Check if it's a compound extension ending with a known compresion suffix
    for known_comp in ('.gz', '.bz2', '.xz', '.lz', '.lz4', '.zst'):
        if ext_lower.endswith(known_comp):
            return 'Archives'
    return 'Other'


def get_category_by_size(size: int) -> str:
    """Return the size category for a given file size in bytes."""
    if size < SIZE_CATEGORIES[1][1]:
        return 'Small'
    elif size < SIZE_CATEGORIES[2][1]:
        return 'Medium'
    else:
        return 'Large'
