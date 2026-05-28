from adapters.base import IncidentSource
from models import NormalizedIncident

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")

class LeeCountyAdapter(IncidentSource):
    name = "lee_county"
    URL = "https://www.sheriffleefl.org/public-api/incidents/q"

    def _parse_lee_datetime(self, s: str) -> datetime:
        # "2026-05-24 16:19:35.0000000" → ignore everything after the seconds
        naive = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        return naive.replace(tzinfo=EASTERN).astimezone(timezone.utc)

    def fetch_raw(self) -> list[dict]:
        return self.fetch_json(self.URL, params={"limit": 1000})

    def normalize(self, raw: dict, fetched_at: datetime) -> "NormalizedIncident":
        return NormalizedIncident(
            source=self.name,
            source_incident_id=str(raw["id"]),
            occurred_at=self._parse_lee_datetime(raw.get("occuredDate")),
            fetched_at=datetime.now(timezone.utc),
            nature=raw.get("nature"),
            disposition=raw.get("disposition"),
            address=raw.get("address"),
            city=raw.get("city"),
            raw=raw
        )
