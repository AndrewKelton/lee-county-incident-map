import sys

from ingest import build_geocoding, build_store, geocode_pending


def backfill(limit: int = 150):
    stats = geocode_pending(build_store(), build_geocoding(), limit)
    print(f"Backfill: {stats}")

if __name__ == "__main__":
    backfill(int(sys.argv[1]) if len(sys.argv) > 1 else 150)