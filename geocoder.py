import httpx
import logging

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "waze-clone-study/1.0 (educational project)"}


async def geocode(address: str, city: str = "Belo Horizonte") -> tuple[float, float] | None:
    
    query = f"{address}, {city}, Brasil"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "br",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(NOMINATIM_URL, params=params, headers=HEADERS)
            response.raise_for_status()
            results = response.json()

        if not results:
            logger.warning(f"Nenhum resultado para: {query}")
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
        logger.info(f"Geocoded '{query}' -> ({lat}, {lon})")
        return lat, lon

    except Exception as e:
        logger.error(f"Erro no geocoding: {e}")
        return None
