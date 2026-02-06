"""Easee API exceptions."""

from ..common import ExpiredAccessToken, IntegrationAPIError

# Re-export common exceptions
__all__ = [
    "EaseeAPIError",
    "ExpiredAccessToken",
    "InvalidCredentials",
    "InvalidRefreshToken",
]


class EaseeAPIError(IntegrationAPIError):
    """Base exception for Easee API errors."""


class InvalidCredentials(EaseeAPIError):
    """Invalid username or password."""


class InvalidRefreshToken(EaseeAPIError):
    """Refresh token is invalid or expired."""
