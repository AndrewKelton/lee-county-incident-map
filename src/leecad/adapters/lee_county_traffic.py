from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from leecad.adapters.base import IncidentSource
from leecad.models import NormalizedIncident

EASTERN = ZoneInfo("America/New_York")

class LeeCountyTrafficAdapter(IncidentSource):
    name = "lee_county_traffic"
    URL = "https://www.sheriffleefl.org/public-api/traffic"

    def _parse_date(self, s: str) -> datetime:
        naive = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        return naive.replace(tzinfo=EASTERN).astimezone(timezone.utc)

    def fetch_raw(self) -> list[dict]:
        return self.fetch_json(self.URL)

    def normalize(self, raw: dict, fetched_at: datetime) -> "NormalizedIncident":
        return NormalizedIncident(
            source=self.name,
            source_incident_id=raw["id"],
            occurred_at=self._parse_date(raw["date"]),
            fetched_at=fetched_at,
            nature=raw.get("nature"),
            address=raw.get("address"),
            city=raw.get("city"),
            status=raw.get("status"),
            raw=raw,
        )