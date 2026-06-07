import httpx
import logging

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "movia-app/2.0 (educational project)"}


async def geocode(address: str, city: str = "Belo Horizonte") -> tuple[float, float] | None:

    # Tenta variações progressivamente menos restritivas
    queries = [
        f"{address}, {city}, Minas Gerais, Brasil",
        f"{address}, {city}, Brasil",
        f"{address}, Minas Gerais, Brasil",
        f"{address}, Brasil",
        address,
    ]

    async with httpx.AsyncClient(timeout=10.0) as client:
        for query in queries:
            params = {
                "q": query,
                "format": "json",
                "limit": 1,
                "countrycodes": "br",
                "addressdetails": 1,
            }
            try:
                response = await client.get(NOMINATIM_URL, params=params, headers=HEADERS)
                response.raise_for_status()
                results = response.json()

                if results:
                    lat = float(results[0]["lat"])
                    lon = float(results[0]["lon"])
                    logger.info(f"Geocoded '{query}' -> ({lat}, {lon})")
                    return lat, lon

                logger.info(f"Sem resultado para: {query}")

            except Exception as e:
                logger.error(f"Erro no geocoding ({query}): {e}")

    return None