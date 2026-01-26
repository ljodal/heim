from .client import AqaraClient

# Re-export the decorator for convenience
with_aqara_client = AqaraClient.with_client()
"""
Decorator that injects an AqaraClient and handles token refresh.

The decorated function must have an account_id keyword argument.
On ExpiredAccessToken, the token is refreshed and the function retried.
Because of this, decorated functions should be idempotent.
"""
