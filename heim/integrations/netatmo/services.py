from .client import NetatmoClient

# Re-export the decorator for convenience
with_netatmo_client = NetatmoClient.with_client()
"""
Decorator that injects a NetatmoClient and handles token refresh.

The decorated function must have an account_id keyword argument.
On ExpiredAccessToken, the token is refreshed and the function retried.
Because of this, decorated functions should be idempotent.
"""
