import sys
from datetime import datetime, timezone
from store.sqlite import SqliteStore
from ingest import build_geocoding


def backfill(limit: int = 150):
    store = SqliteStore()
    geocoding = build_geocoding()  # same Census → Overpass → Nominatim chain

    rows = store.conn.execute(
        """
        SELECT source, source_incident_id, address, city
        FROM incidents
        WHERE lat IS NULL AND address IS NOT NULL AND TRIM(address) != ''
        ORDER BY occurred_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    print(f"Attempting {len(rows)} records...")
    resolved = 0

    for source, sid, address, city in rows:
        result = geocoding.geocode(address, city or "")
        if result:
            lat, lon, quality = result
            store.conn.execute(
                "UPDATE incidents SET lat=?, lon=?, geocoded_at=?, geocode_quality=? "
                "WHERE source=? AND source_incident_id=?",
                (lat, lon, datetime.now(timezone.utc).isoformat(), quality, source, sid),
            )
            store.conn.commit()  # commit each so a crash mid-run loses nothing
            resolved += 1
            print(f"  ✓ {address!r:45s} -> ({lat:.5f}, {lon:.5f})  [{quality}]")

    remaining = store.conn.execute(
        "SELECT COUNT(*) FROM incidents "
        "WHERE lat IS NULL AND address IS NOT NULL AND TRIM(address) != ''"
    ).fetchone()[0]

    print(f"\nResolved {resolved}/{len(rows)} this run. {remaining} still need coordinates.")


if __name__ == "__main__":
    backfill(int(sys.argv[1]) if len(sys.argv) > 1 else 150)