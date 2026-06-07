import os
import psycopg

from dotenv import load_dotenv

from paths import PROJECT_ROOT
from store.base import IncidentStore
from geocoding.service import GeocodingService
from geocoding.composite import CompositeGeocoder
from geocoding.census import CensusGeocoder
from geocoding.overpass import OverpassIntersectionGeocoder
from geocoding.nominatim import NominatimGeocoder

load_dotenv(PROJECT_ROOT / ".env")

CONNECTION_ERRORS = (psycopg.OperationalError, psycopg.InterfaceError)


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
        return {"attempted": 0, "resolved": 0, "cached": 0, "fresh": 0}

    # One batched claim -> batched cache lookup + parallel external geocode -> batched writes.
    # DB statements per pass: 1 claim + 1 cache get + <=1 cache set + <=1 mark_geocoded
    # + <=1 mark_attempt
    items = [(addr, city or "") for (_s, _sid, addr, city) in rows]
    outcomes = geocoding.geocode_batch(items)

    resolved_rows: list[tuple[str, str, float, float, str]] = []
    attempt_rows: list[tuple[str, str, int]] = []
    cached = 0
    for (source, sid, _addr, _city), (result, from_cache) in zip(rows, outcomes):
        if result:
            lat, lon, quality = result
            resolved_rows.append((source, sid, lat, lon, quality))
            cached += from_cache
            print(f"    ✓ {source}/{sid} [{quality}]")
        else:
            attempt_rows.append((source, sid, 1))

    store.mark_geocoded_batch(resolved_rows)
    store.mark_geocode_attempt_batch(attempt_rows)

    resolved = len(resolved_rows)
    return {"attempted": len(rows), "resolved": resolved, "cached": cached, "fresh": resolved - cached}