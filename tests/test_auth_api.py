import httpx
import pytest
from heim.auth.queries import get_session

pytestmark = pytest.mark.asyncio


async def test_get_token(
    client: httpx.AsyncClient, username: str, password: str, account_id: int
) -> None:
    """
    Test a successful token request with valid credentials.
    """

    response = await client.post(
        "/api/auth/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data

    assert "token_type" in data
    assert data["token_type"] == "bearer"

    assert await get_session(key=data["access_token"]) is not None


async def test_get_token_empty_body(client: httpx.AsyncClient, account_id: int) -> None:
    """
    Test a token request without any credentials
    """

    response = await client.post("/api/auth/token")
    assert response.status_code == 422


async def test_get_token_missing_username(
    client: httpx.AsyncClient, password: str, account_id: int
) -> None:
    """
    Test a token request without a username
    """

    response = await client.post("/api/auth/token", data={"password": password})
    assert response.status_code == 422


async def test_get_token_missing_password(
    client: httpx.AsyncClient, username: str, account_id: int
) -> None:
    """
    Test a token request without a password
    """

    response = await client.post("/api/auth/token", data={"username": username})
    assert response.status_code == 422


async def test_get_token_invalid_username(
    client: httpx.AsyncClient, password: str, account_id: int
) -> None:
    """
    Test a token request with a non-existing username
    """

    response = await client.post(
        "/api/auth/token", data={"username": "wrong", "password": password}
    )
    assert response.status_code == 400


async def test_get_token_invalid_password(
    client: httpx.AsyncClient, username: str, account_id: int
) -> None:
    """
    Test a token request with an incorrect password.
    """

    response = await client.post(
        "/api/auth/token", data={"username": username, "password": "wrong"}
    )
    assert response.status_code == 400
