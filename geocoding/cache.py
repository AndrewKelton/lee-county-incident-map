import sqlite3
import threading

from .base import GeocodeCache

class SqliteCache(GeocodeCache):
    def __init__(self, path: str = "geocode_cache.db"):
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

class PostgresCache(GeocodeCache):
    """TODO"""