"""
Utility functions for the distributed key-value store.

Provides logging configuration and address parsing helpers.
"""

import logging
import sys


def configure_logging(name: str, level: int = logging.INFO,
                      stream=sys.stdout) -> logging.Logger:
    """
    Configure and return a logger with a standard format.

    :param name: logger name
    :param level: logging level
    :param stream: output stream (default stdout)
    :return: configured Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
    return logger


def parse_address(address: str, default_port: int = 5555) -> tuple[str, int]:
    """
    Parse an address string like 'host:port' or 'host'.

    :param address: address string
    :param default_port: port to use if not specified
    :return: (host, port) tuple
    """
    if ":" in address:
        host, port_str = address.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = default_port
        return host, port
    return address, default_port
