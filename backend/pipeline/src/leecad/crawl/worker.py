"""Harvest worker, sync model: claim a batch of queries, fetch them offline over the hour
buffering results to a local outbox, and touch Neon only at the hourly sync (flush + lease).

Split into testable pieces:
  - harvest_tick(): the Neon session (flush buffered ops, claim the next batch)
  - process_query(): one offline fetch -> outbox ops (no Neon)
  - run_harvest(): the loop that schedules ticks and paces fetches
"""
import os
import time
from datetime import datetime, timezone

import httpx

from leecad.adapters.lee_county import LeeCountyAdapter
from leecad.ingest import CONNECTION_ERRORS
from leecad.store.postgres import PostgresStore
from leecad.crawl import coordinator
from leecad.paths import DATA_DIR
from leecad.sync.outbox import Outbox
from leecad.sync.flush import flush_harvest
from leecad.sync.schedule import (
    HARVEST_LEASE, HARVEST_INTERVAL_SECONDS, TRUNCATED_AT,
    SYNC_PERIOD_SECONDS, SYNC_JITTER_SECONDS, seconds_to_next_tick,
)


def harvest_tick(store: PostgresStore, worker_id: str, outbox: Outbox,
                 lease: int = HARVEST_LEASE) -> list:
    """The hourly Neon session: flush last hour's buffered ops, then claim up to `lease`
    queries for the coming hour. Caller owns store's connection lifecycle. Postgres-only --
    the crawl_queries coordinator is Neon (SKIP LOCKED / unnest)."""
    stats = flush_harvest(outbox, store, store.conn)
    if any(stats.values()):
        print(f"[{worker_id}] flushed {stats}")
    return coordinator.claim_batch(store.conn, worker_id, lease)


def process_query(adapter, query: str, canonical: str, depth: int, outbox: Outbox,
                  truncated_at: int = TRUNCATED_AT) -> bool:
    """Fetch one query offline and buffer its results. Returns False if rate-limited (caller
    should stop fetching this period). On other failures the query is left leased (no finish
    op) so its lease expiry reclaims it for a later retry."""
    fetched_at = datetime.now(timezone.utc)
    try:
        raw = adapter.fetch_by_address(query)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 429:
            print(f"[harvest] 429 on {query!r}; backing off this period")
            return False
        if 500 <= code < 600:
            print(f"[harvest] {code} on {query!r}; leaving leased for retry")
            return True
        outbox.add("finish", {"query": query, "status": "failed", "error": f"HTTP {code}"})
        return True
    except (httpx.TransportError, httpx.TimeoutException) as e:
        print(f"[harvest] transient on {query!r}: {e}; leaving leased")
        return True

    incidents = [adapter.normalize(r, fetched_at) for r in raw]
    outbox.add_many("incident", [i.model_dump(mode="json") for i in incidents])
    if len(raw) >= truncated_at:
        outbox.add("fanout", {"parent": query, "canonical": canonical, "depth": depth})
        outbox.add("finish", {"query": query, "status": "truncated", "result_count": len(raw)})
    else:
        outbox.add("finish", {"query": query, "status": "done", "result_count": len(raw)})
    print(f"[harvest] {query!r} depth={depth} -> {len(raw)} rows buffered")
    return True


def _outbox_path(worker_id: str) -> str:
    return str(DATA_DIR / f"outbox_harvest_{worker_id}.db")


def run_harvest(worker_id: str, outbox_path: str | None = None, *, lease: int = HARVEST_LEASE,
                interval: float = HARVEST_INTERVAL_SECONDS, period: int = SYNC_PERIOD_SECONDS,
                jitter: int = SYNC_JITTER_SECONDS, max_ticks: int | None = None) -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL must be set for the crawl harvest worker")
    outbox = Outbox(outbox_path or _outbox_path(worker_id))
    adapter = LeeCountyAdapter()
    ticks = 0
    while True:
        try:                                   # the whole tick is one Neon session
            store = PostgresStore(db_url)
            try:
                claimed = harvest_tick(store, worker_id, outbox, lease)
            finally:
                store.close()
        except CONNECTION_ERRORS as e:
            print(f"[{worker_id}] sync failed ({e}); outbox kept, retrying next tick")
            claimed = []

        print(f"[{worker_id}] leased {len(claimed)} queries")
        for i, (query, canonical, depth) in enumerate(claimed):
            if i:
                time.sleep(interval)           # space fetches to respect the per-IP cap
            if not process_query(adapter, query, canonical, depth, outbox):
                break                          # throttled -> stop this period

        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            return
        time.sleep(seconds_to_next_tick(time.time(), period, jitter))
