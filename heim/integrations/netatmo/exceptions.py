class NetatmoAPIError(Exception):
    pass


class ExpiredAccessToken(NetatmoAPIError):
    pass


class InvalidGrant(NetatmoAPIError):
    """The authorization code or refresh token is invalid or expired."""

    pass


class InvalidRefreshToken(InvalidGrant):
    pass
