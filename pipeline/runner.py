from datetime import datetime, timezone
from adapters.lee_county import LeeCountyAdapter
from adapters.lee_county_traffic import LeeCountyTrafficAdapter
from ingest import build_store, build_geocoding, geocode_and_upsert

REGISTRY = {"lee_county": LeeCountyAdapter, "lee_county_traffic": LeeCountyTrafficAdapter}

def run_source(name: str) -> dict:
    if name not in REGISTRY:
        raise ValueError(f"Unknown source: {name!r}. Available: {sorted(REGISTRY)}")
    adapter = REGISTRY[name]()
    fetched_at = datetime.now(timezone.utc)
    incidents = [adapter.normalize(r, fetched_at) for r in adapter.fetch_raw()]
    return build_store().upsert(incidents)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: uv run python -m pipeline.runner <source_name>")
    run_source(sys.argv[1])