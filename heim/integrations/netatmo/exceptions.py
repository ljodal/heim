from ..common.exceptions import ExpiredAccessToken as BaseExpiredAccessToken
from ..common.exceptions import IntegrationAPIError


class NetatmoAPIError(IntegrationAPIError):
    """Netatmo-specific API error."""

    pass


class ExpiredAccessToken(NetatmoAPIError, BaseExpiredAccessToken):
    """Netatmo access token has expired."""

    pass


class InvalidGrant(NetatmoAPIError):
    """The authorization code or refresh token is invalid or expired."""

    pass


class InvalidRefreshToken(InvalidGrant):
    """The refresh token is invalid or expired."""

    pass
