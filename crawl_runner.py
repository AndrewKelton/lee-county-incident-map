import os
import sys
import time

import psycopg

from pathlib import Path
from paths import STREET_QUERIES

from crawl import coordinator
from crawl.worker import worker_loop, RECONNECT_PAUSE_SECONDS
from ingest import build_store, build_geocoding, geocode_pending, CONNECTION_ERRORS

GEOCODE_BATCH = 50     # rows per pass
TEST_MAX_REQUESTS = 8  # enough to truncate a busy arterial + chew a few children
TEST_INTERVAL_SECONDS = 360
DRAINED_SLEEP_SECONDS = 600

def _connect() -> psycopg.Connection:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL must be set (the Neon pooled connection string).")
    return psycopg.connect(db_url)

def main(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit("Usage: crawl_runner.py {init | work <worker_id> | geocode <worker_id> | test <worker_id>}")
    cmd = argv[1]

    if cmd == "init":
        conn = _connect()
        path = Path(argv[2]) if len(argv) > 2 else STREET_QUERIES
        coordinator.init_schema(conn)
        n = coordinator.seed(conn, path)
        print(f"schema ready; seeded {n} street queries")
    elif cmd == "test":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py test <worker_id>")
        worker_loop(_connect, argv[2], max_requests=TEST_MAX_REQUESTS, interval=TEST_INTERVAL_SECONDS)
    elif cmd == "work":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py work <worker_id>")
        worker_loop(_connect, argv[2])
    elif cmd == "geocode":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py geocode <worker_id>")
        worker_id = argv[2]
        store = build_store()
        geocoding = build_geocoding()
        print(f"[{worker_id}] draining ungeocoded incidents")
        while True:
            try:
                stats = geocode_pending(store, geocoding, worker_id, limit=GEOCODE_BATCH)
            except CONNECTION_ERRORS as e:
                print(f"[{worker_id}] DB connection lost ({e}); reconnecting...")
                time.sleep(RECONNECT_PAUSE_SECONDS)
                store = build_store()
                geocoding = build_geocoding()
                continue
            print(f"[{worker_id}] {stats}")
            if stats["attempted"] == 0:
                time.sleep(DRAINED_SLEEP_SECONDS)  # nothing pending; idle, then re-check
    else:
        sys.exit(f"Unknown command: {cmd!r}")

if __name__ == "__main__":
    main(sys.argv)