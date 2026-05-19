"""
Configuration for the REST API server.
"""

# Server settings
HOST = "127.0.0.1"
PORT = 8080

# Authentication token (Bearer token)
AUTH_TOKEN = "secret-token-12345"

# Data file for persisting items
DATA_FILE = "/tmp/items.json"

# Logging
LOG_FORMAT = "%(asctime)s - %(message)s"
