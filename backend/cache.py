import time
import threading

from scraper import fetch_incidents
from geocoder import geocode_incidents_cached

CACHE_TTL_SECONDS = 3600  # 1 hour

_lock = threading.Lock()
_cache: dict = {
    "incidents": [],
    "fetched_at": 0.0,
}


def get_incidents() -> list[dict]:
    """Return geocoded incidents, refreshing from source if cache is stale."""
    with _lock:
        age = time.time() - _cache["fetched_at"]
        if age < CACHE_TTL_SECONDS and _cache["incidents"]:
            return _cache["incidents"]

        raw = fetch_incidents()
        geocoded = geocode_incidents_cached(raw)
        _cache["incidents"] = geocoded
        _cache["fetched_at"] = time.time()
        return _cache["incidents"]
