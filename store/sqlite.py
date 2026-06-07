import sqlite3
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from paths import INCIDENTS_DB
from models import NormalizedIncident
from store.base import IncidentStore, MAX_GEOCODE_ATTEMPTS, GEOCODE_LEASE_MINUTES

INSERT_SQL = """
             INSERT INTO incidents
             (source, source_incident_id, occurred_at, fetched_at, last_changed, lat, lon,
              nature, disposition, address, city, geocoded_at, geocode_quality,
              status, raw)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) \
             """

class SqliteStore(IncidentStore):
    def __init__(self, path: str = None):
        path = Path(path) if path else INCIDENTS_DB
        path.parent.mkdir(exist_ok=True, parents=True)
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
                last_changed        TEXT,
                lat                 REAL,
                lon                 REAL,
                nature              TEXT,
                disposition         TEXT,
                address             TEXT,
                city                TEXT,
                geocoded_at         TEXT,
                geocode_quality     TEXT,
                status              TEXT,
                raw                 TEXT NOT NULL,
                PRIMARY KEY         (source, source_incident_id)
            );
            CREATE INDEX IF NOT EXISTS idx_occurred_at ON incidents(occurred_at);
            CREATE INDEX IF NOT EXISTS idx_source_time ON incidents(source, occurred_at);
        """)
        self._migrate()
        self.conn.commit()

    def upsert(self, incidents: list[NormalizedIncident]) -> dict[str, int]:
        if not incidents:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        inserted = updated = skipped = 0

        with self.conn:
            for incident in incidents:
                existing = self.conn.execute(
                    "SELECT lat, status, disposition, last_changed FROM incidents "
                    "WHERE source = ? AND source_incident_id = ?",
                    (incident.source, incident.source_incident_id),
                ).fetchone()

                if existing is None:
                    self.conn.execute(INSERT_SQL, self._to_row(incident))
                    inserted += 1
                    continue

                existing_lat, existing_status, existing_disposition, existing_last_changed = existing
                sets, params = [], []

                if existing_lat is None and incident.lat is not None:
                    sets += ["lat = ?", "lon = ?", "geocoded_at = ?", "geocode_quality = ?"]
                    params += [
                        incident.lat, incident.lon,
                        incident.geocoded_at.isoformat() if incident.geocoded_at else None,
                        incident.geocode_quality,
                    ]

                # Recency guard: only accept status/disposition from data newer than the
                # last accepted change (mirrors the Postgres upsert); geocode fill is exempt.
                fresh = existing_last_changed is None
                if not fresh:
                    prev = datetime.fromisoformat(existing_last_changed)
                    if prev.tzinfo is None:
                        prev = prev.replace(tzinfo=timezone.utc)
                    fresh = incident.fetched_at > prev

                content_changed = False

                if fresh and incident.status is not None and incident.status != existing_status:
                    sets += ["status = ?"]
                    params += [incident.status]
                    content_changed = True

                if fresh and incident.disposition is not None and incident.disposition != existing_disposition:
                    sets += ["disposition = ?"]
                    params += [incident.disposition]
                    content_changed = True

                # last_changed + raw advance only on a real content change, never on a
                # geocode fill (mirrors the Postgres upsert).
                if content_changed:
                    sets += ["last_changed = ?", "raw = ?"]
                    params += [incident.fetched_at.isoformat(), json.dumps(incident.raw)]

                if sets:
                    params += [incident.source, incident.source_incident_id]
                    self.conn.execute(
                        f"UPDATE incidents SET {', '.join(sets)} "
                        f"WHERE source = ? AND source_incident_id = ?",
                        params
                    )
                    updated += 1
                else:
                    skipped += 1

        return {"inserted": inserted, "updated": updated, "skipped": skipped}



    @staticmethod
    def _to_row(i: NormalizedIncident) -> tuple:
        return (
            i.source, i.source_incident_id,
            i.occurred_at.isoformat(), i.fetched_at.isoformat(), i.fetched_at.isoformat(),
            i.lat, i.lon, i.nature, i.disposition, i.address, i.city,
            i.geocoded_at.isoformat() if i.geocoded_at else None,
            i.geocode_quality,
            i.status,
            json.dumps(i.raw),
        )

    def _migrate(self):
        cols = {row[1] for row in self.conn.execute("PRAGMA table_info(incidents)")}
        if "status" not in cols:
            self.conn.execute("ALTER TABLE incidents ADD COLUMN status TEXT")
        if "geocode_attempts" not in cols:
            self.conn.execute(
                "ALTER TABLE incidents ADD COLUMN geocode_attempts INTEGER NOT NULL DEFAULT 0"
            )
        if "geocode_locked_by" not in cols:
            self.conn.execute("ALTER TABLE incidents ADD COLUMN geocode_locked_by TEXT")
        if "geocode_locked_at" not in cols:
            self.conn.execute("ALTER TABLE incidents ADD COLUMN geocode_locked_at TEXT")
        if "last_changed" not in cols:
            self.conn.execute("ALTER TABLE incidents ADD COLUMN last_changed TEXT")
            self.conn.execute("UPDATE incidents SET last_changed = fetched_at WHERE last_changed IS NULL")

    def claim_ungeocoded(self, worker_id: str, limit: int) -> list[tuple[str, str, str, str | None]]:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=GEOCODE_LEASE_MINUTES)).isoformat()
        with self.conn:
            rows = self.conn.execute(
                "SELECT source, source_incident_id, address, city FROM incidents "
                "WHERE lat IS NULL AND address IS NOT NULL AND TRIM(address) != '' "
                "AND geocode_attempts < ? "
                "AND (geocode_locked_at IS NULL OR geocode_locked_at < ?) "
                "ORDER BY occurred_at DESC LIMIT ?",
                (MAX_GEOCODE_ATTEMPTS, cutoff, limit),
            ).fetchall()
            now = datetime.now(timezone.utc).isoformat()
            self.conn.executemany(
                "UPDATE incidents SET geocode_locked_by=?, geocode_locked_at=? "
                "WHERE source=? AND source_incident_id=?",
                [(worker_id, now, s, sid) for s, sid, _addr, _city in rows],
            )
        return rows

    def mark_geocoded(self, source: str, sid: str, lat: float, lon: float, quality: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE incidents SET lat=?, lon=?, geocoded_at=?, geocode_quality=? "
                "WHERE source=? AND source_incident_id=?",
                (lat, lon, datetime.now(timezone.utc).isoformat(), quality, source, sid),
            )

    def mark_geocode_attempt(self, source: str, sid: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE incidents SET geocode_attempts = geocode_attempts + 1, geocode_locked_at = NULL "
                "WHERE source=? AND source_incident_id=?",
                (source, sid),
            )

    def mark_geocoded_batch(self, rows: list[tuple[str, str, float, float, str]]) -> None:
        if not rows:
            return
        by_key = {(s, sid): (s, sid, lat, lon, q) for (s, sid, lat, lon, q) in rows}
        now = datetime.now(timezone.utc).isoformat()
        with self.conn:
            self.conn.executemany(
                "UPDATE incidents SET lat=?, lon=?, geocoded_at=?, geocode_quality=? "
                "WHERE source=? AND source_incident_id=?",
                [(lat, lon, now, q, s, sid) for (s, sid, lat, lon, q) in by_key.values()],
            )

    def mark_geocode_attempt_batch(self, rows: list[tuple[str, str, int]]) -> None:
        if not rows:
            return
        tally: dict[tuple[str, str], int] = {}
        for s, sid, n in rows:
            tally[(s, sid)] = tally.get((s, sid), 0) + n
        with self.conn:
            self.conn.executemany(
                "UPDATE incidents SET geocode_attempts = geocode_attempts + ?, geocode_locked_at = NULL "
                "WHERE source=? AND source_incident_id=?",
                [(n, s, sid) for (s, sid), n in tally.items()],
            )
