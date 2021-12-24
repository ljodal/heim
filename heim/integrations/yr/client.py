import httpx


async def get_location_forecast(
    *, coordinate: tuple[float, float], if_modified_since: str | None = None
) -> httpx.Response:
    """
    Load the YR location forecast for a given coordinate. Note that the
    coordinate will be truncated to 4 decimals, as per YR's documentation.
    """

    latitude, longitude = coordinate

    # TODO: Set user agent property
    headers = {
        "User-Agent": "github.com/ljodal",
    }
    if if_modified_since:
        headers["If-Modified-Since"] = if_modified_since

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.met.no/weatherapi/locationforecast/2.0/complete",
            params={"lat": round(latitude, 4), "lon": round(longitude, 4)},
            headers=headers,
        )

        return response
