from datetime import datetime, timezone
from adapters.lee_county import LeeCountyAdapter
from adapters.lee_county_traffic import LeeCountyTrafficAdapter
from models import NormalizedIncident
from ingest import build_store

REGISTRY = {"lee_county": LeeCountyAdapter, "lee_county_traffic": LeeCountyTrafficAdapter}

def fetch_source(name: str) -> list[NormalizedIncident]:
    """Fetch + normalize one source (no persistence). Used by the fetch Lambdas (stash to S3)
    and by run_source (direct local upsert). fetched_at is stamped here, at fetch time, which
    the recency guard relies on."""
    if name not in REGISTRY:
        raise ValueError(f"Unknown source: {name!r}. Available: {sorted(REGISTRY)}")
    adapter = REGISTRY[name]()
    fetched_at = datetime.now(timezone.utc)
    return [adapter.normalize(r, fetched_at) for r in adapter.fetch_raw()]

def run_source(name: str) -> dict:
    """Fetch + normalize + upsert in one shot (local/manual harvest)."""
    incidents = fetch_source(name)
    counts = build_store().upsert(incidents)
    print(f"[{name}] {len(incidents)} fetched -> "
          f"{counts['inserted']} inserted, {counts['updated']} updated, {counts['skipped']} skipped")
    return counts

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m pipeline.runner <source_name>")
    run_source(sys.argv[1])