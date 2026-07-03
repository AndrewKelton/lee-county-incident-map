import random

# ---- Harvest ----
HARVEST_LEASE = 4                    # claim a whole hour's API budget at once
HARVEST_INTERVAL_SECONDS = 900       # 15 min between fetches -> ~4/hr, under the per-IP cap
TRUNCATED_AT = 1000                  # a full page means fan out

# ---- Geocode adaptive lease ----
GEOCODE_SEED_LEASE = 150             # first run / no history
GEOCODE_MIN_LEASE = 50
GEOCODE_MAX_LEASE = 2000
GEOCODE_GROWTH = 1.2

# ---- Sync cadence ----
SYNC_PERIOD_SECONDS = 3600           # one Neon session per hour
SYNC_JITTER_SECONDS = 300            # spread workers so they don't all hit Neon at once


def seconds_to_next_tick(now_ts: float,
                         period_s: int = SYNC_PERIOD_SECONDS,
                         max_jitter_s: int = SYNC_JITTER_SECONDS) -> float:
    """Delay until the next UTC period boundary (top of the hour for the default period) plus
    a little jitter. Aligning to UTC boundaries keeps every worker's Neon touch near xx:00."""
    base = period_s - (now_ts % period_s)
    return base + random.uniform(0, max_jitter_s)


def adaptive_geocode_lease(prev_processed: int) -> int:
    """Size the next lease from how much the worker actually got through last period: grow
    when it saturated the batch, shrink when it couldn't keep up. Bounded. Uses *processed*
    (resolved + attempted) so time spent on unresolvable addresses still counts as throughput."""
    if prev_processed <= 0:
        return GEOCODE_SEED_LEASE
    return max(GEOCODE_MIN_LEASE, min(GEOCODE_MAX_LEASE, round(prev_processed * GEOCODE_GROWTH)))
