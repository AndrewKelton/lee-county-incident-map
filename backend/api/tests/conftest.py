import os
from datetime import UTC, datetime

import psycopg
import pytest

from leecad_api.app import create_app

LEE = "lee_county"
CCM = "community_crime_map"
TRAFFIC = "lee_county_traffic"


def at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 6, day, hour, tzinfo=UTC)


ROWS = [
    (LEE, "25-001", at(10), "ASSAULT", "1 MAIN ST", "FORT MYERS", 26.64, -81.87, "EXACT"),
    (CCM, "25-001", at(9), "ASSAULT", "1 MAIN ST", "FORT MYERS", 26.65, -81.88, "ccm:block"),

    (CCM, "25-002", at(11), "GRAND THEFT", "2 OAK AVE", "CAPE CORAL", 26.56, -81.95, "ccm:block"),

    (LEE, "25-003", at(12), "BURGLARY", "3 PINE RD", "N FORT MYERS", None, None, None),
    (CCM, "25-003", at(12), "BURGLARY", "3 PINE RD", "N FORT MYERS", 26.70, -81.90, "ccm:block"),

    (LEE, "25-004", at(13), "ASSAULT", "4 ELM ST", "ESTERO", 26.43, -81.80, "nominatim:primary"),
    (CCM, "25-004", at(13), "ASSAULT", "4 ELM ST", "ESTERO", 26.44, -81.81, "ccm:block"),

    (LEE, "25-005", at(14), "GRAND THEFT AUTO", "5 BAY DR", "SANIBEL", 26.45, -82.02, "EXACT"),
    (CCM, "25-005", at(14), "GRAND THEFT AUTO", "5 BAY DR", "SANIBEL", 26.46, -82.03, "ccm:block"),

    (LEE, "25-006", at(15), "NOT A REAL NATURE", "6 GULF BLVD", "FORT MYERS", 26.60, -81.85, "EXACT"),
    (LEE, "25-007", at(16), "ASSAULT", "7 FAR AWAY", "FORT MYERS", 41.88, -87.63, "EXACT"),

    (TRAFFIC, "T-001", at(17), "CRASH", "8 CROSS ST", "FORT MYERS", 26.62, -81.86, "EXACT"),

    (LEE, "25-008", at(18), "ASSAULT", "9 TIE ST", "FORT MYERS", 26.61, -81.84, "EXACT"),
    (LEE, "25-009", at(18), "ASSAULT", "10 TIE ST", "FORT MYERS", 26.61, -81.84, "EXACT"),
    (LEE, "25-010", at(18), "ASSAULT", "11 TIE ST", "FORT MYERS", 26.61, -81.84, "EXACT"),
]

INSERT = """
    INSERT INTO incidents (source, source_incident_id, occurred_at, fetched_at, last_changed,
                           nature, address, city, lat, lon, geocode_quality, raw)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, '{}'::jsonb)
"""


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: needs a live Postgres")


@pytest.fixture(scope="session")
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set; see backend/api/README.md")
    return url


@pytest.fixture
def seeded(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE incidents")
        for source, sid, occurred, nature, address, city, lat, lon, quality in ROWS:
            conn.execute(INSERT, (source, sid, occurred, occurred, occurred,
                                  nature, address, city, lat, lon, quality))
    return database_url


@pytest.fixture
def client(seeded):
    return create_app(seeded).test_client()
