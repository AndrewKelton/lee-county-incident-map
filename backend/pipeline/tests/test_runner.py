from datetime import datetime, timezone

import pytest

from leecad.models import NormalizedIncident
from leecad.pipeline import runner


class FakeAdapter:
    """Normalizes any record carrying an "id". Anything else raises, like the real adapters do."""

    def __init__(self, records):
        self.records = records

    def fetch_raw(self):
        return self.records

    def normalize(self, raw, fetched_at):
        return NormalizedIncident(
            source="fake",
            source_incident_id=raw["id"],
            occurred_at=datetime(2026, 7, 13, tzinfo=timezone.utc),
            fetched_at=fetched_at,
            raw=raw,
        )


@pytest.fixture
def feed(monkeypatch):
    def register(records):
        monkeypatch.setitem(runner.REGISTRY, "fake", lambda: FakeAdapter(records))

    return register


def test_one_bad_record_does_not_cost_us_the_fetch(feed):
    feed([{"id": "a"}, {"malformed": True}, {"id": "c"}])
    assert [i.source_incident_id for i in runner.fetch_source("fake")] == ["a", "c"]


def test_every_record_failing_raises(feed):
    # An upstream schema change. Returning [] here would look like "no incidents".
    feed([{"malformed": True}, {"malformed": True}])
    with pytest.raises(RuntimeError, match="all 2 records failed"):
        runner.fetch_source("fake")


def test_an_empty_feed_is_not_an_error(feed):
    feed([])
    assert runner.fetch_source("fake") == []