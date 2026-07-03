from pathlib import Path

import psycopg

from leecad.paths import STREET_QUERIES

SCHEMA = """
    CREATE TABLE IF NOT EXISTS crawl_queries (
        query           TEXT PRIMARY KEY,
        parent_query    TEXT,
        canonical       TEXT NOT NULL,
        depth           INTEGER NOT NULL,
        status          TEXT NOT NULL DEFAULT 'pending', --pending|in_progress|done|truncated|failed
        worker_id       TEXT,
        started_at      TIMESTAMPTZ,
        completed_at    TIMESTAMPTZ,
        result_count    INTEGER,
        error_message   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_crawl_status     ON crawl_queries(status);
    CREATE INDEX IF NOT EXISTS idx_crawl_canonical  ON crawl_queries(canonical);
"""

STALE_AFTER_MINUTES = 240

def init_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()

def seed(conn: psycopg.Connection, path: Path = STREET_QUERIES) -> int:
    names = [line.strip().upper() for line in path.read_text().splitlines() if line.strip()]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO crawl_queries (query, canonical, depth) VALUES (%s, %s, 0) "
            "ON CONFLICT (query) DO NOTHING",
            [(n, n) for n in names],
        )
    conn.commit()
    return len(names)


def claim_next(conn: psycopg.Connection, worker_id: str) -> tuple[str, str, int] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_queries SET status='in_progress', worker_id=%s, started_at=now()
            WHERE query = (
                SELECT query FROM crawl_queries
                WHERE status = 'pending'
                    OR (status = 'in_progress' AND started_at < now() - make_interval(mins => %s))
                ORDER BY depth ASC, query ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1 
            ) 
            RETURNING query, canonical, depth
            """,
            (worker_id, STALE_AFTER_MINUTES),
        )
        row = cur.fetchone()
    conn.commit()
    return row # (query, canonical, depth) or None

def claim_batch(conn: psycopg.Connection, worker_id: str, limit: int) -> list[tuple[str, str, int]]:
    """Lease up to `limit` queries at once (the hourly-sync worker claims its whole hour's
    work in one statement). Same pending/stale rules and SKIP LOCKED as claim_next."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_queries SET status='in_progress', worker_id=%s, started_at=now()
            WHERE query IN (
                SELECT query FROM crawl_queries
                WHERE status = 'pending'
                    OR (status = 'in_progress' AND started_at < now() - make_interval(mins => %s))
                ORDER BY depth ASC, query ASC
                FOR UPDATE SKIP LOCKED
                LIMIT %s
            )
            RETURNING query, canonical, depth
            """,
            (worker_id, STALE_AFTER_MINUTES, limit),
        )
        rows = cur.fetchall()
    conn.commit()
    return rows  # list of (query, canonical, depth)

def _children(parent: str, canonical: str, depth: int) -> list[tuple[str, str, str, int]]:
    kids = [(f"{d} {parent}" if depth == 0 else f"{d}{parent}") for d in "0123456789"]
    return [(c, parent, canonical, depth + 1) for c in kids]

def fan_out(conn: psycopg.Connection, parent: str, canonical: str, depth: int) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO crawl_queries (query, parent_query, canonical, depth) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (query) DO NOTHING",
            _children(parent, canonical, depth),
        )
    conn.commit()

def fanout_batch(conn: psycopg.Connection, parents: list[tuple[str, str, int]]) -> None:
    """Enqueue children for many truncated queries in one statement. parents: (parent,
    canonical, depth)."""
    rows = [child for p, c, d in parents for child in _children(p, c, d)]
    if not rows:
        return
    queries, parent_qs, canons, depths = (list(col) for col in zip(*rows))
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO crawl_queries (query, parent_query, canonical, depth) "
            "SELECT * FROM unnest(%s::text[], %s::text[], %s::text[], %s::int[]) "
            "ON CONFLICT (query) DO NOTHING",
            (queries, parent_qs, canons, depths),
        )
    conn.commit()

def finish(
        conn: psycopg.Connection,
        query: str,
        status: str,
        result_count: int | None = None,
        error: str | None =None
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE crawl_queries SET status=%s, result_count=%s, error_message=%s, "
            "completed_at=now() WHERE query=%s",
            (status, result_count, error, query))
    conn.commit()

def finish_batch(conn: psycopg.Connection, rows: list[tuple[str, str, int | None, str | None]]) -> None:
    """Complete many queries in one statement. rows: (query, status, result_count, error)."""
    if not rows:
        return
    queries, statuses, counts, errors = (list(col) for col in zip(*rows))
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE crawl_queries AS c
            SET status = v.status, result_count = v.rc, error_message = v.err, completed_at = now()
            FROM unnest(%s::text[], %s::text[], %s::int[], %s::text[]) AS v(query, status, rc, err)
            WHERE c.query = v.query
            """,
            (queries, statuses, counts, errors),
        )
    conn.commit()

def requeue(conn: psycopg.Connection, query: str) -> None:   # release claim without completing (for example after 429)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE crawl_queries SET status='pending', worker_id=NULL, "
            "started_at=NULL WHERE query=%s",
            (query,)
        )
    conn.commit()

def reap_stale(conn: psycopg.Connection, older_than: str = "4 hours") -> int:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE crawl_queries SET status='pending', worker_id=NULL, started_at=NULL "
            "WHERE status='in_progress' AND started_at < now() - %s::interval",
            (older_than,)
        )
        n = cur.rowcount
    conn.commit()
    return n