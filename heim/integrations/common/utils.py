"""Common utility functions for integrations."""

import os


def getenv(key: str) -> str:
    """
    Get a required environment variable.

    Raises KeyError if the variable is not set.
    """
    if value := os.getenv(key):
        return value

    raise KeyError(f"Environment variable {key} not set")
