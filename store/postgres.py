import psycopg
from psycopg.types.json import Jsonb
from models import NormalizedIncident
from store.base import IncidentStore

UPSERT_SQL = """
    INSERT INTO incidents
        (source, source_incident_id, occurred_at, fetched_at, lat, lon,
         nature, disposition, address, city, geocoded_at, geocode_quality, status, raw)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source, source_incident_id) DO UPDATE SET
        lat = COALESCE(incidents.lat, EXCLUDED.lat),
        lon = COALESCE(incidents.lon, EXCLUDED.lon),
        geocoded_at = CASE WHEN incidents.lat IS NULL
                           THEN EXCLUDED.geocoded_at ELSE incidents.geocoded_at END,
        geocode_quality = CASE WHEN incidents.lat IS NULL
                               THEN EXCLUDED.geocode_quality ELSE incidents.geocode_quality END,
        status = COALESCE(EXCLUDED.status, incidents.status)
"""

class PostgresStore(IncidentStore):
    def __init__(self, conn_string: str):
        self.conn = psycopg.connect(conn_string)
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

        source = incidents[0].source
        ids = [i.source_incident_id for i in incidents]

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT source_incident_id, lat, status FROM incidents "
                "WHERE source = %s AND source_incident_id = ANY(%s)",
                (source, ids),
            )
            existing = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        inserted = updated = skipped = 0
        for inc in incidents:
            prev = existing.get(inc.source_incident_id)
            if prev is None:
                inserted += 1
            elif (prev[0] is None and inc.lat is not None) or \
                    (inc.status is not None and inc.status != prev[1]):
                updated += 1
            else:
                skipped += 1

        with self.conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, [self._to_row(i) for i in incidents])
        self.conn.commit()

        return {"inserted": inserted, "updated": updated, "skipped": skipped}

    @staticmethod
    def _to_row(i: NormalizedIncident) -> tuple:
        return (
            i.source, i.source_incident_id,
            i.occurred_at, i.fetched_at,
            i.lat, i.lon,
            i.nature, i.disposition, i.address, i.city,
            i.geocoded_at, i.geocode_quality,
            i.status,
            Jsonb(i.raw),
        )
