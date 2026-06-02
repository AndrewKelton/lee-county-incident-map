from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from adapters.lee_county import LeeCountyAdapter
from adapters.lee_county_traffic import LeeCountyTrafficAdapter
from models import NormalizedIncident
from store.sqlite import SqliteStore
from geocoding.census import CensusGeocoder
from geocoding.sqlite_cache import SqliteCache
from geocoding.service import GeocodingService

REGISTRY = {
    "lee_county": LeeCountyAdapter,
    "lee_county_traffic": LeeCountyTrafficAdapter,
}

def build_store():
    return SqliteStore()

def build_geocoding():
    return GeocodingService(
        geocoder=CensusGeocoder(),
        cache=SqliteCache(),
    )

def run_source(name: str) -> dict:
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown source: {name!r}. Available: {sorted(REGISTRY)}"
        )

    adapter = REGISTRY[name]()
    store = build_store()
    geocoding = build_geocoding()
    fetched_at = datetime.now(timezone.utc)

    print(f"[{name}] fetching...")
    raw_records = adapter.fetch_raw()
    print(f"[{name}] fetched {len(raw_records)} records")

    incidents = [adapter.normalize(r, fetched_at) for r in raw_records]

    def _try_geocode(geocoding: GeocodingService, incident: NormalizedIncident):
        try:
            return incident, geocoding.geocode(incident.address, incident.city)
        except Exception as e:
            print(f"    geocode failed for incident {incident.source_incident_id}: {e}")
            return incident, None

    to_geocode = [
        i for i in incidents
        if i.lat is None and i.address and i.city
    ]
    print(f"[{name}] geocoding {len(to_geocode)} records concurrently…")

    geocoded = 0
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(_try_geocode, geocoding, i) for i in to_geocode]
        for future in as_completed(futures):
            incident, result = future.result()
            if result:
                incident.lat, incident.lon, incident.geocode_quality = result
                incident.geocoded_at = datetime.now(timezone.utc)
                geocoded += 1

    print(f"[{name}] geocoded {geocoded} records (of {len(to_geocode)} attempted)")

    print(f"[{name}] upserting...")
    counts = store.upsert(incidents)
    print(f"[{name}] done: {counts}")

    return counts

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: uv run python runner.py <source_name>")
        sys.exit(1)
    run_source(sys.argv[1])