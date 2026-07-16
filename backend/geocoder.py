import json
import os
import time

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

CACHE_FILE = os.path.join(os.path.dirname(__file__), "geocode_cache.json")
RATE_LIMIT_SECONDS = 1.1  # Nominatim requires max 1 req/sec


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def geocode_incidents_cached(incidents: list[dict]) -> list[dict]:
    """Cache-only geocode — fast startup, no network calls.

    Addresses not in the cache get lat=None, lng=None.
    """
    cache = _load_cache()
    result = []
    for inc in incidents:
        key = f"{inc.get('address','').strip()}|{inc.get('city','').strip()}"
        lat, lng = cache.get(key, [None, None])
        result.append({**inc, "lat": lat, "lng": lng})
    return result


def geocode_incidents(incidents: list[dict]) -> list[dict]:
    """Add lat/lng to each incident dict. Uses a disk cache to avoid repeat lookups.

    Incidents that cannot be geocoded get lat=None, lng=None and are still included.
    """
    geolocator = Nominatim(user_agent="fort-myers-crime-map/1.0")
    cache = _load_cache()
    cache_dirty = False
    result = []

    for incident in incidents:
        address = incident.get("address", "").strip()
        city = incident.get("city", "").strip()
        cache_key = f"{address}|{city}"

        if cache_key in cache:
            lat, lng = cache[cache_key]
        else:
            query = f"{address}, {city}, FL, USA"
            lat, lng = None, None
            try:
                location = geolocator.geocode(query, timeout=10)
                if location:
                    lat, lng = location.latitude, location.longitude
            except (GeocoderTimedOut, GeocoderServiceError):
                pass

            cache[cache_key] = [lat, lng]
            cache_dirty = True
            # Save incrementally every 25 new lookups so progress survives restarts
            if sum(1 for v in cache.values() if v == [lat, lng]) % 25 == 0:
                _save_cache(cache)
                cache_dirty = False
            time.sleep(RATE_LIMIT_SECONDS)

        result.append({**incident, "lat": lat, "lng": lng})

    if cache_dirty:
        _save_cache(cache)

    return result
