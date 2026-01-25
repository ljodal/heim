class EaseeAPIError(Exception):
    """Base exception for Easee API errors."""


class ExpiredAccessToken(EaseeAPIError):
    """Access token has expired and needs to be refreshed."""


class InvalidCredentials(EaseeAPIError):
    """Invalid username or password."""


class InvalidRefreshToken(EaseeAPIError):
    """Refresh token is invalid or expired."""
