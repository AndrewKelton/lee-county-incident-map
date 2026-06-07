import sqlite3
import threading
from pathlib import Path
from paths import GEOCODE_CACHE_DB

from .base import GeocodeCache

class SqliteCache(GeocodeCache):
    def __init__(self, path: str = None):
        path = Path(path) if path else GEOCODE_CACHE_DB
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS geocode_cache (
                key TEXT PRIMARY KEY,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                quality TEXT,
                cached_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def get(self, key: str) -> tuple[float, float, str] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT lat, lon, quality FROM geocode_cache WHERE key = ?", (key, )
            ).fetchone()
            return tuple(row) if row else None

    def set(self, key: str, lat: float, lon: float, quality: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO geocode_cache "
                "(key, lat, lon, quality, cached_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (key, lat, lon, quality),
            )
            self.conn.commit()

    def get_many(self, keys: list[str]) -> dict[str, tuple[float, float, str]]:
        if not keys:
            return {}
        keys = list(keys)
        placeholders = ",".join("?" * len(keys))
        with self._lock:
            rows = self.conn.execute(
                f"SELECT key, lat, lon, quality FROM geocode_cache WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def set_many(self, entries: dict[str, tuple[float, float, str]]) -> None:
        if not entries:
            return
        with self._lock:
            self.conn.executemany(
                "INSERT OR REPLACE INTO geocode_cache "
                "(key, lat, lon, quality, cached_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                [(k, lat, lon, q) for k, (lat, lon, q) in entries.items()],
            )
            self.conn.commit()
