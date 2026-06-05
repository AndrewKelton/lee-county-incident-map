import os
import sys

import psycopg

from crawl import coordinator
from crawl.worker import worker_loop


def _connect() -> psycopg.Connection:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL must be set (the Neon pooled connection string).")
    return psycopg.connect(db_url)

def main(argv: list[str]) -> None:
    if len(argv) < 2:
        sys.exit("Usage: crawl_runner.py {init | work <worker_id> | reap}")
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
        print(f"reclaimed {coordinator.reap_stale(conn)} stale in_progress_queries")
    else:
        sys.exit(f"Unknown command: {cmd!r}")

if __name__ == "__main__":
    main(sys.argv)