"""Single operational CLI for the leecad engine.

One-shot / local:
    leecad harvest <source>            fetch + normalize + upsert one feed
    leecad backfill [limit]            one geocoding pass over rows missing coordinates
    leecad smoke                       fetch the incidents feed, pretty-print samples
    leecad flush-s3                    drain the S3 live-feed buffer into the store (ops)

Long-running crawl workers (hourly outbox sync; see README "Bulk historical extraction"):
    leecad crawl init [seed_path]      create crawl schema + seed the street-query queue
    leecad crawl work <worker_id>      harvest worker loop
    leecad crawl geocode <worker_id>   geocoding worker loop
    leecad crawl test <worker_id>      bounded 2-tick smoke against the real API

Imports are deferred into each command so `leecad --help` stays instant and
commands only pay for what they use (e.g. boto3 only for flush-s3).
"""
import argparse
import json
import sys


def _cmd_harvest(args) -> None:
    from leecad.pipeline.runner import run_source
    run_source(args.source)


def _cmd_backfill(args) -> None:
    from leecad.ingest import build_geocoding, build_store, geocode_pending
    stats = geocode_pending(build_store(), build_geocoding(), worker_id="backfill", limit=args.limit)
    print(f"Backfill: {stats}")


def _cmd_smoke(args) -> None:
    from datetime import datetime, timezone
    from leecad.adapters.lee_county import LeeCountyAdapter

    adapter = LeeCountyAdapter()
    fetched_at = datetime.now(timezone.utc)
    raw = adapter.fetch_raw()

    print(f"Type: {type(raw).__name__}, Length: {len(raw) if hasattr(raw, '__len__') else 'N/A'}")
    print("\n--- First raw record ---")
    print(json.dumps(raw[0], indent=2))
    print("\n--- Normalized ---")
    print(adapter.normalize(raw[0], fetched_at).model_dump_json(indent=2))
    print("\n--- Last 3 normalized (sanity check timestamps & nulls) ---")
    for r in raw[-3:]:
        n = adapter.normalize(r, fetched_at)
        print(f"  {n.occurred_at}  {n.nature}  {n.city}")


def _cmd_flush_s3(args) -> None:
    import os
    from leecad.ingest import build_store
    from leecad.pipeline.flush import drain
    from leecad.pipeline.s3_buffer import S3Buffer  # boto3: dev dependency locally

    bucket = os.environ.get("S3_BUFFER_BUCKET")
    if not bucket:
        sys.exit("S3_BUFFER_BUCKET must be set.")
    store = build_store()
    try:
        stats = drain(S3Buffer(bucket), store)
    finally:
        store.close()
    print(stats)


def _connect_neon():
    import os
    import psycopg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("DATABASE_URL must be set (the Neon pooled connection string).")
    return psycopg.connect(db_url)


def _cmd_crawl(args) -> None:
    if args.crawl_cmd == "init":
        from pathlib import Path
        from leecad.crawl import coordinator
        from leecad.paths import STREET_QUERIES

        conn = _connect_neon()
        path = Path(args.seed) if args.seed else STREET_QUERIES
        coordinator.init_schema(conn)
        n = coordinator.seed(conn, path)
        print(f"schema ready; seeded {n} street queries")
    elif args.crawl_cmd == "work":
        from leecad.crawl.worker import run_harvest
        run_harvest(args.worker_id)
    elif args.crawl_cmd == "geocode":
        from leecad.sync.geocode_worker import run_geocode
        run_geocode(args.worker_id)
    elif args.crawl_cmd == "test":
        # Gentle smoke: 1 fetch/tick, 2 ticks — a full lease -> fetch -> flush cycle
        # with only ~2 real API requests ~60s apart (won't trip the burst limit).
        from leecad.crawl.worker import run_harvest
        run_harvest(args.worker_id, lease=1, period=60, jitter=0, max_ticks=2)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="leecad",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("harvest", help="fetch + normalize + upsert one feed")
    sp.add_argument("source", help="lee_county | lee_county_traffic")
    sp.set_defaults(fn=_cmd_harvest)

    sp = sub.add_parser("backfill", help="one geocoding pass over rows missing coordinates")
    sp.add_argument("limit", nargs="?", type=int, default=150)
    sp.set_defaults(fn=_cmd_backfill)

    sp = sub.add_parser("smoke", help="fetch the incidents feed and pretty-print samples")
    sp.set_defaults(fn=_cmd_smoke)

    sp = sub.add_parser("flush-s3", help="drain the S3 live-feed buffer into the store")
    sp.set_defaults(fn=_cmd_flush_s3)

    sp = sub.add_parser("crawl", help="bulk historical crawl (see README)")
    sp.set_defaults(fn=_cmd_crawl)
    csub = sp.add_subparsers(dest="crawl_cmd", required=True)
    c = csub.add_parser("init", help="create crawl schema + seed the street-query queue")
    c.add_argument("seed", nargs="?", help="seed list path (default: data/seeds/street_queries.txt)")
    for name, hlp in [
        ("work", "harvest worker loop"),
        ("geocode", "geocoding worker loop"),
        ("test", "bounded 2-tick harvest smoke"),
    ]:
        c = csub.add_parser(name, help=hlp)
        c.add_argument("worker_id")

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
