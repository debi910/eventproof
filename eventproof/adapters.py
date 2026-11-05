from typing import Any

import httpx


async def open_meteo_weather(latitude: float, longitude: float, date: str) -> dict[str, Any]:
    """Optional adapter; callers should treat network errors as unavailable evidence."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": date,
        "end_date": date,
        "daily": "weather_code",
    }
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return {"provider": "Open-Meteo", "available": True, "data": response.json()}


async def gdacs_events() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get("https://www.gdacs.org/gdacsapi/api/events/geteventlist/ALL")
        response.raise_for_status()
        return {"provider": "GDACS", "available": True, "data": response.json()}
