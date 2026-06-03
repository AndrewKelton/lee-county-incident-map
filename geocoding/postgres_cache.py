import threading
import psycopg

from geocoding.base import GeocodeCache


class PostgresCache(GeocodeCache):
    def __init__(self, conn_string: str):
        self.conn = psycopg.connect(conn_string, autocommit=True)
        self._lock = threading.Lock()
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS geocode_cache (
                    key       TEXT PRIMARY KEY,
                    lat       DOUBLE PRECISION NOT NULL,
                    lon       DOUBLE PRECISION NOT NULL,
                    quality   TEXT,
                    cached_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)

    def get(self, key):
        with self._lock:
            row = self.conn.execute(
                "SELECT lat, lon, quality FROM geocode_cache WHERE key = %s", (key,)
            ).fetchone()
            return tuple(row) if row else None

    def set(self, key, lat, lon, quality):
        with self._lock:
            self.conn.execute(
                "INSERT INTO geocode_cache (key, lat, lon, quality) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (key) DO UPDATE SET lat=EXCLUDED.lat, lon=EXCLUDED.lon, "
                "quality=EXCLUDED.quality, cached_at=now()",
                (key, lat, lon, quality),
            )