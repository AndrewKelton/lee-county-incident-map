import os
import json
import sqlite3
from datetime import datetime
from models import NormalizedIncident
from store.postgres import PostgresStore
from paths import INCIDENTS_DB, GEOCODE_CACHE_DB

PG_URL = os.environ["PG_URL"]

def _dt(s):
    return datetime.fromisoformat(s) if s else None

def migrate_incidents():
    src = sqlite3.connect(INCIDENTS_DB)
    src.row_factory = sqlite3.Row
    dest = PostgresStore(PG_URL)

    rows = src.execute("SELECT * FROM incidents").fetchall()
    print(f"Migrating {len(rows)} incidents...")

    batch, totals = [], {"inserted": 0, "updated": 0, "skipped": 0}
    for r in rows:
        batch.append(NormalizedIncident(
            source=r["source"],
            source_incident_id=r["source_incident_id"],
            occurred_at=_dt(r["occurred_at"]),
            fetched_at=_dt(r["fetched_at"]),
            lat=r["lat"], lon=r["lon"],
            nature=r["nature"], disposition=r["disposition"],
            address=r["address"], city=r["city"],
            geocoded_at=_dt(r["geocoded_at"]),
            geocode_quality=r["geocode_quality"],
            status=r["status"],
            raw=json.loads(r["raw"]),
        ))
        if len(batch) >= 500:
            for k, v in dest.upsert(batch).items():
                totals[k] += v
            batch = []
    if batch:
        for k, v in dest.upsert(batch).items():
            totals[k] += v

    print(f"Incidents done: {totals}")

def migrate_cache():
    import psycopg
    src = sqlite3.connect(GEOCODE_CACHE_DB)
    src.row_factory = sqlite3.Row
    rows = src.execute("SELECT key, lat, lon, quality FROM geocode_cache").fetchall()
    print(f"Migrating {len(rows)} cache entries...")

    dest = psycopg.connect(PG_URL, autocommit=True)
    dest.execute("""
        CREATE TABLE IF NOT EXISTS geocode_cache (
            key TEXT PRIMARY KEY,
            lat DOUBLE PRECISION NOT NULL,
            lon DOUBLE PRECISION NOT NULL,
            quality TEXT,
            cached_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    with dest.cursor() as cur:
        cur.executemany(
            "INSERT INTO geocode_cache (key, lat, lon, quality) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (key) DO NOTHING",
            [(r["key"], r["lat"], r["lon"], r["quality"]) for r in rows],
        )
    print("Cache done.")


if __name__ == "__main__":
    migrate_incidents()
    migrate_cache()
