import os
import sys

import psycopg

from pathlib import Path
from paths import STREET_QUERIES

from crawl import coordinator
from crawl.worker import run_harvest
from sync.geocode_worker import run_geocode

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
    elif cmd == "work":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py work <worker_id>")
        run_harvest(argv[2])                       # harvest, hourly outbox sync
    elif cmd == "geocode":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py geocode <worker_id>")
        run_geocode(argv[2])                        # geocode, hourly outbox sync
    elif cmd == "test":
        if len(argv) != 3:
            sys.exit("Usage: crawl_runner.py test <worker_id>")
        # Gentle smoke: 1 fetch/tick, 2 ticks, so you see a full lease -> fetch -> (next tick)
        # flush cycle with only ~2 real API requests ~60s apart (won't trip the burst limit).
        run_harvest(argv[2], lease=1, period=60, jitter=0, max_ticks=2)
    else:
        sys.exit(f"Unknown command: {cmd!r}")

if __name__ == "__main__":
    main(sys.argv)
