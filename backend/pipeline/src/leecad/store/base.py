from abc import ABC, abstractmethod

from leecad.models import NormalizedIncident

MAX_GEOCODE_ATTEMPTS = 3
GEOCODE_LEASE_MINUTES = 120  # must outlive the hour a worker holds rows un-flushed (sync model)

class IncidentStore(ABC):
    @abstractmethod
    def upsert(self, incidents: list[NormalizedIncident]) -> dict[str, int]:
        """Persist incidents. Return counts: {'inserted': N, 'updated': M, 'skipped': K}."""

    @abstractmethod
    def claim_ungeocoded(self, worker_id: str, limit: int) -> list[tuple[str, str, str, str | None]]:
        """Atomically lease up to `limit` ungeocoded rows for this worker, return them as
        (source, source_incident_id, address, city). Free or expired leases are claimable."""

    @abstractmethod
    def mark_geocoded(self, source: str, sid: str, lat: float, lon: float, quality: str) -> None:
        """Records a successful geocode"""

    @abstractmethod
    def mark_geocode_attempt(self, source: str, sid: str) -> None:
        """Records a failed geocode attempt (so we eventually stop retrying)"""

    @abstractmethod
    def mark_geocoded_batch(self, rows: list[tuple[str, str, float, float, str]]) -> None:
        """Bulk version of mark_geocoded. rows: (source, sid, lat, lon, quality)."""

    @abstractmethod
    def mark_geocode_attempt_batch(self, rows: list[tuple[str, str, int]]) -> None:
        """Bulk version of mark_geocode_attempt. rows: (source, sid, n_attempts); counts are
        summed per (source, sid) so a worker batching several tries of one address over an
        hour bumps geocode_attempts by the true total, not 1."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying database connection."""