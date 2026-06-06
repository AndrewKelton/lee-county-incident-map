import random
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx
import psycopg

from adapters.lee_county import LeeCountyAdapter
from ingest import build_store, CONNECTION_ERRORS
from crawl import coordinator

INTERVAL_SECONDS = 900      # 15 min -> 4 req/hr
TRUNCATED_AT = 1000
THROTTLE_PAUSE_SECONDS = 60 * 60    # 429 -> wait for 60 min
IDLE_POLL_SECONDS = 60
RECONNECT_PAUSE_SECONDS = 5

def _backoff_seconds(attempt: int) -> float:
    return min(30.0 * (2 ** attempt), 600.0)    # 30 seconds -> 10 minute cap

def worker_loop(connect: Callable[[], psycopg.Connection], worker_id: str, *,
                max_requests: int | None = None, interval: float = INTERVAL_SECONDS) -> None:
    conn = connect()
    adapter = LeeCountyAdapter()
    store = build_store()
    transient_attempts = 0
    completed = 0

    while True:
        try:
            claimed = coordinator.claim_next(conn, worker_id)
            if claimed is None:
                time.sleep(IDLE_POLL_SECONDS)
                continue
            query, canonical, depth = claimed
            started = time.monotonic()

            try:
                raw = adapter.fetch_by_address(query)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 429:
                    coordinator.requeue(conn, query)
                    print(f"[{worker_id}] 429 throttled on {query!r}; pausing 90m")
                    time.sleep(THROTTLE_PAUSE_SECONDS)
                    continue
                if 500 <= status < 600:
                    coordinator.requeue(conn, query)
                    time.sleep(_backoff_seconds(transient_attempts))
                    transient_attempts += 1
                    continue
                coordinator.finish(conn, query, "failed", error=f"HTTP {status}")
                continue
            except (httpx.TransportError, httpx.TimeoutException) as e:
                coordinator.requeue(conn, query)
                print(f"[{worker_id}] transient on {query!r}: {e}")
                time.sleep(_backoff_seconds(transient_attempts))
                transient_attempts += 1
                continue
            transient_attempts = 0

            fetched_at = datetime.now(timezone.utc)
            incidents = [adapter.normalize(r, fetched_at) for r in raw]
            counts = store.upsert(incidents)

            if len(raw) >= TRUNCATED_AT:
                coordinator.fan_out(conn, query, canonical, depth)
                coordinator.finish(conn, query, "truncated", result_count=len(raw))
            else:
                coordinator.finish(conn, query, "done", result_count=len(raw))
            print(f"[{worker_id}] {query!r} depth={depth} -> {len(raw)} rows {counts}")
            completed += 1

            if max_requests is not None and completed >= max_requests:
                print(f"[{worker_id}] hit max_requests={max_requests}, stopping")
                return

            elapsed = time.monotonic() - started
            time.sleep(max(0.0, interval - elapsed) + random.uniform(0, 60))
        except CONNECTION_ERRORS as e:
            print(f"[{worker_id}] DB connection lost ({e}); reconnecting...")
            time.sleep(RECONNECT_PAUSE_SECONDS)
            conn = connect()
            store = build_store()