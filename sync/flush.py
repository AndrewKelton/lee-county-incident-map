"""Drain a worker's outbox into Neon using the phase-② batch writes.

This is the ONLY place a sync worker writes to Neon. Crash-safety: we read up to a fixed
`max_id`, apply the grouped ops, and only delete them once every write succeeds. A failure
mid-flush leaves the ops in place, so the next sync re-applies them -- safe because every
write is an idempotent upsert on a stable key.
"""
from collections import defaultdict

from models import NormalizedIncident
from crawl import coordinator


def _grouped(outbox):
    ops = outbox.pending()
    if not ops:
        return None, {}
    groups = defaultdict(list)
    for _id, kind, payload in ops:
        groups[kind].append(payload)
    return ops[-1][0], groups   # (max_id, {kind: [payload, ...] in insertion order})


def flush_harvest(outbox, store, conn) -> dict:
    """Drain harvest ops: incidents -> upsert; fanout -> enqueue children; finish -> complete
    queries. Children and completions ride this batch (an hour's delay on 10 child addresses
    is irrelevant against a multi-week crawl)."""
    max_id, g = _grouped(outbox)
    if max_id is None:
        return {"incidents": 0, "finished": 0, "fanned_out": 0}

    incidents = [NormalizedIncident.model_validate(p) for p in g.get("incident", [])]
    if incidents:
        store.upsert(incidents)

    fanout = [(p["parent"], p["canonical"], p["depth"]) for p in g.get("fanout", [])]
    if fanout:
        coordinator.fanout_batch(conn, fanout)

    finishes = [(p["query"], p["status"], p.get("result_count"), p.get("error"))
                for p in g.get("finish", [])]
    if finishes:
        coordinator.finish_batch(conn, finishes)

    outbox.delete_through(max_id)
    return {"incidents": len(incidents), "finished": len(finishes), "fanned_out": len(fanout)}


def flush_geocode(outbox, store, geocoding) -> dict:
    """Drain geocode ops: cache -> set_many; geocoded -> mark_geocoded_batch; attempt ->
    mark_geocode_attempt_batch (sums per address). Returns `processed` (resolved + attempted)
    for the adaptive lease."""
    max_id, g = _grouped(outbox)
    if max_id is None:
        return {"processed": 0, "resolved": 0, "attempted": 0}

    # last-wins per key (later op overwrites earlier in insertion order)
    cache_entries = {p["key"]: (p["lat"], p["lon"], p["quality"]) for p in g.get("cache", [])}
    if cache_entries:
        geocoding.cache.set_many(cache_entries)

    geocoded = [(p["source"], p["sid"], p["lat"], p["lon"], p["quality"]) for p in g.get("geocoded", [])]
    if geocoded:
        store.mark_geocoded_batch(geocoded)

    attempts = [(p["source"], p["sid"], p["n"]) for p in g.get("attempt", [])]
    if attempts:
        store.mark_geocode_attempt_batch(attempts)

    outbox.delete_through(max_id)
    return {"processed": len(geocoded) + len(attempts),
            "resolved": len(geocoded), "attempted": len(attempts)}
