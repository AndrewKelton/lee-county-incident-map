from datetime import datetime, timezone
from leecad.adapters.lee_county import LeeCountyAdapter
from leecad.adapters.lee_county_traffic import LeeCountyTrafficAdapter
from leecad.models import NormalizedIncident
from leecad.ingest import build_store

REGISTRY = {"lee_county": LeeCountyAdapter, "lee_county_traffic": LeeCountyTrafficAdapter}

def fetch_source(name: str) -> list[NormalizedIncident]:
    """Fetch + normalize one source (no persistence). Used by the fetch Lambdas (stash to S3)
    and by run_source (direct local upsert). fetched_at is stamped here, at fetch time, which
    the recency guard relies on."""
    if name not in REGISTRY:
        raise ValueError(f"Unknown source: {name!r}. Available: {sorted(REGISTRY)}")
    adapter = REGISTRY[name]()
    fetched_at = datetime.now(timezone.utc)

    raw = adapter.fetch_raw()
    incidents, failed = [], []
    for record in raw:
        try:
            incidents.append(adapter.normalize(record, fetched_at))
        except Exception as exc:
            failed.append(exc)

    if failed:
        print(f"[{name}] skipped {len(failed)} of {len(raw)} records; first: {failed[0]!r}")
    if raw and not incidents:
        # A quiet feed returns nothing and that is fine. Every record failing means the upstream
        # shape changed, and returning an empty batch would hide that.
        raise RuntimeError(f"[{name}] all {len(raw)} records failed to normalize: {failed[0]!r}")

    return incidents

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
        sys.exit("Usage: uv run leecad harvest <source_name>")
    run_source(sys.argv[1])