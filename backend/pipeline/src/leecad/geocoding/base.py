from abc import ABC, abstractmethod

class Geocoder(ABC):
    @abstractmethod
    def geocode(self, address: str, city: str, state: str = "FL") -> tuple[float, float, str] | None:
        """Return (lat, lon, quality) or None if no match"""

class GeocodeCache(ABC):
    @abstractmethod
    def get(self, key: str) -> tuple[float, float, str] | None: ...

    @abstractmethod
    def set(self, key: str, lat: float, lon: float, quality: str) -> None: ...

    @abstractmethod
    def get_many(self, keys: list[str]) -> dict[str, tuple[float, float, str]]:
        """Look up many keys in one round trip. Returns only the keys that hit."""

    @abstractmethod
    def set_many(self, entries: dict[str, tuple[float, float, str]]) -> None:
        """Upsert many cache entries (key -> (lat, lon, quality)) in one round trip."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying database connection."""