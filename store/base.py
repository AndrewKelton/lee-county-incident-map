from abc import ABC, abstractmethod

from models import NormalizedIncident

class IncidentStore(ABC):
    @abstractmethod
    def upsert(self, incidents: list[NormalizedIncident]) -> dict[str, int]:
        """Persist incidents. Return counts: {'inserted': N, 'updated': M, 'skipped': K}."""
