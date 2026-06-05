# scripts/backfill_geocode_postgres.py
import os
import sys
from datetime import datetime, timezone
import psycopg
from ingest import build_geocoding


def backfill(limit: int = 150):
    pg_url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(pg_url)
    geocoding = build_geocoding()            # Census → Overpass → Nominatim

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source, source_incident_id, address, city
            FROM incidents
            WHERE lat IS NULL AND address IS NOT NULL AND TRIM(address) != ''
            ORDER BY occurred_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    print(f"Attempting {len(rows)} records...")
    resolved = 0

    for source, sid, address, city in rows:
        result, from_cache = geocoding.geocode(address, city or "")
        if result:
            lat, lon, quality = result
            tag = "cached" if from_cache else "fresh"
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE incidents SET lat=%s, lon=%s, geocoded_at=%s, geocode_quality=%s "
                    "WHERE source=%s AND source_incident_id=%s",
                    (lat, lon, datetime.now(timezone.utc), quality, source, sid),
                )
            conn.commit()
            resolved += 1
            print(f"  ✓ {address!r:45s} -> ({lat:.5f}, {lon:.5f})  [{quality}, {tag}]")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM incidents "
            "WHERE lat IS NULL AND address IS NOT NULL AND TRIM(address) != ''"
        )
        remaining = cur.fetchone()[0]

    print(f"\nResolved {resolved}/{len(rows)} this run. {remaining} still need coordinates.")


if __name__ == "__main__":
    backfill(int(sys.argv[1]) if len(sys.argv) > 1 else 150)