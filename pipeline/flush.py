"""Drain the S3 buffer into Neon. The flush Lambda's core, kept separate from the handler
so it can be tested with a fake buffer."""
from models import NormalizedIncident


def drain(buffer, store) -> dict:
    """Read every pending object, upsert the incidents, then delete the objects we processed.

    - Incidents are sorted by `fetched_at` so the upsert's last-wins dedup keeps the freshest
      snapshot of each call (the traffic feed shows the same active call across many 5-min
      fetches as its status evolves); the recency guard then prevents any stale overwrite.
    - Crash-safe: objects are deleted only after a successful upsert, so a failed/retried flush
      reprocesses them (idempotent). Only the keys listed at the start are deleted, so objects
      written by a fetch Lambda *during* the flush survive to the next run.
    """
    keys = buffer.list_pending()
    if not keys:
        return {"objects": 0, "incidents": 0, "inserted": 0, "updated": 0, "skipped": 0}

    incidents = []
    for key in keys:
        incidents += [NormalizedIncident.model_validate(r) for r in buffer.get(key)]
    incidents.sort(key=lambda i: i.fetched_at)              # oldest -> newest

    counts = store.upsert(incidents)
    buffer.delete(keys)
    return {"objects": len(keys), "incidents": len(incidents), **counts}
