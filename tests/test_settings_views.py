"""Tests for the settings views."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from heim.accounts.utils import get_random_string
from heim.auth.models import Session
from heim.integrations.netatmo.queries import (
    create_netatmo_account,
    create_netatmo_sensor,
    get_netatmo_sensors,
)
from heim.integrations.netatmo.types import Module, Station, StationsDataResponse

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def browser_client(
    session: Session, httpx_transport: httpx.ASGITransport
) -> AsyncIterator[httpx.AsyncClient]:
    """Client with session cookie for browser-based views."""
    cookies = {"session_id": session.key}
    async with httpx.AsyncClient(
        transport=httpx_transport,
        base_url="http://test",
        cookies=cookies,
        follow_redirects=False,
    ) as c:
        yield c


@pytest.fixture
async def netatmo_account_id(connection: None, account_id: int) -> int:
    """Create a Netatmo account linked to the test account."""
    return await create_netatmo_account(
        account_id=account_id,
        access_token=get_random_string(32),
        refresh_token=get_random_string(32),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


@pytest.fixture
def mock_station() -> Station:
    """Create a mock Netatmo station for testing."""
    return Station(
        _id="70:ee:50:aa:bb:cc",
        type="NAMain",
        station_name="Test Station",
        home_name="Test Home",
        module_name="Indoor",
        data_type=["Temperature", "Humidity", "CO2", "Noise", "Pressure"],
        modules=[
            Module(
                _id="02:00:00:aa:bb:dd",
                type="NAModule1",
                module_name="Outdoor",
                data_type=["Temperature", "Humidity"],
            ),
            Module(
                _id="06:00:00:aa:bb:ee",
                type="NAModule3",
                module_name="Rain Gauge",
                data_type=["Rain"],
            ),
        ],
    )


class TestSettingsIndex:
    """Tests for the main settings index page."""

    async def test_settings_index_requires_auth(
        self, client: httpx.AsyncClient
    ) -> None:
        """Unauthenticated users are redirected to login."""
        response = await client.get("/settings/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login/"

    async def test_settings_index_shows_locations(
        self, browser_client: httpx.AsyncClient, location_id: int
    ) -> None:
        """Settings index shows configured locations."""
        response = await browser_client.get("/settings/")
        assert response.status_code == 200
        assert b"Test location" in response.content
        assert b"1 location configured" in response.content

    async def test_settings_index_shows_netatmo_not_connected(
        self, browser_client: httpx.AsyncClient, location_id: int
    ) -> None:
        """Settings index shows Netatmo as not connected when no account."""
        response = await browser_client.get("/settings/")
        assert response.status_code == 200
        assert b"Not connected" in response.content

    async def test_settings_index_shows_netatmo_connected(
        self,
        browser_client: httpx.AsyncClient,
        location_id: int,
        netatmo_account_id: int,
    ) -> None:
        """Settings index shows Netatmo as connected when account exists."""
        response = await browser_client.get("/settings/")
        assert response.status_code == 200
        assert b"Connected" in response.content


class TestNetatmoIndex:
    """Tests for the Netatmo settings page."""

    async def test_netatmo_index_requires_auth(self, client: httpx.AsyncClient) -> None:
        """Unauthenticated users are redirected to login."""
        response = await client.get("/settings/netatmo/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login/"

    async def test_netatmo_index_not_connected(
        self, browser_client: httpx.AsyncClient, location_id: int
    ) -> None:
        """Shows connect button when Netatmo not linked."""
        response = await browser_client.get("/settings/netatmo/")
        assert response.status_code == 200
        # Check for connect button (text varies)
        has_connect = (
            b"Connect Netatmo" in response.content
            or b"Connect with Netatmo" in response.content
        )
        assert has_connect
        assert b"Link your Netatmo account" in response.content

    async def test_netatmo_index_connected_no_sensors(
        self,
        browser_client: httpx.AsyncClient,
        location_id: int,
        netatmo_account_id: int,
    ) -> None:
        """Shows account status and empty sensors list."""
        response = await browser_client.get("/settings/netatmo/")
        assert response.status_code == 200
        assert b"Connected" in response.content
        assert b"Add Sensor" in response.content
        # Check for "No sensors" message (case insensitive)
        content_lower = response.content.lower()
        assert b"no sensors" in content_lower or b"not registered" in content_lower

    async def test_netatmo_index_with_sensors(
        self,
        browser_client: httpx.AsyncClient,
        account_id: int,
        location_id: int,
        netatmo_account_id: int,
    ) -> None:
        """Shows list of configured sensors."""
        # Create a sensor
        await create_netatmo_sensor(
            account_id=account_id,
            name="Test Sensor",
            location_id=location_id,
            module_type="NAMain",
            netatmo_id="70:ee:50:aa:bb:cc",
            station_id="70:ee:50:aa:bb:cc",
        )

        response = await browser_client.get("/settings/netatmo/")
        assert response.status_code == 200
        assert b"Test Sensor" in response.content
        assert b"NAMain" in response.content


class TestNetatmoDevices:
    """Tests for the Netatmo devices discovery page."""

    async def test_devices_requires_auth(self, client: httpx.AsyncClient) -> None:
        """Unauthenticated users are redirected to login."""
        response = await client.get(
            "/settings/netatmo/devices/", follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login/"

    async def test_devices_redirects_without_netatmo_account(
        self, browser_client: httpx.AsyncClient, location_id: int
    ) -> None:
        """Redirects to Netatmo index if no account linked."""
        response = await browser_client.get("/settings/netatmo/devices/")
        assert response.status_code == 303
        assert response.headers["location"] == "/settings/netatmo/"

    async def test_devices_shows_stations(
        self,
        browser_client: httpx.AsyncClient,
        location_id: int,
        netatmo_account_id: int,
        mock_station: Station,
    ) -> None:
        """Shows available Netatmo devices."""
        mock_response = StationsDataResponse(devices=[mock_station])

        with patch(
            "heim.frontend.settings._get_netatmo_stations",
            new_callable=AsyncMock,
            return_value=mock_response.devices,
        ):
            response = await browser_client.get("/settings/netatmo/devices/")

        assert response.status_code == 200
        assert b"Test Station" in response.content
        assert b"Indoor" in response.content
        assert b"Outdoor" in response.content
        assert b"Rain Gauge" in response.content

    async def test_devices_shows_add_forms(
        self,
        browser_client: httpx.AsyncClient,
        location_id: int,
        netatmo_account_id: int,
        mock_station: Station,
    ) -> None:
        """Shows add forms for each device."""
        mock_response = StationsDataResponse(devices=[mock_station])

        with patch(
            "heim.frontend.settings._get_netatmo_stations",
            new_callable=AsyncMock,
            return_value=mock_response.devices,
        ):
            response = await browser_client.get("/settings/netatmo/devices/")

        assert response.status_code == 200
        # Check that add buttons are present
        assert response.content.count(b'type="submit"') >= 3  # Main + 2 modules
        # Check location select is present
        assert b"Test location" in response.content

    async def test_devices_marks_registered_as_added(
        self,
        browser_client: httpx.AsyncClient,
        account_id: int,
        location_id: int,
        netatmo_account_id: int,
        mock_station: Station,
    ) -> None:
        """Shows 'Added' badge for already registered devices."""
        # Register the main station
        await create_netatmo_sensor(
            account_id=account_id,
            name="Indoor",
            location_id=location_id,
            module_type="NAMain",
            netatmo_id="70:ee:50:aa:bb:cc",
            station_id="70:ee:50:aa:bb:cc",
        )

        mock_response = StationsDataResponse(devices=[mock_station])

        with patch(
            "heim.frontend.settings._get_netatmo_stations",
            new_callable=AsyncMock,
            return_value=mock_response.devices,
        ):
            response = await browser_client.get("/settings/netatmo/devices/")

        assert response.status_code == 200
        assert b"Added" in response.content

    async def test_devices_no_locations_warning(
        self,
        browser_client: httpx.AsyncClient,
        account_id: int,
        netatmo_account_id: int,
        mock_station: Station,
    ) -> None:
        """Shows warning when no locations are configured."""
        mock_response = StationsDataResponse(devices=[mock_station])

        with patch(
            "heim.frontend.settings._get_netatmo_stations",
            new_callable=AsyncMock,
            return_value=mock_response.devices,
        ):
            response = await browser_client.get("/settings/netatmo/devices/")

        assert response.status_code == 200
        assert b"create a location" in response.content


class TestNetatmoAddDevice:
    """Tests for adding a Netatmo device as a sensor."""

    async def test_add_device_requires_auth(self, client: httpx.AsyncClient) -> None:
        """Unauthenticated users are redirected."""
        response = await client.post(
            "/settings/netatmo/devices/add/",
            data={
                "device_id": "70:ee:50:aa:bb:cc",
                "device_name": "Test",
                "module_type": "NAMain",
                "station_id": "70:ee:50:aa:bb:cc",
                "location_id": "1",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303

    async def test_add_device_success(
        self,
        browser_client: httpx.AsyncClient,
        account_id: int,
        location_id: int,
        netatmo_account_id: int,
    ) -> None:
        """Successfully adds a device as a sensor."""
        with patch("heim.frontend.settings.update_netatmo_sensor_data") as mock_task:
            # Mock the task scheduling
            mock_task.return_value.schedule = AsyncMock()

            response = await browser_client.post(
                "/settings/netatmo/devices/add/",
                data={
                    "device_id": "70:ee:50:aa:bb:cc",
                    "device_name": "My Indoor Sensor",
                    "module_type": "NAMain",
                    "station_id": "70:ee:50:aa:bb:cc",
                    "location_id": str(location_id),
                },
            )

        assert response.status_code == 303
        assert response.headers["location"] == "/settings/netatmo/"

        # Verify sensor was created
        sensors = await get_netatmo_sensors(account_id=account_id)
        assert len(sensors) == 1
        sensor_id, name, module_type = sensors[0]
        assert name == "My Indoor Sensor"
        assert module_type == "NAMain"

    async def test_add_device_missing_fields(
        self,
        browser_client: httpx.AsyncClient,
        location_id: int,
        netatmo_account_id: int,
    ) -> None:
        """Returns validation error when fields are missing."""
        response = await browser_client.post(
            "/settings/netatmo/devices/add/",
            data={
                "device_name": "Test",
                "location_id": str(location_id),
            },
        )
        assert response.status_code == 422


class TestNetatmoLink:
    """Tests for the Netatmo OAuth link endpoint."""

    async def test_link_requires_auth(self, client: httpx.AsyncClient) -> None:
        """Unauthenticated users are redirected."""
        response = await client.get("/settings/netatmo/link/", follow_redirects=False)
        assert response.status_code == 303

    async def test_link_redirects_to_netatmo(
        self, browser_client: httpx.AsyncClient, location_id: int
    ) -> None:
        """Redirects to Netatmo OAuth page."""
        response = await browser_client.get("/settings/netatmo/link/")
        assert response.status_code == 303
        location = response.headers["location"]
        assert "api.netatmo.com/oauth2/authorize" in location
        assert "client_id=" in location
        assert "scope=read_station" in location
