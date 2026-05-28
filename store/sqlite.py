import sqlite3
import json
from pathlib import Path
from datetime import datetime
from models import NormalizedIncident
from store.base import IncidentStore

class SqliteStore(IncidentStore):
    def __init__(self, path: str = "data/incidents.db"):
        Path(path).parent.mkdir(exist_ok=True, parents=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS incidents(
                source              TEXT NOT NULL,
                source_incident_id  TEXT NOT NULL,
                occurred_at         TEXT NOT NULL,
                fetched_at          TEXT NOT NULL,
                lat                 REAL,
                lon                 REAL,
                nature              TEXT,
                disposition         TEXT,
                address             TEXT,
                city                TEXT,
                geocoded_at         TEXT,
                geocode_quality     TEXT,
                raw                 TEXT NOT NULL,
                PRIMARY KEY         (source, source_incident_id)
            );
            CREATE INDEX IF NOT EXISTS idx_occurred_at ON incidents(occurred_at);
            CREATE INDEX IF NOT EXISTS idx_source_time ON incidents(source, occurred_at);
        """)
        self.conn.commit()

    def upsert(self, incidents: list[NormalizedIncident]) -> dict[str, int]:
        if not incidents:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        inserted = updated = skipped = 0

        with self.conn:
            for incident in incidents:
                existing_lat = self.conn.execute(
                    "SELECT lat FROM incidents "
                    "WHERE source = ? AND source_incident_id = ?",
                    (incident.source, incident.source_incident_id),
                ).fetchone()

                if existing_lat is None:
                    self.conn.execute(
                        "INSERT INTO incidents VALUES "
                        "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        self._to_row(incident)
                    )
                    inserted += 1
                elif existing_lat[0] is None and incident.lat is not None:
                    self.conn.execute(
                        "UPDATE incidents SET lat=?, lon=?, "
                        "geocoded_at=?, geocode_quality=? "
                        "WHERE source=? AND source_incident_id=?",
                        (
                            incident.lat, incident.lon,
                            incident.geocoded_at.isoformat() if incident.geocoded_at else None,
                            incident.geocode_quality,
                            incident.source, incident.source_incident_id
                        ),
                    )
                    updated += 1
                else:
                    skipped += 1
        return {"inserted": inserted, "updated": updated, "skipped": skipped}

    @staticmethod
    def _to_row(i: NormalizedIncident) -> tuple:
        return (
            i.source, i.source_incident_id,
            i.occurred_at.isoformat(), i.fetched_at.isoformat(),
            i.lat, i.lon, i.nature, i.disposition, i.address, i.city,
            i.geocoded_at.isoformat() if i.geocoded_at else None,
            i.geocode_quality,
            json.dumps(i.raw),
        )


