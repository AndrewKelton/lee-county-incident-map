import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from store.base import IncidentStore
from geocoding.service import GeocodingService
from geocoding.composite import CompositeGeocoder
from geocoding.census import CensusGeocoder
from geocoding.overpass import OverpassIntersectionGeocoder
from geocoding.nominatim import NominatimGeocoder

GeocodeResult = tuple[float, float, str] | None     # (lat, lon, quality) or None

def build_store() -> IncidentStore:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        from store.postgres import PostgresStore
        return PostgresStore(db_url)
    from store.sqlite import SqliteStore
    return SqliteStore()

def build_geocoding() -> GeocodingService:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        from geocoding.postgres_cache import PostgresCache
        cache = PostgresCache(db_url)
    else:
        from geocoding.sqlite_cache import SqliteCache
        cache = SqliteCache()
    return GeocodingService(
        geocoder=CompositeGeocoder([
            CensusGeocoder(), OverpassIntersectionGeocoder(), NominatimGeocoder()
        ]),
        cache=cache,
    )

def geocode_pending(store: IncidentStore, geocoding: GeocodingService, worker_id: str, limit: int = 150) -> dict[str, int]:
    rows = store.claim_ungeocoded(worker_id, limit)
    if not rows:
        return {"attempted": 0, "resolved": 0}

    def _try(row):
        source_, sid_, address_, city_ = row
        try:
            result_, from_cache_ = geocoding.geocode(address_, city_ or "")
            return row, result_, from_cache_
        except Exception as e:
            print(f"    geocode failed {sid_}: {e}")
            return row, None, None

    resolved = cached = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        for fut in as_completed([pool.submit(_try, r) for r in rows]):
            (source, sid, addr, city), result, from_cache = fut.result()
            if result:
                lat, lon, quality = result
                store.mark_geocoded(source, sid, lat, lon, quality)
                resolved += 1
                cached += from_cache
                print(f"    ✓ {source}/{sid} [{quality}]")
            else:
                store.mark_geocode_attempt(source, sid)
    return {"attempted": len(rows), "resolved": resolved, "cached": cached, "fresh": resolved - cached}