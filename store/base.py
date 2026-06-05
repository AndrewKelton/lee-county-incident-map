from abc import ABC, abstractmethod

from models import NormalizedIncident

MAX_GEOCODE_ATTEMPTS = 3

class IncidentStore(ABC):
    @abstractmethod
    def upsert(self, incidents: list[NormalizedIncident]) -> dict[str, int]:
        """Persist incidents. Return counts: {'inserted': N, 'updated': M, 'skipped': K}."""

    @abstractmethod
    def fetch_ungeocoded(self, limit: int) -> list[tuple[str, str, str, str | None]]:
        """Rows needing coordinates: (source, source_incident_id, address, city)"""

    @abstractmethod
    def mark_geocoded(self, source: str, sid: str, lat: float, lon: float, quality: str) -> None:
        """Records a successful geocode"""

    @abstractmethod
    def mark_geocode_attempt(self, source: str, sid: str) -> None:
        """Records a failed geocode attempt (so we eventually stop retrying)"""