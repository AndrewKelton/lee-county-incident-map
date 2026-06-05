import os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from models import NormalizedIncident
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

def geocode_and_upsert(
        incidents: list[NormalizedIncident],
        store: IncidentStore,
        geocoding: GeocodingService,
        label: str = ""):
    def _try(inc: NormalizedIncident) -> tuple[NormalizedIncident, tuple[GeocodeResult, bool]]:
        try:
            return inc, geocoding.geocode(inc.address or "", inc.city or "")
        except Exception as e:
            print(f"    geocode failed {inc.source_incident_id}: {e}")
            return inc, (None, False)

    to_geocode = [i for i in incidents if i.lat is None and i.address and i.city]
    cached = fresh = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_try, i) for i in to_geocode]
        for future in as_completed(futures):
            inc, (result, from_cache) = future.result()
            if result:
                inc.lat, inc.lon, inc.geocode = result
                inc.geocoded_at = datetime.now(timezone.utc)
                if from_cache:
                    cached += 1
                else:
                    fresh += 1

    if label:
        print(f"[{label}] geocoded {cached + fresh} ({cached} cached, {fresh} fresh)")
    return store.upsert(incidents)

