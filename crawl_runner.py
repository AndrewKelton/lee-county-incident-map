import os
import sys
import time

import psycopg

from crawl import coordinator
from crawl.worker import worker_loop
from ingest import build_store, build_geocoding, geocode_pending

GEOCODE_BATCH = 150     # rows per pass


def _connect() -> psycopg.Connection:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL must be set (the Neon pooled connection string).")
    return psycopg.connect(db_url)

def main(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit("Usage: crawl_runner.py {init | work <worker_id> | geocode <worker_id> | reap}")
    cmd = argv[1]
    conn = _connect()

    if cmd == "init":
        coordinator.init_schema(conn)
        n = coordinator.seed(conn)
        print(f"schema ready; seeded {n} street queries")
    elif cmd == "work":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py work <worker_id>")
        worker_loop(conn, argv[2])
    elif cmd == "reap":
        print(f"reclaimed {coordinator.reap_stale(conn)} stale in_progress queries")
    elif cmd == "geocode":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py geocode <worker_id>")
        worker_id = argv[2]
        store = build_store()
        geocoding = build_geocoding()
        print(f"[{worker_id}] draining ungeocoded incidents")
        while True:
            stats = geocode_pending(store, geocoding, worker_id, limit=GEOCODE_BATCH)
            print(f"[{worker_id}] {stats}")
            if stats["attempted"] == 0:
                time.sleep(600)  # nothing pending; idle, then re-check
    else:
        sys.exit(f"Unknown command: {cmd!r}")

if __name__ == "__main__":
    main(sys.argv)