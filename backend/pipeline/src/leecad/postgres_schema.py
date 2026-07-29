from collections.abc import Iterable

import psycopg


class DatabaseSchemaError(RuntimeError):
    """Raised when required Alembic-managed tables are unavailable."""


def require_tables(conn: psycopg.Connection, tables: Iterable[str]) -> None:
    required = set(tables)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (sorted(required),),
        )
        available = {row[0] for row in cur.fetchall()}

    missing = sorted(required - available)
    if missing:
        names = ", ".join(missing)
        raise DatabaseSchemaError(
            f"PostgreSQL schema is not migrated; missing public tables: {names}. "
            "Apply the Alembic migrations before starting the pipeline."
        )
