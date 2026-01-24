class NetatmoAPIError(Exception):
    pass


class ExpiredAccessToken(NetatmoAPIError):
    pass


class InvalidRefreshToken(NetatmoAPIError):
    pass
