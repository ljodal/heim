from ..common.exceptions import ExpiredAccessToken as BaseExpiredAccessToken
from ..common.exceptions import IntegrationAPIError


class AqaraAPIError(IntegrationAPIError):
    """Aqara-specific API error."""

    pass


class ExpiredAccessToken(AqaraAPIError, BaseExpiredAccessToken):
    """Aqara access token has expired."""

    pass
