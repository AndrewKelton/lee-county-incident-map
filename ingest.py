import os

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
    resolved = 0
    for source, sid, address, city in rows:
        result, _ = geocoding.geocode(address, city or "")
        if result:
            lat, lon, quality = result
            store.mark_geocoded(source, sid, lat, lon, quality)
            resolved += 1
        else:
            store.mark_geocode_attempt(source, sid)
    return {"attempted": len(rows), "resolved": resolved}