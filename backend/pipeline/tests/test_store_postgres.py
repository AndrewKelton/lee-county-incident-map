from datetime import datetime, timezone

import pytest

from leecad.models import NormalizedIncident

pytestmark = pytest.mark.integration


def test_upsert_inserts_and_reads_back(postgres_store):
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    incident = NormalizedIncident(
        source="lee_county",
        source_incident_id="SMOKE-1",
        occurred_at=now,
        fetched_at=now,
        nature="TEST NATURE",
        address="1 MAIN ST",
        city="FORT MYERS",
        status="ACTIVE",
        raw={"probe": True},
    )

    assert postgres_store.upsert([incident]) == {"inserted": 1, "updated": 0, "skipped": 0}

    with postgres_store.conn.cursor() as cur:
        cur.execute(
            "SELECT nature, address, status, raw FROM incidents "
            "WHERE source = %s AND source_incident_id = %s",
            (incident.source, incident.source_incident_id),
        )
        row = cur.fetchone()

    assert row == ("TEST NATURE", "1 MAIN ST", "ACTIVE", {"probe": True})
