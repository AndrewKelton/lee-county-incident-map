from datetime import datetime, timezone

import pytest

from leecad.models import NormalizedIncident

pytestmark = pytest.mark.integration

T1 = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 7, 13, 13, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 7, 13, 14, 0, tzinfo=timezone.utc)


def incident(sid: str, fetched_at: datetime, **fields) -> NormalizedIncident:
    return NormalizedIncident(
        source="lee_county",
        source_incident_id=sid,
        occurred_at=T1,
        fetched_at=fetched_at,
        raw={},
        **fields,
    )


def read(store, sid: str, columns: str) -> tuple:
    with store.conn.cursor() as cur:
        cur.execute(
            f"SELECT {columns} FROM incidents WHERE source = 'lee_county' AND source_incident_id = %s",
            (sid,),
        )
        return cur.fetchone()


def test_upsert_inserts_and_reads_back(postgres_store):
    assert postgres_store.upsert(
        [incident("SMOKE-1", T1, nature="TEST NATURE", address="1 MAIN ST", status="ACTIVE")]
    ) == {"inserted": 1, "updated": 0, "skipped": 0}

    assert read(postgres_store, "SMOKE-1", "nature, address, status") == (
        "TEST NATURE", "1 MAIN ST", "ACTIVE",
    )


def test_a_stale_fetch_cannot_overwrite_a_newer_status(postgres_store):
    postgres_store.upsert([incident("stale", T2, status="CLEARED")])

    counts = postgres_store.upsert([incident("stale", T1, status="DISPATCHED")])

    assert counts == {"inserted": 0, "updated": 0, "skipped": 1}
    assert read(postgres_store, "stale", "status, last_changed") == ("CLEARED", T2)


def test_geocoded_coordinates_survive_a_later_feed_update(postgres_store):
    # The feed never carries coordinates. Geocoding fills them in afterwards, so every later fetch
    # of the same incident arrives with lat and lon empty. They must not wipe out the geocode.
    postgres_store.upsert([incident("geo", T1, status="DISPATCHED")])
    postgres_store.mark_geocoded("lee_county", "geo", 26.6406, -81.8723, "rooftop")

    postgres_store.upsert([incident("geo", T2, status="CLEARED")])

    assert read(postgres_store, "geo", "lat, lon, geocode_quality, status") == (
        26.6406, -81.8723, "rooftop", "CLEARED",
    )


def test_a_newer_fetch_takes_a_changed_status_and_skips_an_unchanged_one(postgres_store):
    postgres_store.upsert([incident("live", T1, status="DISPATCHED")])

    assert postgres_store.upsert([incident("live", T2, status="CLEARED")]) == {
        "inserted": 0, "updated": 1, "skipped": 0,
    }
    assert read(postgres_store, "live", "status, last_changed") == ("CLEARED", T2)

    # An open incident comes back on every fetch until it drops off the feed. Re-seeing it
    # unchanged has to cost nothing, and must not advance last_changed.
    assert postgres_store.upsert([incident("live", T3, status="CLEARED")]) == {
        "inserted": 0, "updated": 0, "skipped": 1,
    }
    assert read(postgres_store, "live", "last_changed") == (T2,)


def test_duplicates_within_one_batch_collapse(postgres_store):
    # A drain feeds many hourly objects through one upsert, so the same incident shows up several
    # times. Postgres rejects two rows with the same conflict key in one ON CONFLICT statement, so
    # upsert dedups first and keeps the last. Callers sort oldest first to make that the freshest.
    counts = postgres_store.upsert([
        incident("dupe", T1, status="DISPATCHED"),
        incident("dupe", T2, status="CLEARED"),
    ])

    assert counts == {"inserted": 1, "updated": 0, "skipped": 0}
    assert read(postgres_store, "dupe", "status, last_changed") == ("CLEARED", T2)
