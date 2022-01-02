import httpx
import pytest

pytestmark = pytest.mark.asyncio


async def test_get_locations(
    authenticated_client: httpx.AsyncClient, location_id: int
) -> None:
    response = await authenticated_client.get("/api/locations")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1

    location = data[0]
    assert "id" in location
    assert location["id"] == location_id


async def test_get_locations_unauthenticated(
    client: httpx.AsyncClient, location_id: int
) -> None:
    response = await client.get("/api/locations")
    assert response.status_code == 401
