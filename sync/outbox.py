import json
import sqlite3
from pathlib import Path


class Outbox:
    """Local, durable op log that lets a worker stay offline between hourly Neon syncs.

    Workers only ever *append* result-ops here (cheap, no network); the flush step
    (sync/flush.py) is the only thing that drains them to Neon. Because every op maps to an
    idempotent batch write, re-flushing after a crash is safe. Knows nothing about Neon.

    `sync_state` is a tiny key/value side table for things the loop must remember across
    restarts (e.g. the adaptive geocode lease size).
    """

    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS outbox(
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                kind       TEXT NOT NULL,
                payload    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sync_state(k TEXT PRIMARY KEY, v TEXT);
            """
        )
        self.conn.commit()

    def add(self, kind: str, payload: dict) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO outbox(kind, payload) VALUES (?, ?)", (kind, json.dumps(payload))
            )

    def add_many(self, kind: str, payloads: list[dict]) -> None:
        rows = [(kind, json.dumps(p)) for p in payloads]
        if not rows:
            return
        with self.conn:
            self.conn.executemany("INSERT INTO outbox(kind, payload) VALUES (?, ?)", rows)

    def pending(self) -> list[tuple[int, str, dict]]:
        """Every pending op in insertion order: (id, kind, payload). Ordering matters --
        a later 'incident' op for the same key must win at flush time."""
        return [
            (i, k, json.loads(p))
            for i, k, p in self.conn.execute("SELECT id, kind, payload FROM outbox ORDER BY id")
        ]

    def delete_through(self, max_id: int) -> None:
        """Drop ops with id <= max_id (called only after their Neon write succeeds)."""
        with self.conn:
            self.conn.execute("DELETE FROM outbox WHERE id <= ?", (max_id,))

    def count(self) -> int:
        return self.conn.execute("SELECT count(*) FROM outbox").fetchone()[0]

    def get_state(self, k: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT v FROM sync_state WHERE k = ?", (k,)).fetchone()
        return row[0] if row else default

    def set_state(self, k: str, v) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO sync_state(k, v) VALUES (?, ?) "
                "ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                (k, str(v)),
            )

    def close(self) -> None:
        self.conn.close()
