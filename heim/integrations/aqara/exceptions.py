class AqaraAPIError(Exception):
    pass


class ExpiredAccessToken(AqaraAPIError):
    pass
