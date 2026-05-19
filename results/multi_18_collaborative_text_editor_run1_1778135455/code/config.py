"""
Server configuration loader.
Reads a JSON config file defining rooms and their passwords.
"""

import json
import os
from typing import Dict


DEFAULT_CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "rooms": {
        "lobby": {"password": ""},
        "python_dev": {"password": "py123"},
        "writers_room": {"password": "write"},
    }
}


def load_config(path: str | None = None) -> dict:
    """Load server configuration from a JSON file.

    If the file doesn't exist, a default config is created.
    """
    filepath = path or DEFAULT_CONFIG_PATH

    if not os.path.exists(filepath):
        _write_default(filepath)
        return DEFAULT_CONFIG

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            config = json.load(f)
        if "rooms" not in config:
            config["rooms"] = {}
        return config
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load config ({e}), using defaults.")
        return DEFAULT_CONFIG


def _write_default(path: str):
    """Write the default configuration file."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"Created default config at {path}")
    except IOError as e:
        print(f"Warning: Could not write default config: {e}")


def get_room_password(config: dict, room: str) -> str | None:
    """Get the password for a room. Returns None if room doesn't exist."""
    rooms = config.get("rooms", {})
    if room not in rooms:
        return None
    return rooms[room].get("password", "")


def room_exists(config: dict, room: str) -> bool:
    return room in config.get("rooms", {})
