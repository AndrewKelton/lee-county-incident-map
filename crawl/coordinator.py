from pathlib import Path

import psycopg

from paths import STREET_QUERIES

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

def init_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()

def seed(conn: psycopg.Connection, path: Path = STREET_QUERIES) -> int:
    names = [l.strip().upper() for l in path.read_text().splitlines() if l.strip()]
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
                WHERE status='pending'
                ORDER BY depth ASC, query ASC 
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING query, canonical, depth
            """,
            (worker_id,),
        )
        row = cur.fetchone()
    conn.commit()
    return row  # (query, canonical, depth) or None

def fan_out(conn: psycopg.Connection, parent: str, canonical: str, depth: int) -> None:
    children = [(f"{d} {parent}" if depth == 0 else f"{d}{parent}") for d in "0123456789"]
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO crawl_queries (query, parent_query, canonical, depth) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (query) DO NOTHING",
            [(c, parent, canonical, depth + 1) for c in children],
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