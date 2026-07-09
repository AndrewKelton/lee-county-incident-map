import psycopg
from psycopg.types.json import Jsonb
from leecad.models import NormalizedIncident
from leecad.store.base import IncidentStore, MAX_GEOCODE_ATTEMPTS, GEOCODE_LEASE_MINUTES

_ACCEPT_CHANGE = """(
        EXCLUDED.fetched_at > incidents.last_changed
    AND (incidents.status      IS DISTINCT FROM COALESCE(EXCLUDED.status, incidents.status)
      OR incidents.disposition IS DISTINCT FROM COALESCE(EXCLUDED.disposition, incidents.disposition))
    )"""

# {{values}} survives this f-string (escaped) for the per-call .format(values=...).
UPSERT_SQL = f"""
    INSERT INTO incidents
        (source, source_incident_id, occurred_at, fetched_at, last_changed, lat, lon,
         nature, disposition, address, city, geocoded_at, geocode_quality, status, raw)
    VALUES {{values}}
    ON CONFLICT (source, source_incident_id) DO UPDATE SET
        lat = COALESCE(incidents.lat, EXCLUDED.lat),
        lon = COALESCE(incidents.lon, EXCLUDED.lon),
        geocoded_at = CASE WHEN incidents.lat IS NULL
                           THEN EXCLUDED.geocoded_at ELSE incidents.geocoded_at END,
        geocode_quality = CASE WHEN incidents.lat IS NULL
                               THEN EXCLUDED.geocode_quality ELSE incidents.geocode_quality END,
        status      = CASE WHEN {_ACCEPT_CHANGE}
                           THEN COALESCE(EXCLUDED.status, incidents.status) ELSE incidents.status END,
        disposition = CASE WHEN {_ACCEPT_CHANGE}
                           THEN COALESCE(EXCLUDED.disposition, incidents.disposition) ELSE incidents.disposition END,
        last_changed = CASE WHEN {_ACCEPT_CHANGE} THEN EXCLUDED.last_changed ELSE incidents.last_changed END,
        raw          = CASE WHEN {_ACCEPT_CHANGE} THEN EXCLUDED.raw ELSE incidents.raw END
    WHERE (incidents.lat IS NULL AND EXCLUDED.lat IS NOT NULL)
       OR {_ACCEPT_CHANGE}
    RETURNING (xmax = 0) AS inserted
"""

_COLUMNS = 15
_MAX_ROWS_PER_STATEMENT = 1000

class PostgresStore(IncidentStore):
    def __init__(self, conn_string: str):
        self.conn = psycopg.connect(conn_string, autocommit=True)
        self._init_schema()

    def _init_schema(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    source              TEXT        NOT NULL,
                    source_incident_id  TEXT        NOT NULL,
                    occurred_at         TIMESTAMPTZ NOT NULL,
                    fetched_at          TIMESTAMPTZ NOT NULL,
                    lat                 DOUBLE PRECISION,
                    lon                 DOUBLE PRECISION,
                    nature              TEXT,
                    disposition         TEXT,
                    address             TEXT,
                    city                TEXT,
                    geocoded_at         TIMESTAMPTZ,
                    geocode_quality     TEXT,
                    status              TEXT,
                    raw                 JSONB       NOT NULL,
                    PRIMARY KEY (source, source_incident_id)
                );
            """)
            cur.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS geocode_attempts INTEGER NOT NULL DEFAULT 0")
            cur.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS geocode_locked_by TEXT")
            cur.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS geocode_locked_at TIMESTAMPTZ")
            # last_changed = last time status/disposition moved; fetched_at already
            # serves as "first seen". Backfill runs once (NULL only on first deploy).
            cur.execute("ALTER TABLE incidents ADD COLUMN IF NOT EXISTS last_changed TIMESTAMPTZ")
            cur.execute("UPDATE incidents SET last_changed = fetched_at WHERE last_changed IS NULL")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_occurred "
                        "ON incidents (occurred_at DESC);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_source_time "
                        "ON incidents (source, occurred_at DESC);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_incidents_location "
                        "ON incidents (lat, lon) WHERE lat IS NOT NULL;")
        self.conn.commit()

    def upsert(self, incidents: list[NormalizedIncident]) -> dict[str, int]:
        if not incidents:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        by_key: dict[tuple[str, str], NormalizedIncident] = {}
        for inc in incidents:
            by_key[(inc.source, inc.source_incident_id)] = inc
        rows = [self._to_row(i) for i in by_key.values()]

        row_ph = "(" + ",".join(["%s"] * _COLUMNS) + ")"
        inserted = updated = 0
        with self.conn.cursor() as cur:
            for start in range(0, len(rows), _MAX_ROWS_PER_STATEMENT):
                chunk = rows[start:start + _MAX_ROWS_PER_STATEMENT]
                sql = UPSERT_SQL.format(values=",".join([row_ph] * len(chunk)))
                cur.execute(sql, [v for row in chunk for v in row])
                for (is_insert,) in cur.fetchall():
                    if is_insert:
                        inserted += 1
                    else:
                        updated += 1
        self.conn.commit()

        skipped = len(rows) - inserted - updated
        return {"inserted": inserted, "updated": updated, "skipped": skipped}


    @staticmethod
    def _to_row(i: NormalizedIncident) -> tuple:
        return (
            i.source, i.source_incident_id,
            i.occurred_at, i.fetched_at, i.fetched_at,   # fetched_at(=first seen), last_changed
            i.lat, i.lon,
            i.nature, i.disposition, i.address, i.city,
            i.geocoded_at, i.geocode_quality,
            i.status,
            Jsonb(i.raw),
        )

    def claim_ungeocoded(self, worker_id: str, limit: int) -> list[tuple[str, str, str, str | None]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE incidents
                SET geocode_locked_by = %s,
                    geocode_locked_at = now()
                WHERE (source, source_incident_id) IN (SELECT source, source_incident_id
                                                       FROM incidents
                                                       WHERE lat IS NULL
                                                         AND address IS NOT NULL
                                                         AND TRIM(address) <> ''
                                                         AND geocode_attempts < %s
                                                         AND (geocode_locked_at IS NULL
                                                          OR  geocode_locked_at < now() - make_interval(mins => %s))
                                                       ORDER BY occurred_at DESC
                                                       LIMIT %s FOR UPDATE SKIP LOCKED)
                RETURNING source, source_incident_id, address, city
                """,
                (worker_id, MAX_GEOCODE_ATTEMPTS, GEOCODE_LEASE_MINUTES, limit),
            )
            rows = cur.fetchall()
        return rows

    def mark_geocoded(self, source: str, sid: str, lat: float, lon: float, quality: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents SET lat=%s, lon=%s, geocoded_at=now(), geocode_quality=%s "
                "WHERE source=%s AND source_incident_id=%s",
                (lat, lon, quality, source, sid),
            )
        self.conn.commit()

    def mark_geocode_attempt(self, source: str, sid: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents SET geocode_attempts = geocode_attempts + 1 "
                "WHERE source=%s AND source_incident_id=%s",
                (source, sid),
            )
        self.conn.commit()

    def mark_geocoded_batch(self, rows: list[tuple[str, str, float, float, str]]) -> None:
        if not rows:
            return
        by_key = {(s, sid): (s, sid, lat, lon, q) for (s, sid, lat, lon, q) in rows}
        sources, sids, lats, lons, quals = (list(c) for c in zip(*by_key.values()))
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents AS i "
                "SET lat = v.lat, lon = v.lon, geocoded_at = now(), geocode_quality = v.quality "
                "FROM unnest(%s::text[], %s::text[], %s::float8[], %s::float8[], %s::text[]) "
                "       AS v(source, sid, lat, lon, quality) "
                "WHERE i.source = v.source AND i.source_incident_id = v.sid",
                (sources, sids, lats, lons, quals),
            )
        self.conn.commit()

    def mark_geocode_attempt_batch(self, rows: list[tuple[str, str, int]]) -> None:
        if not rows:
            return
        tally: dict[tuple[str, str], int] = {}
        for s, sid, n in rows:
            tally[(s, sid)] = tally.get((s, sid), 0) + n
        sources = [s for (s, _sid) in tally]
        sids = [sid for (_s, sid) in tally]
        counts = list(tally.values())
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE incidents AS i "
                "SET geocode_attempts = i.geocode_attempts + v.n "
                "FROM unnest(%s::text[], %s::text[], %s::int[]) AS v(source, sid, n) "
                "WHERE i.source = v.source AND i.source_incident_id = v.sid",
                (sources, sids, counts),
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()