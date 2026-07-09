"""Geocode worker, sync model: once an hour, flush last hour's results and lease the next
batch (sized adaptively); the rest of the hour, geocode offline against a prefetched cache
snapshot, buffering everything to the outbox.

Testable pieces:
  - geocode_tick(): the Neon session (flush, size lease, claim rows, prefetch cache)
  - process_geocode(): offline geocoding -> outbox ops (no Neon)
  - run_geocode(): the thin scheduling loop
"""
import time

from leecad.ingest import build_store, build_geocoding, CONNECTION_ERRORS
from leecad.paths import DATA_DIR
from leecad.sync.outbox import Outbox
from leecad.sync.flush import flush_geocode
from leecad.sync.schedule import (
    SYNC_PERIOD_SECONDS, SYNC_JITTER_SECONDS, seconds_to_next_tick, adaptive_geocode_lease,
)


def geocode_tick(store, geocoding, worker_id: str, outbox: Outbox):
    """Flush last period's results, size the next lease from throughput, claim that many
    ungeocoded rows, and prefetch their cache entries. Returns (rows, cached)."""
    stats = flush_geocode(outbox, store, geocoding)
    if stats["processed"]:
        print(f"[{worker_id}] flushed {stats}")
        outbox.set_state("last_processed", stats["processed"])
    basis = stats["processed"] or int(outbox.get_state("last_processed", 0) or 0)
    n = adaptive_geocode_lease(basis)

    rows = store.claim_ungeocoded(worker_id, n)
    keys = [geocoding._key(addr, city or "") for (_s, _sid, addr, city) in rows]
    cached = geocoding.cache.get_many(list(set(keys))) if keys else {}
    print(f"[{worker_id}] leased {len(rows)}/{n} ungeocoded ({len(cached)} cache prefetched)")
    return rows, cached


def process_geocode(geocoding, rows, cached, outbox: Outbox) -> None:
    """Offline: resolve the leased rows against the prefetched cache + external geocoders,
    buffering coords / attempts / new cache entries (no Neon)."""
    items = [(addr, city or "") for (_s, _sid, addr, city) in rows]
    outcomes, fresh = geocoding.geocode_batch_offline(items, cached)

    outbox.add_many("cache", [{"key": k, "lat": v[0], "lon": v[1], "quality": v[2]}
                              for k, v in fresh.items()])
    geocoded, attempts = [], []
    for (source, sid, _addr, _city), (result, _from_cache) in zip(rows, outcomes):
        if result:
            lat, lon, quality = result
            geocoded.append({"source": source, "sid": sid, "lat": lat, "lon": lon, "quality": quality})
        else:
            attempts.append({"source": source, "sid": sid, "n": 1})
    outbox.add_many("geocoded", geocoded)
    outbox.add_many("attempt", attempts)
    print(f"[geocode] {len(geocoded)} resolved, {len(attempts)} attempts buffered")


def _run_tick(worker_id: str, outbox: Outbox):
    """One Neon session, connections always closed before returning."""
    store = build_store()
    try:
        geocoding = build_geocoding()
    except BaseException:
        store.close()
        raise
    try:
        rows, cached = geocode_tick(store, geocoding, worker_id, outbox)
    finally:
        geocoding.cache.close()
        store.close()
    return rows, cached, geocoding   # geocoding reused offline (geocoder only; cache conn closed)


def _outbox_path(worker_id: str) -> str:
    return str(DATA_DIR / f"outbox_geocode_{worker_id}.db")


def run_geocode(worker_id: str, outbox_path: str | None = None, *,
                period: int = SYNC_PERIOD_SECONDS, jitter: int = SYNC_JITTER_SECONDS,
                max_ticks: int | None = None) -> None:
    outbox = Outbox(outbox_path or _outbox_path(worker_id))
    ticks = 0
    while True:
        try:
            rows, cached, geocoding = _run_tick(worker_id, outbox)
            if rows:
                process_geocode(geocoding, rows, cached, outbox)
        except CONNECTION_ERRORS as e:
            print(f"[{worker_id}] sync failed ({e}); outbox kept, retrying next tick")

        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            return
        time.sleep(seconds_to_next_tick(time.time(), period, jitter))
