from ..common import create_oauth_decorator
from .client import NetatmoClient
from .queries import get_netatmo_account, update_netatmo_account

with_netatmo_client = create_oauth_decorator(
    create_client=lambda token: NetatmoClient(access_token=token),
    get_account=lambda account_id: get_netatmo_account(account_id=account_id),
    get_account_for_update=lambda account_id, for_update: get_netatmo_account(
        account_id=account_id, for_update=for_update
    ),
    update_account=lambda account, refresh_token, access_token, expires_at: (
        update_netatmo_account(
            account,
            refresh_token=refresh_token,
            access_token=access_token,
            expires_at=expires_at,
        )
    ),
)
"""
Decorator that injects a NetatmoClient and handles token refresh.

The decorated function must have an account_id keyword argument.
On ExpiredAccessToken, the token is refreshed and the function retried.
Because of this, decorated functions should be idempotent.
"""
