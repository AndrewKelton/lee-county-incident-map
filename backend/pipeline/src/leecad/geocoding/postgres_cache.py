import threading
import psycopg

from leecad.geocoding.base import GeocodeCache
from leecad.postgres_schema import require_tables


class PostgresCache(GeocodeCache):
    def __init__(self, conn_string: str):
        self.conn = psycopg.connect(conn_string, autocommit=True)
        self._lock = threading.Lock()
        try:
            require_tables(self.conn, {"geocode_cache"})
        except Exception:
            self.conn.close()
            raise

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

    def get_many(self, keys):
        if not keys:
            return {}
        with self._lock:
            rows = self.conn.execute(
                "SELECT key, lat, lon, quality FROM geocode_cache WHERE key = ANY(%s)",
                (list(keys),),
            ).fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def set_many(self, entries):
        if not entries:
            return
        keys = list(entries)
        lats, lons, quals = ([v[i] for v in entries.values()] for i in range(3))
        # unnest(arrays) -> one statement, 4 params regardless of batch size.
        with self._lock:
            self.conn.execute(
                "INSERT INTO geocode_cache (key, lat, lon, quality) "
                "SELECT * FROM unnest(%s::text[], %s::float8[], %s::float8[], %s::text[]) "
                "ON CONFLICT (key) DO UPDATE SET lat=EXCLUDED.lat, lon=EXCLUDED.lon, "
                "quality=EXCLUDED.quality, cached_at=now()",
                (keys, lats, lons, quals),
            )

    def close(self):
        self.conn.close()
