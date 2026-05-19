"""Constants for the .vcs directory structure."""

import os

VCS_DIR = ".vcs"
OBJECTS_DIR = "objects"
REFS_DIR = "refs"
REFS_HEADS = "refs/heads"
HEAD_FILE = "HEAD"
INDEX_FILE = "index"

# Full paths relative to repo root
def vcs_path(*parts: str) -> str:
    return os.path.join(VCS_DIR, *parts)

def objects_path() -> str:
    return vcs_path(OBJECTS_DIR)

def refs_heads_path() -> str:
    return vcs_path(REFS_HEADS)

def head_path() -> str:
    return vcs_path(HEAD_FILE)

def index_path() -> str:
    return vcs_path(INDEX_FILE)
