import json
from pathlib import Path
from datetime import timezone
from adapters.lee_county import LeeCountyAdapter

FIXTURE = json.loads(Path("tests/fixtures/lee_county_sample.json").read_text())

def test_normalize_produces_valid_records():
    adapter = LeeCountyAdapter()
    for raw in FIXTURE:
        result = adapter.normalize(raw)
        assert result.source == "lee_county"
        assert result.occurred_at.tzinfo == timezone.utc
        assert result.source_incident_id

def test_normalize_handles_missing_optional_fields():
    adapter = LeeCountyAdapter()
    minimal = {"id": 123, "occuredDate": "2026-05-24 16:19:35.0000000"}
    result = adapter.normalize(minimal)
    assert result.city is None
    assert result.lat is None
    assert result.lon is None
