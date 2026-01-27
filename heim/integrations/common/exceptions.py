"""Common exception classes for integrations."""


class IntegrationAPIError(Exception):
    """Base exception for all integration API errors."""

    pass


class ExpiredAccessToken(IntegrationAPIError):
    """The OAuth access token has expired and needs to be refreshed."""

    pass
